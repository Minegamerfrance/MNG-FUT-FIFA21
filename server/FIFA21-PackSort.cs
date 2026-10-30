using System;
using System.ComponentModel;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;

// Presentation-only correction for the retail New Items player comparator.
// Patch the live process, never CardsDLL on disk or any card identity/value.
internal static class PackSort {
 const long Start=0x23768b, FunctionStart=0x2375c0, FunctionEnd=0x237727;
 const string Original="418b513c41395138448b413c410f47513844394138440f474138413bd074040f97c0c3";
 const string Replacement="418b51283b5128741a0f97c0c390909090909090909090909090909090909090909090";
 [DllImport("kernel32.dll",SetLastError=true)] static extern IntPtr OpenProcess(uint access,bool inherit,int pid);
 [DllImport("kernel32.dll",SetLastError=true)] static extern IntPtr OpenThread(uint access,bool inherit,int tid);
 [DllImport("kernel32.dll")] static extern bool CloseHandle(IntPtr h);
 [DllImport("kernel32.dll",SetLastError=true)] static extern bool GetThreadContext(IntPtr h,IntPtr context);
 [DllImport("kernel32.dll",SetLastError=true)] static extern bool ReadProcessMemory(IntPtr h,IntPtr address,byte[] b,UIntPtr n,out UIntPtr done);
 [DllImport("kernel32.dll",SetLastError=true)] static extern bool WriteProcessMemory(IntPtr h,IntPtr address,byte[] b,UIntPtr n,out UIntPtr done);
 [DllImport("kernel32.dll",SetLastError=true)] static extern bool VirtualProtectEx(IntPtr h,IntPtr address,UIntPtr n,uint protect,out uint previous);
 [DllImport("kernel32.dll")] static extern bool FlushInstructionCache(IntPtr h,IntPtr address,UIntPtr n);
 [DllImport("ntdll.dll")] static extern int NtSuspendProcess(IntPtr h);
 [DllImport("ntdll.dll")] static extern int NtResumeProcess(IntPtr h);
 static byte[] Hex(string s){return Enumerable.Range(0,s.Length/2).Select(i=>Convert.ToByte(s.Substring(i*2,2),16)).ToArray();}
 static void Need(bool ok,string reason){if(!ok)throw new InvalidOperationException(reason+" ("+new Win32Exception().Message+")");}
 static byte[] Read(IntPtr h,long address,int size){var b=new byte[size];UIntPtr n;Need(ReadProcessMemory(h,new IntPtr(address),b,(UIntPtr)size,out n)&&n.ToUInt64()==(ulong)size,"Read failed");return b;}
 static void Write(IntPtr h,long address,byte[] b){UIntPtr n;Need(WriteProcessMemory(h,new IntPtr(address),b,(UIntPtr)b.Length,out n)&&n.ToUInt64()==(ulong)b.Length,"Write failed");}
 static bool ComparatorIdle(Process game,long module){
  foreach(ProcessThread thread in game.Threads){
   IntPtr h=OpenThread(8,false,thread.Id);Need(h!=IntPtr.Zero,"Cannot inspect suspended thread");
   IntPtr allocation=Marshal.AllocHGlobal(1280);
   try{
    IntPtr aligned=new IntPtr((allocation.ToInt64()+15)&~15L);
    Marshal.Copy(new byte[1232],0,aligned,1232);Marshal.WriteInt32(aligned,48,0x100001);
    Need(GetThreadContext(h,aligned),"Cannot read suspended thread context");
    long rip=Marshal.ReadInt64(aligned,248);
    if(rip>=module+FunctionStart&&rip<module+FunctionEnd)return false;
   }finally{Marshal.FreeHGlobal(allocation);CloseHandle(h);}
  }
  return true;
 }
 static void Install(int pid,bool wait,bool restore,bool quietAlready){
  while(true){
   using(var game=Process.GetProcessById(pid)){
    Need(game.ProcessName=="FIFA21"||game.ProcessName=="FIFA21_Trial","Not a FIFA21 process");
    var dll=game.Modules.Cast<ProcessModule>().SingleOrDefault(m=>m.ModuleName.Equals("CardsDLL_Win64_retail.dll",StringComparison.OrdinalIgnoreCase));
    if(dll==null){Need(wait,"CardsDLL not loaded");Thread.Sleep(1000);continue;}
    long module=dll.BaseAddress.ToInt64(),address=module+Start;
    IntPtr h=OpenProcess(0x1f0fff,false,pid);Need(h!=IntPtr.Zero,"Cannot open FIFA21");
    try{
     var from=Hex(restore?Replacement:Original);var to=Hex(restore?Original:Replacement);
     Need(Read(h,module+FunctionStart,8).SequenceEqual(Hex("4c8b4a104d85c90f")),"Unsupported New Items comparator entry");
     Need(Read(h,module+0x2376ae,11).SequenceEqual(Hex("8b4118413941180f9ec0c3")),"Unsupported New Items comparator fallback");
     if(Read(h,address,to.Length).SequenceEqual(to)){if(!quietAlready)Console.WriteLine("[ALREADY] Pack display ordering is ready.");return;}
     Need(Read(h,address,from.Length).SequenceEqual(from),"Unknown comparator bytes; no change made");
     for(int attempt=0;attempt<10;attempt++){
      Need(NtSuspendProcess(h)==0,"Cannot pause FIFA21 for atomic installation");
      bool idle=false,writable=false;uint prior=0,ignored;
      try{
       idle=ComparatorIdle(game,module);
       if(idle){
        Need(Read(h,address,from.Length).SequenceEqual(from),"Comparator changed while preparing");
        Need(VirtualProtectEx(h,new IntPtr(address),(UIntPtr)from.Length,0x40,out prior),"Cannot change code protection");writable=true;
        try{Write(h,address,to);Need(Read(h,address,to.Length).SequenceEqual(to),"Patch verification failed");}
        catch{Write(h,address,from);throw;}
        finally{Need(FlushInstructionCache(h,new IntPtr(address),(UIntPtr)from.Length),"Cannot refresh instruction cache");}
       }
      }finally{
       if(writable)VirtualProtectEx(h,new IntPtr(address),(UIntPtr)from.Length,prior,out ignored);
       NtResumeProcess(h);
      }
      if(idle){Console.WriteLine("[READY] "+(restore?"Original":"Server-defined")+" New Items player ordering installed. IDs, ratings, prices and game files unchanged.");return;}
      Thread.Sleep(50);
     }
     throw new InvalidOperationException("Comparator remained busy; no change made");
    }finally{CloseHandle(h);}
   }
  }
 }
 static int Main(string[] args){
  StreamWriter log=null;
  try{
   Need(Environment.Is64BitProcess,"x64 required");int li=Array.IndexOf(args,"--log");
   if(li>=0){log=new StreamWriter(args[li+1],false,Encoding.UTF8);log.AutoFlush=true;Console.SetOut(log);Console.SetError(log);}
   int pi=Array.IndexOf(args,"--pid");Need(pi>=0&&pi+1<args.Length,"Missing PID");
   int pid=int.Parse(args[pi+1]);bool watch=args.Contains("--watch"),created;
   using(var mutex=new Mutex(false,"Local\\MNGFUT-PackSort-"+pid,out created)){
    if(!created){Console.WriteLine("[ALREADY] Pack sort helper is watching this game.");return 0;}
    bool quiet=false;
    do{
     try{Install(pid,args.Contains("--wait"),args.Contains("--restore"),quiet);}
     catch(ArgumentException){return 0;}
     if(!watch)return 0;
     quiet=true;Thread.Sleep(1000);
    }while(true);
   }
  }catch(Exception e){Console.Error.WriteLine(e);return 1;}finally{if(log!=null)log.Dispose();}
 }
}

using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;

// Local display override only. Original game files and all other translations stay intact.
internal static class RarityNames {
 const long GlobalRva=0x522dd0;
 const int EntryOffset=0x100, DataOffset=0x2000;
 static readonly byte[] Magic=Encoding.ASCII.GetBytes("MNG21-RARITY-NAMES-V2\0");
 static readonly string[] Names={"Rulebreakers","Flashback","Prime","Ballon d'Or","MNG FUT"};
 static readonly int[] Ids={22,37,38,63,19};
 [DllImport("kernel32.dll",SetLastError=true)] static extern IntPtr OpenProcess(uint access,bool inherit,int pid);
 [DllImport("kernel32.dll")] static extern bool CloseHandle(IntPtr h);
 [DllImport("kernel32.dll")] static extern IntPtr GetCurrentProcess();
 [DllImport("kernel32.dll",SetLastError=true)] static extern bool ReadProcessMemory(IntPtr h,IntPtr a,byte[] b,UIntPtr n,out UIntPtr done);
 [DllImport("kernel32.dll",SetLastError=true)] static extern bool WriteProcessMemory(IntPtr h,IntPtr a,byte[] b,UIntPtr n,out UIntPtr done);
 [DllImport("kernel32.dll",SetLastError=true)] static extern IntPtr VirtualAllocEx(IntPtr h,IntPtr a,UIntPtr n,uint type,uint protect);
 [DllImport("kernel32.dll",SetLastError=true)] static extern bool VirtualFreeEx(IntPtr h,IntPtr a,UIntPtr n,uint type);
 [DllImport("kernel32.dll",SetLastError=true)] static extern bool VirtualProtectEx(IntPtr h,IntPtr a,UIntPtr n,uint protect,out uint previous);
 [DllImport("kernel32.dll")] static extern bool FlushInstructionCache(IntPtr h,IntPtr a,UIntPtr n);
 [DllImport("ntdll.dll")] static extern int NtSuspendProcess(IntPtr h);
 [DllImport("ntdll.dll")] static extern int NtResumeProcess(IntPtr h);
 [UnmanagedFunctionPointer(CallingConvention.Winapi)] delegate int Translate(IntPtr self,IntPtr output,IntPtr key,int flags);
 [UnmanagedFunctionPointer(CallingConvention.Winapi)] delegate IntPtr AssignText(IntPtr output,IntPtr first,IntPtr last);
 sealed class Asm {
  public List<byte> B=new List<byte>(); Dictionary<string,int> labels=new Dictionary<string,int>(); List<KeyValuePair<int,string>> fixups=new List<KeyValuePair<int,string>>();
  public void E(params byte[] b){B.AddRange(b);} public void I64(long v){E(BitConverter.GetBytes(v));}
  public void L(string n){labels.Add(n,B.Count);} public void J(string n,params byte[] op){E(op);fixups.Add(new KeyValuePair<int,string>(B.Count,n));E(0,0,0,0);}
  public byte[] Finish(){var b=B.ToArray();foreach(var f in fixups)Buffer.BlockCopy(BitConverter.GetBytes(labels[f.Value]-f.Key-4),0,b,f.Key,4);return b;}
 }
 static void Need(bool b,string message){if(!b)throw new InvalidOperationException(message);}
 static byte[] Read(IntPtr h,long a,int n){var b=new byte[n];UIntPtr done;Need(ReadProcessMemory(h,new IntPtr(a),b,(UIntPtr)n,out done)&&done.ToUInt64()==(ulong)n,"Read failed: "+new Win32Exception().Message);return b;}
 static long Ptr(IntPtr h,long a){return BitConverter.ToInt64(Read(h,a,8),0);}
 static void Write(IntPtr h,long a,byte[] b){UIntPtr done;Need(WriteProcessMemory(h,new IntPtr(a),b,(UIntPtr)b.Length,out done)&&done.ToUInt64()==(ulong)b.Length,"Write failed: "+new Win32Exception().Message);}
 static long Alloc(IntPtr h){long a=VirtualAllocEx(h,IntPtr.Zero,(UIntPtr)12288,0x3000,4).ToInt64();Need(a!=0,"Allocation failed");return a;}
 static byte[] SmallString(string text){byte[] raw=Encoding.UTF8.GetBytes(text);Need(raw.Length<15,"Label exceeds native inline capacity");byte[] b=new byte[16];Buffer.BlockCopy(raw,0,b,0,raw.Length);b[15]=(byte)(15-raw.Length);return b;}
 static byte[] Hook(long original,long counters,long assign,long labels){
  var a=new Asm();a.E(0x4d,0x85,0xc0);a.J("fallback",0x0f,0x84); // null key
  a.E(0x48,0x85,0xd2);a.J("fallback",0x0f,0x84); // null result
  int serial=0;
  for(int i=0;i<Ids.Length;i++)foreach(string prefix in new[]{"Player_Rarity_","PLAYER_RARITY_","FUT_POA_PLAYER_RARITY_"}){
   string key=prefix+Ids[i], next="next"+(serial++);byte[] k=Encoding.ASCII.GetBytes(key+"\0");
   for(int n=0;n<k.Length;n++){a.E(0x41,0x80,0x78,(byte)n,k[n]);a.J(next,0x0f,0x85);} // cmp byte [r8+n],imm8
   string text=prefix.StartsWith("FUT_POA")?Names[i].ToUpperInvariant():Names[i];
   long label=labels+i*64+(prefix.StartsWith("FUT_POA")?32:0);
   a.E(0x49,0xba);a.I64(counters+i*8);a.E(0xf0,0x49,0xff,0x02);
   // Use FIFA's own string assignment so allocator ownership stays native.
   a.E(0x48,0x83,0xec,0x28,0x48,0x89,0xd1); // shadow space, rcx=result
   a.E(0x48,0xba);a.I64(label);
   a.E(0x49,0xb8);a.I64(label+Encoding.UTF8.GetByteCount(text));
   a.E(0x48,0xb8);a.I64(assign);a.E(0xff,0xd0);
   a.E(0xb8,1,0,0,0,0x48,0x83,0xc4,0x28,0xc3);a.L(next);
  }
  a.L("fallback");a.E(0xff,0x25,0,0,0,0);a.I64(original);return a.Finish();
 }
 static void Labels(IntPtr h,long address){for(int i=0;i<Ids.Length;i++){Write(h,address+i*64,Encoding.UTF8.GetBytes(Names[i]+"\0"));Write(h,address+i*64+32,Encoding.UTF8.GetBytes(Names[i].ToUpperInvariant()+"\0"));}}
 static void SelfTest(){
  Need(Environment.Is64BitProcess,"x64 required");var h=GetCurrentProcess();long mem=Alloc(h);IntPtr output=Marshal.AllocHGlobal(16);
  try{
   AssignText assign=(o,first,last)=>{int n=checked((int)(last.ToInt64()-first.ToInt64()));var raw=new byte[n];Marshal.Copy(first,raw,0,n);byte[] result=SmallString(Encoding.UTF8.GetString(raw));Marshal.Copy(result,0,o,16);return o;};
   Labels(h,mem+DataOffset+256);
   byte[] code=Hook(mem+0x1f00,mem+DataOffset+128,Marshal.GetFunctionPointerForDelegate(assign).ToInt64(),mem+DataOffset+256);Need(code.Length<0x1e00,"Hook too large");Write(h,mem+EntryOffset,code);Write(h,mem+0x1f00,new byte[]{0xb8,0x34,0x12,0,0,0xc3});uint old;Need(VirtualProtectEx(h,new IntPtr(mem),(UIntPtr)8192,0x20,out old),"RX protection failed");FlushInstructionCache(h,new IntPtr(mem),(UIntPtr)8192);
   var call=(Translate)Marshal.GetDelegateForFunctionPointer(new IntPtr(mem+EntryOffset),typeof(Translate));
   for(int i=0;i<Ids.Length;i++)foreach(string prefix in new[]{"Player_Rarity_","PLAYER_RARITY_","FUT_POA_PLAYER_RARITY_"}){
    string key=prefix+Ids[i];IntPtr text=Marshal.StringToHGlobalAnsi(key);
    try{Need(call(IntPtr.Zero,output,text,1)==1,"Native result ABI");byte[] b=new byte[16];Marshal.Copy(output,b,0,16);string expected=prefix.StartsWith("FUT_POA")?Names[i].ToUpperInvariant():Names[i];Need(b.SequenceEqual(SmallString(expected)),"Inline text layout mismatch");}
    finally{Marshal.FreeHGlobal(text);}
   }
   foreach(string key in new[]{"Player_Rarity_1","Player_Rarity_220","Player_Rarity_22_extra","Other",""}){IntPtr t=Marshal.StringToHGlobalAnsi(key);try{Need(call(IntPtr.Zero,output,t,1)==0x1234,"Unrelated text intercepted");}finally{Marshal.FreeHGlobal(t);}}
   Need(call(IntPtr.Zero,output,IntPtr.Zero,1)==0x1234,"Null key fallback");
   IntPtr probe=Marshal.StringToHGlobalAnsi("Player_Rarity_22");try{Need(call(IntPtr.Zero,IntPtr.Zero,probe,1)==0x1234,"Null result fallback");}finally{Marshal.FreeHGlobal(probe);}
   for(int i=0;i<Ids.Length;i++)Need(Ptr(h,mem+DataOffset+128+i*8)==3,"Counter mismatch");
   GC.KeepAlive(assign);Console.WriteLine("PASS x64 native-assignment ABI, all rarity keys, exact match, nulls, original fallback, hit counters. No FIFA process touched.");
  }finally{Marshal.FreeHGlobal(output);VirtualFreeEx(h,new IntPtr(mem),UIntPtr.Zero,0x8000);}
 }
 static void Run(int pid,string mode){
  using(var p=Process.GetProcessById(pid)){
   Need(p.ProcessName=="FIFA21"||p.ProcessName=="FIFA21_Trial","Not a FIFA21 process");
   var module=p.Modules.Cast<ProcessModule>().SingleOrDefault(m=>m.ModuleName.Equals("CardsDLL_Win64_retail.dll",StringComparison.OrdinalIgnoreCase));Need(module!=null,"Localization service not ready");long b=module.BaseAddress.ToInt64();
   IntPtr h=OpenProcess(mode=="probe"?0x410u:0x1f0fffu,false,pid);Need(h!=IntPtr.Zero,"OpenProcess failed: "+new Win32Exception().Message);
   try{
    Need(Read(h,b+0x119b0a,7).SequenceEqual(new byte[]{0x48,0x8d,0x15,0x4f,0xa2,0x34,0}),"Unsupported CardsDLL lookup signature");
    long service=Ptr(h,b+GlobalRva);Need(service>0,"Localization service not ready");long vtable=Ptr(h,service),slot=vtable+0x1d0,original=Ptr(h,slot);
    Console.WriteLine("pid="+pid+" module="+b.ToString("x")+" service="+service.ToString("x")+" vtable="+vtable.ToString("x")+" slot="+slot.ToString("x")+" method="+original.ToString("x"));
    var owner=p.Modules.Cast<ProcessModule>().FirstOrDefault(m=>original>=m.BaseAddress.ToInt64()&&original<m.BaseAddress.ToInt64()+m.ModuleMemorySize);
    Console.WriteLine("Method owner="+(owner==null?"private":owner.ModuleName+" RVA="+(original-owner.BaseAddress.ToInt64()).ToString("x")));
    if(mode=="probe") {File.WriteAllBytes(Path.Combine(AppDomain.CurrentDomain.BaseDirectory,"rarity-localize-method.bin"),Read(h,original,2048));return;}
    if(Read(h,original-EntryOffset,Magic.Length).SequenceEqual(Magic)){
     Console.WriteLine("[ALREADY] Rarity names installed; hits="+string.Join(",",Enumerable.Range(0,Ids.Length).Select(i=>Ptr(h,original-EntryOffset+DataOffset+128+i*8).ToString()).ToArray()));return;
    }
    Need(owner!=null,"Localization method owner is unknown; no patch installed");
    Need(mode=="install","Unknown mode");long mem=Alloc(h);bool installed=false;
    try{
     long imageBase=p.MainModule.BaseAddress.ToInt64(),assign=imageBase+0x95b390;
     Need(owner.ModuleName.Equals("FIFA21.exe",StringComparison.OrdinalIgnoreCase)&&original==imageBase+0xe43ab0,"Unsupported native localization implementation");
     Need(Read(h,assign,16).SequenceEqual(new byte[]{0x48,0x89,0x5c,0x24,0x08,0x48,0x89,0x6c,0x24,0x10,0x48,0x89,0x74,0x24,0x18,0x57}),"Unsupported native string assignment");
     Labels(h,mem+DataOffset+256);
     byte[] code=Hook(original,mem+DataOffset+128,assign,mem+DataOffset+256);Need(code.Length<0x1e00,"Hook exceeds page");Write(h,mem,Magic);Write(h,mem+EntryOffset,code);Write(h,mem+DataOffset,BitConverter.GetBytes(original));uint ignored;Need(VirtualProtectEx(h,new IntPtr(mem),(UIntPtr)8192,0x20,out ignored),"RX protection failed");FlushInstructionCache(h,new IntPtr(mem),(UIntPtr)8192);
     Need(NtSuspendProcess(h)==0,"Could not suspend briefly for atomic installation");
     uint prior=0;bool writable=false;
     try{
      Need(Ptr(h,slot)==original,"Localization method changed during preparation");Need(VirtualProtectEx(h,new IntPtr(slot),(UIntPtr)8,4,out prior),"Slot protection failed");writable=true;
      try{Write(h,slot,BitConverter.GetBytes(mem+EntryOffset));Need(Ptr(h,slot)==mem+EntryOffset,"Readback failed");installed=true;}
      catch{Write(h,slot,BitConverter.GetBytes(original));throw;}
     }finally{if(writable)VirtualProtectEx(h,new IntPtr(slot),(UIntPtr)8,prior,out ignored);NtResumeProcess(h);}
     Console.WriteLine("[READY] Custom rarity names installed in current FIFA process only. No game files modified.");
    }finally{if(!installed)VirtualFreeEx(h,new IntPtr(mem),UIntPtr.Zero,0x8000);}
   }finally{CloseHandle(h);}
  }
 }
 static int Main(string[] args){
  StreamWriter log=null;
  try{
   int li=Array.IndexOf(args,"--log");
   if(li>=0){Need(li+1<args.Length,"Missing log path");log=new StreamWriter(args[li+1],false,Encoding.UTF8);log.AutoFlush=true;Console.SetOut(log);Console.SetError(log);}
   if(args.Contains("--self-test")){SelfTest();return 0;}
   int pi=Array.IndexOf(args,"--pid");Need(pi>=0&&pi+1<args.Length,"Missing PID");int pid=int.Parse(args[pi+1]);string mode=args[0].TrimStart('-');
   bool wait=args.Contains("--wait");
   while(true){try{Run(pid,mode);return 0;}catch(InvalidOperationException e){if(e.Message!="Localization service not ready"||!wait)throw;
    using(var game=Process.GetProcessById(pid)){if(game.HasExited)return 0;}
    Thread.Sleep(1000);}}
  }catch(Exception e){Console.Error.WriteLine(e);return 1;}finally{if(log!=null)log.Dispose();}
 }
}

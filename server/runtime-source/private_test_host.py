"""Run one private hosting trial club on this PC's verified Tailscale address."""
import argparse
import _thread
import threading
import time
import json
import os
from pathlib import Path
import runpy
import sys

RUNTIME = Path(__file__).resolve().parent
sys.path.insert(0, str(RUNTIME))
from remote_relay import tailnet


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--stop-file", required=True)
    args = parser.parse_args()
    stop = Path(args.stop_file)
    def watch():
        while not stop.exists():
            time.sleep(.5)
        _thread.interrupt_main()
    threading.Thread(target=watch, daemon=True).start()
    status = tailnet()
    addresses = (status.get("Self") or {}).get("TailscaleIPs", [])
    host = next((address for address in addresses if ":" not in address), None)
    if not host:
        raise RuntimeError("No private IPv4 address available")
    data = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "MNG21/HostingTest21"
    config = data / "config"
    config.mkdir(parents=True, exist_ok=True)
    file = config / "config.json"
    if not file.exists():
        with file.open("x", encoding="utf-8") as output:
            json.dump({"display_name": "MinegTest", "club_name": "MNG Test", "club_abbr": "MNG"}, output)
    os.environ["LOCALFUT_RUNTIME_ROOT"] = str(data / "runtime")
    os.environ["LOCALFUT21_USER_CONFIG_ROOT"] = str(config)
    os.environ["LOCALAPPDATA"] = str(data / "cache")
    print("Private trial server:", host, flush=True)
    print("Separate trial club:", data, flush=True)
    script = RUNTIME / "localfut21/server.py"
    sys.path.insert(0, str(script.parent))
    sys.argv = [str(script), "--host", host, "--lsx-mode", "off"]
    runpy.run_path(str(script), run_name="__main__")


if __name__ == "__main__":
    main()

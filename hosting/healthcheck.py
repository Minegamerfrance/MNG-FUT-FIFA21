"""Check the backend without reading or changing club inventory."""
import json
import socket
import urllib.request


def check(host="127.0.0.1"):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(f"http://{host}:8090/localfut/auth/bootstrap", timeout=2) as response:
        profile = json.load(response)
    if profile.get("version") != 1:
        raise RuntimeError("Unexpected FUT authentication profile")
    for port in (44321, 10853, 17502):
        with socket.create_connection((host, port), timeout=1):
            pass


if __name__ == "__main__":
    check()
    print("FUT, Blaze, SSF and QoS reachable")

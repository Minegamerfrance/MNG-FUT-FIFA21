"""Start only temporary club backends; never access the player's saved club."""
from pathlib import Path
from contextlib import closing
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import time

from healthcheck import check


def main():
    repo = Path(__file__).resolve().parents[1]
    host = "127.77.0.21"
    with tempfile.TemporaryDirectory(prefix="mng21-hosting-test-") as temporary:
        root = Path(temporary)
        env = dict(os.environ, LOCALFUT_RUNTIME_ROOT=str(root / "runtime"),
                   LOCALFUT21_USER_CONFIG_ROOT=str(root / "config"),
                   LOCALAPPDATA=str(root / "cache"), PYTHONDONTWRITEBYTECODE="1")
        db = root / "runtime/data/localfut15.sqlite3"
        for attempt in range(2):
            with (root / "server.log").open("w", encoding="utf-8") as log:
                process = subprocess.Popen(
                    [sys.executable, "-u", str(repo / "server/runtime-source/localfut21/server.py"),
                     "--host", host, "--lsx-mode", "off"], env=env,
                    stdout=log, stderr=subprocess.STDOUT)
                try:
                    deadline = time.monotonic() + 40
                    while True:
                        if process.poll() is not None:
                            raise RuntimeError((root / "server.log").read_text(encoding="utf-8")[-3000:])
                        try:
                            check(host)
                            break
                        except (OSError, ValueError):
                            if time.monotonic() >= deadline:
                                raise
                            time.sleep(0.3)
                    assert db.is_file()
                finally:
                    process.terminate()
                    process.wait(timeout=10)
            with closing(sqlite3.connect(db)) as connection:
                if attempt == 0:
                    connection.execute("INSERT INTO kv(key,value) VALUES(?,?)",
                                       ("hosting_persistence_test", json.dumps("saved")))
                    connection.commit()
                else:
                    value = connection.execute("SELECT value FROM kv WHERE key=?",
                                               ("hosting_persistence_test",)).fetchone()
                    assert value and json.loads(value[0]) == "saved"
                assert connection.execute("PRAGMA quick_check").fetchone()[0] == "ok"
        print("PASS: isolated backend startup, FUT/Blaze/SSF/QoS-TCP readiness, restart, SQLite persistence")
        print("No personal club, running FIFA process or public network setting changed")


if __name__ == "__main__":
    main()

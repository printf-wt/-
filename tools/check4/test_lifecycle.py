"""Exercise real collector interruption on loopback in Ubuntu; no experiment data is synthesized."""

import json, os, re, signal, subprocess, sys, tempfile, time
from pathlib import Path

def main():
    if sys.platform != "linux":
        raise SystemExit("Run this lifecycle check inside Ubuntu/WSL.")
    collector=Path("tools/check4/collect.py").resolve()
    for mode, expected in [("child", "ended_early"), ("parent", "interrupted")]:
        with tempfile.TemporaryDirectory(prefix="check4-lifecycle-") as directory:
            proc=subprocess.Popen([sys.executable,str(collector),"127.0.0.1","--duration","30","--output",directory],stdout=subprocess.PIPE,text=True)
            try:
                line=proc.stdout.readline()
                child=int(re.search(r"PID (\d+)",line).group(1))
                time.sleep(0.5)
                target=child if mode=="child" else proc.pid
                if mode=="child":
                    status=Path(f"/proc/{child}/status").read_text()
                    assert int(re.search(r"PPid:\s*(\d+)",status).group(1))==proc.pid
                os.kill(target,signal.SIGINT)
                proc.communicate(timeout=8)
                meta=json.loads((Path(directory)/"metadata.json").read_text())
                assert meta["state"]==expected and proc.returncode==1,meta
                print(f"[PASS] {mode} signal -> {expected}; incomplete session cannot count as finished")
            finally:
                if proc.poll() is None:
                    proc.send_signal(signal.SIGINT)
                    proc.communicate(timeout=8)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Foreground recorder owned by the Wayfire Quickshell session."""

import argparse
from contextlib import ExitStack
from datetime import datetime
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time

from wayfire import IpcError, Wayfire, select_view, snapshot


def output(*args: str) -> str:
    return subprocess.check_output(args, text=True).strip()


def shell_call(*args: str) -> None:
    subprocess.run(["qs", "ipc", "call", "Argus", *args], check=True, stdout=subprocess.DEVNULL)


def finish(child: subprocess.Popen) -> None:
    if child.poll() is not None:
        return
    child.send_signal(signal.SIGINT)
    try:
        child.wait(timeout=10)
    except subprocess.TimeoutExpired:
        child.kill()
        child.wait()
        raise RuntimeError("wf-recorder did not finalize within 10 seconds")


def record(mode: str) -> int:
    child: subprocess.Popen | None = None

    def stop(signum, frame) -> None:
        if child is None:
            raise KeyboardInterrupt
        child.send_signal(signal.SIGINT)

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    for dependency in ("wf-recorder", "qs", "xdg-user-dir", "notify-send"):
        if not shutil.which(dependency):
            raise FileNotFoundError(f"Install {dependency} to record")
    ipc = Wayfire()
    try:
        state = snapshot(ipc)
    finally:
        ipc.close()
    monitor = next(m for m in state["monitors"] if m["id"] == state["focusedOutput"])
    args = ["wf-recorder", "-D", "-r", "60", "-o", monitor["name"]]
    if mode == "region":
        args += ["-g", output("slurp")]
    elif mode == "window":
        window = select_view(state)
        x, y = window["at"]
        width, height = window["size"]
        args += ["-g", f"{int(x)},{int(y)} {int(width)}x{int(height)}"]
    preferences = dict(word.split("=", 1) for word in output("qs", "ipc", "call", "Argus", "recPrefs").split() if "=" in word)
    videos = output("xdg-user-dir", "VIDEOS")
    directory = (Path(videos) if videos and videos != os.environ["HOME"] else Path.home() / "Videos") / "Captures"
    directory.mkdir(parents=True, exist_ok=True)
    destination = directory / (datetime.now().strftime("%Y-%m-%d-%H%M%S-%f") + ".mp4")
    with ExitStack() as cleanup:
        cleanup.callback(shell_call, "recording", "false")
        cleanup.callback((directory / ".active-recording").unlink, missing_ok=True)
        audio = preferences.get("audio", "system")
        if audio != "none" and not shutil.which("pactl"):
            raise FileNotFoundError("Install pactl to record audio")
        source = ""
        if audio in ("system", "both"):
            source = output("pactl", "get-default-sink") + ".monitor"
        if audio == "mic":
            source = output("pactl", "get-default-source")
        if audio == "both":
            sink = "zenworks_wayfire_" + str(os.getpid())
            module = output("pactl", "load-module", "module-null-sink", "sink_name=" + sink)
            cleanup.callback(subprocess.run, ["pactl", "unload-module", module], check=True)
            for input_source in (source, output("pactl", "get-default-source")):
                module = output("pactl", "load-module", "module-loopback", "source=" + input_source, "sink=" + sink, "latency_msec=30")
                cleanup.callback(subprocess.run, ["pactl", "unload-module", module], check=True)
            source = sink + ".monitor"
        if source:
            args.append("--audio=" + source)
        countdown = max(0, min(10, int(preferences.get("countdown", "0"))))
        if countdown:
            shell_call("countdown", str(countdown))
            time.sleep(countdown)
        args += ["-f", str(destination)]
        child = subprocess.Popen(args)
        cleanup.callback(finish, child)
        (directory / ".active-recording").write_text(str(destination))
        shell_call("recording", "true")
        code = child.wait()
        if code not in (0, -signal.SIGINT):
            raise RuntimeError(f"wf-recorder exited with status {code}")
        subprocess.run(["notify-send", "-a", "Argus", "-h", "string:x-howler-capture:video",
                        "-h", f"string:x-howler-file:{destination}", "Recording saved", str(destination)], check=True)
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("screen", "region", "window"))
    args = parser.parse_args()
    try:
        return record(args.mode)
    except KeyboardInterrupt:
        return 0
    except (IpcError, OSError, ValueError, RuntimeError, StopIteration, subprocess.SubprocessError) as error:
        print(f"zenworks-wayfire recording: {error}", file=sys.stderr)
        if shutil.which("notify-send"):
            subprocess.run(["notify-send", "-a", "Argus", "Recording failed", str(error)], check=False)
        return 1


if __name__ == "__main__":
    sys.exit(main())

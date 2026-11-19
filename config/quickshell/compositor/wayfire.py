#!/usr/bin/env python3
"""Wayfire IPC transport and the shell's compositor-neutral command adapter."""

import argparse
import json
import os
import re
import select
import socket
import struct
import subprocess
import sys
import time


class IpcError(RuntimeError):
    pass


class Wayfire:
    def __init__(self, path: str | None = None) -> None:
        self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.socket.settimeout(3)
        address = path or os.environ.get("WAYFIRE_SOCKET")
        if not address:
            raise IpcError("WAYFIRE_SOCKET is unset; enable the ipc and ipc-rules plugins")
        self.socket.connect(address)

    def close(self) -> None:
        self.socket.close()

    def read_exact(self, size: int) -> bytes:
        chunks = bytearray()
        while len(chunks) < size:
            chunk = self.socket.recv(size - len(chunks))
            if not chunk:
                raise IpcError("Wayfire closed its IPC connection")
            chunks.extend(chunk)
        return bytes(chunks)

    def receive(self):
        size = struct.unpack("<I", self.read_exact(4))[0]
        if not 0 < size <= 16 * 1024 * 1024:
            raise IpcError(f"Invalid Wayfire message size: {size}")
        return json.loads(self.read_exact(size))

    def call(self, method: str, data: dict | None = None):
        message = json.dumps({"method": method, "data": data or {}}).encode()
        self.socket.sendall(struct.pack("<I", len(message)) + message)
        reply = self.receive()
        while isinstance(reply, dict) and "event" in reply:
            reply = self.receive()
        if isinstance(reply, dict) and "error" in reply:
            raise IpcError(f"{method}: {reply['error']}")
        return reply


def snapshot(ipc: Wayfire) -> dict:
    outputs = ipc.call("window-rules/list-outputs")
    views = ipc.call("window-rules/list-views")
    focused_output = ipc.call("window-rules/get-focused-output").get("info")
    focused_view = ipc.call("window-rules/get-focused-view").get("info")
    monitors, workspaces, clients = [], [], []
    for output in outputs:
        geometry = output["geometry"]
        workarea = output["workarea"]
        workspace = output["workspace"]
        width, height = workspace["grid_width"], workspace["grid_height"]
        active_id = workspace["y"] * width + workspace["x"] + 1
        monitors.append({
            "id": output["id"], "name": output["name"],
            "x": geometry["x"], "y": geometry["y"],
            "width": geometry["width"], "height": geometry["height"],
            "scale": output.get("scale", 1), "transform": 0,
            "focused": bool(focused_output and output["id"] == focused_output["id"]),
            "reserved": [workarea["x"], workarea["y"],
                         geometry["width"] - workarea["x"] - workarea["width"],
                         geometry["height"] - workarea["y"] - workarea["height"]],
            "activeWorkspace": {"id": active_id, "name": str(active_id), "address": f"wf:{output['id']}:{active_id}"},
            "specialWorkspace": {"id": 0, "name": ""},
        })
        for y in range(height):
            for x in range(width):
                number = y * width + x + 1
                workspaces.append({
                    "id": number, "name": str(number), "monitorID": output["id"],
                    "address": f"wf:{output['id']}:{number}",
                    "x": x, "y": y, "active": number == active_id,
                    "focused": bool(focused_output and focused_output["id"] == output["id"] and number == active_id),
                    "urgent": False, "lastIpcObject": {},
                })
    for view in views:
        if not view.get("mapped") or view.get("role") != "toplevel":
            continue
        output = next((o for o in outputs if o["id"] == view["output-id"]), None)
        if output is None:
            continue
        geometry = view["geometry"]
        current = output["workspace"]
        # Wayfire view geometry is relative to the output's active workspace.
        center_x = geometry["x"] + geometry["width"] // 2
        center_y = geometry["y"] + geometry["height"] // 2
        x = int(current["x"] + center_x // output["geometry"]["width"])
        y = int(current["y"] + center_y // output["geometry"]["height"])
        number = y * current["grid_width"] + x + 1
        address = format(view["id"], "x")
        client = {
            "id": view["id"], "address": address, "title": view["title"],
            "class": view["app-id"], "initialClass": view["app-id"],
            "initialTitle": view["title"], "pid": view.get("pid", -1),
            "monitor": view["output-id"], "mapped": True, "hidden": False,
            "workspace": {"id": number, "name": str(number), "address": f"wf:{output['id']}:{number}"},
            "at": [int(geometry["x"] + output["geometry"]["x"]), int(geometry["y"] + output["geometry"]["y"])],
            "size": [int(geometry["width"]), int(geometry["height"])],
            "floating": view.get("tiled-edges", 0) == 0,
            "fullscreen": bool(view.get("fullscreen")),
            "urgent": bool(view.get("attention", False)), "focusHistoryID": 0,
        }
        client["lastIpcObject"] = dict(client)
        clients.append(client)
    return {
        "monitors": monitors, "workspaces": workspaces, "clients": clients,
        "focusedOutput": focused_output["id"] if focused_output else -1,
        "focusedView": focused_view["id"] if focused_view else -1,
    }


def select_view(state: dict, selector: str | None = None) -> dict:
    if not selector:
        match = next((c for c in state["clients"] if c["id"] == state["focusedView"]), None)
    elif selector.startswith("address:0x"):
        match = next((c for c in state["clients"] if c["id"] == int(selector[10:], 16)), None)
    elif selector.startswith("title:"):
        match = next((c for c in state["clients"] if re.search(selector[6:], c["title"])), None)
    elif selector.startswith("class:"):
        pattern = selector[6:].replace("(?i)", "")
        match = next((c for c in state["clients"] if re.search(pattern, c["class"], re.IGNORECASE)), None)
    else:
        raise ValueError(f"Unsupported window selector: {selector}")
    if match is None:
        raise ValueError("The requested window is no longer mapped")
    return match


def workspace_target(state: dict, name: str) -> dict:
    spaces = [w for w in state["workspaces"] if w["monitorID"] == state["focusedOutput"]]
    if name == "empty":
        target = next((w for w in spaces if not any(
            c["monitor"] == w["monitorID"] and c["workspace"]["id"] == w["id"]
            for c in state["clients"])), None)
    else:
        target = next((w for w in spaces if w["name"] == str(name)), None)
    if target is None:
        raise ValueError(f"No available Wayfire workspace: {name}")
    return target


def dispatch(ipc: Wayfire, command: dict, state: dict | None = None) -> None:
    op, args = command["op"], command.get("args", [])
    if op in ("toggleSpecial", "submap", "tagWindow", "execWith", "placeWindow"):
        raise ValueError(f"{op} is Hyprland-only; use Wayfire overview, shortcuts and startup configuration")
    if op == "dpms":
        subprocess.run(["wlopm", "--on" if args[0] else "--off", "*"], check=True)
        return
    state = snapshot(ipc) if state is None else state
    if op in ("focusWorkspace", "focusNamedWorkspace", "moveToWorkspace"):
        target = workspace_target(state, args[0])
        payload = {"x": target["x"], "y": target["y"], "output-id": target["monitorID"]}
        if op == "moveToWorkspace":
            view = select_view(state)
            payload["view-id"] = view["id"]
            view["workspace"] = target
        ipc.call("vswitch/set-workspace", payload)
        return
    if op == "focusTitle":
        selector = "title:^" + re.escape(args[0]) + "$"
    else:
        selector = args[0] if op in ("focusWindow", "raiseWindow", "closeWindow") else (
            args[2] if op in ("resizeBy", "resizeTo", "moveBy", "moveTo") and len(args) > 2 else None)
    view = select_view(state, selector)
    if op in ("focusWindow", "focusTitle"):
        ipc.call("window-rules/focus-view", {"id": view["id"]})
        state["focusedView"], state["focusedOutput"] = view["id"], view["monitor"]
    elif op == "raiseWindow":
        ipc.call("wm-actions/bring-to-front", {"view_id": view["id"], "state": True})
    elif op == "closeWindow":
        ipc.call("window-rules/close-view", {"id": view["id"]})
    elif op == "fullscreen":
        ipc.call("wm-actions/set-fullscreen", {"view_id": view["id"], "state": not view["fullscreen"]})
        view["fullscreen"] = not view["fullscreen"]
    elif op in ("floatOn", "floatOff", "floatToggle"):
        floating = op == "floatOn" or (op == "floatToggle" and not view["floating"])
        if floating != view["floating"]:
            raise ValueError("Use Super+F to toggle native Wayfire tiling; programmatic retiling is unsafe on Wayfire 0.11")
    elif op == "moveToMonitor":
        monitors = state["monitors"]
        name = str(args[0])
        if name.startswith(("+", "-")):
            index = next(i for i, monitor in enumerate(monitors) if monitor["id"] == view["monitor"])
            target = monitors[(index + int(name)) % len(monitors)]
        else:
            target = next((m for m in monitors if name in (m["name"], str(m["id"]))), None)
            if target is None:
                raise ValueError(f"No Wayfire output: {name}")
        ipc.call("window-rules/configure-view", {"id": view["id"], "output_id": target["id"]})
        view["monitor"] = target["id"]
    elif op in ("resizeBy", "resizeTo", "moveBy", "moveTo", "center"):
        output = next(m for m in state["monitors"] if m["id"] == view["monitor"])
        x, y = view["at"][0] - output["x"], view["at"][1] - output["y"]
        width, height = view["size"]
        if op == "resizeBy":
            width, height = width + args[0], height + args[1]
        elif op == "resizeTo":
            width, height = args[:2]
        elif op == "moveBy":
            x, y = x + args[0], y + args[1]
        elif op == "moveTo":
            x, y = args[0] - output["x"], args[1] - output["y"]
        else:
            x, y = (output["width"] - width) // 2, (output["height"] - height) // 2
        ipc.call("window-rules/configure-view", {
            "id": view["id"], "geometry": {"x": x, "y": y, "width": max(1, width), "height": max(1, height)}})
        view["at"], view["size"] = [x + output["x"], y + output["y"]], [max(1, width), max(1, height)]
    else:
        raise ValueError(f"{op} is not available on Wayfire; use the native Wayfire bindings")


def query(ipc: Wayfire, args: list[str]):
    query_args = [a for a in args if a not in ("-j", "-q", "all")]
    name = query_args[0]
    if name == "cursorpos":
        position = ipc.call("window-rules/get_cursor_position")["pos"]
        return f"{int(position['x'])}, {int(position['y'])}"
    state = snapshot(ipc)
    clients = [dict(c, address="0x" + c["address"]) for c in state["clients"]]
    active = next((c for c in clients if c["id"] == state["focusedView"]), {})
    workspace = next((w for w in state["workspaces"] if w["focused"]), {})
    if name == "clients":
        return clients
    if name == "monitors":
        return state["monitors"]
    if name == "activewindow":
        return active
    if name == "activeworkspace":
        return workspace
    if name == "capture":
        return "@@".join(json.dumps(value) for value in (state["monitors"], clients, active, []))
    if name == "room":
        return json.dumps(active) + "@@mons" + json.dumps(state["monitors"])
    if name == "snap":
        return "\x1e".join(json.dumps(value) for value in (state["monitors"], clients, {"int": 8}))
    if name == "layout":
        return json.dumps(clients) + "\x1e" + json.dumps(workspace)
    raise ValueError(f"{name} has no Wayfire equivalent")


def watch(ipc: Wayfire) -> None:
    events = Wayfire()
    try:
        events.call("window-rules/events/watch")
        while True:
            print(json.dumps(snapshot(ipc)), flush=True)
            select.select([events.socket], [], [])
            events.receive()
            deadline = time.monotonic() + 0.05
            while time.monotonic() < deadline and select.select([events.socket], [], [], 0.01)[0]:
                events.receive()
    finally:
        events.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("watch", "query", "dispatch", "sequence", "call"))
    parser.add_argument("arguments", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    ipc = None
    try:
        ipc = Wayfire()
        if args.action == "watch":
            watch(ipc)
        elif args.action == "query":
            result = query(ipc, args.arguments)
            print(result if isinstance(result, str) else json.dumps(result))
        elif args.action == "call":
            print(json.dumps(ipc.call(args.arguments[0], json.loads(args.arguments[1]) if len(args.arguments) > 1 else {})))
        elif args.action == "sequence":
            state = snapshot(ipc)
            for command in json.loads(args.arguments[0]):
                dispatch(ipc, command, state)
        else:
            dispatch(ipc, json.loads(args.arguments[0]))
    except (IpcError, OSError, ValueError, KeyError, IndexError, subprocess.CalledProcessError) as error:
        print(f"zenworks-wayfire: {error}", file=sys.stderr)
        if args.action in ("dispatch", "sequence"):
            subprocess.run(["notify-send", "-a", "Zenworks", "Wayfire command failed", str(error)], check=False)
        return 1
    finally:
        if ipc:
            ipc.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())

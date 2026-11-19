#!/usr/bin/env python3
"""Backend and non-destructive launcher checks; no compositor is required."""

import importlib.util
import json
import os
from pathlib import Path
import socket
import struct
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[4]
SPEC = importlib.util.spec_from_file_location("wayfire_backend", ROOT / "config/quickshell/compositor/wayfire.py")
backend = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(backend)
sys.modules["wayfire"] = backend
RECORD_SPEC = importlib.util.spec_from_file_location("wayfire_recorder", ROOT / "config/quickshell/compositor/record.py")
recorder = importlib.util.module_from_spec(RECORD_SPEC)
RECORD_SPEC.loader.exec_module(recorder)


class FakeWayfire:
    def __init__(self) -> None:
        self.calls = []
        self.outputs = [{
            "id": 4, "name": "DP-1", "wset-index": 1,
            "geometry": {"x": 1920.0, "y": 0.0, "width": 1280.0, "height": 720.0},
            "workarea": {"x": 0.0, "y": 0.0, "width": 1280.0, "height": 676.0},
            "workspace": {"x": 1, "y": 0, "grid_width": 5, "grid_height": 1},
        }]
        self.views = [{
            "id": 42, "title": 'a "quoted" title', "app-id": "org.quickshell",
            "pid": 100, "mapped": True, "role": "toplevel", "output-id": 4,
            "geometry": {"x": -1200.0, "y": 20.0, "width": 600.0, "height": 400.0},
            "tiled-edges": 0, "fullscreen": False,
        }]

    def call(self, method, data=None):
        self.calls.append((method, data))
        if method == "window-rules/list-outputs":
            return self.outputs
        if method == "window-rules/list-views":
            return self.views
        if method == "window-rules/get-focused-output":
            return {"info": self.outputs[0]}
        if method == "window-rules/get-focused-view":
            return {"info": self.views[0] if self.views else None}
        if method == "window-rules/get_cursor_position":
            return {"result": "ok", "pos": {"x": 2020.0, "y": 40.0}}
        return {"result": "ok"}


class BackendTests(unittest.TestCase):
    def test_workspace_geometry_and_capture_identity(self):
        state = backend.snapshot(FakeWayfire())
        window = state["clients"][0]
        self.assertEqual(window["workspace"]["name"], "1")
        self.assertEqual(window["at"], [720, 20])
        self.assertEqual(window["workspace"]["address"], state["workspaces"][0]["address"])
        self.assertEqual(state["monitors"][0]["activeWorkspace"]["address"], "wf:4:2")
        self.assertEqual(state["monitors"][0]["reserved"], [0, 0, 0, 44])
        self.assertEqual(window["address"], "2a")
        self.assertIsInstance(window["workspace"]["id"], int)

    def test_layers_and_unmapped_views_are_not_app_windows(self):
        ipc = FakeWayfire()
        ipc.views += [dict(ipc.views[0], role="desktop-environment"), dict(ipc.views[0], mapped=False)]
        self.assertEqual(len(backend.snapshot(ipc)["clients"]), 1)

    def test_output_workspaces_have_distinct_capture_addresses(self):
        ipc = FakeWayfire()
        ipc.outputs.append(dict(ipc.outputs[0], id=7, name="DP-2"))
        spaces = backend.snapshot(ipc)["workspaces"]
        self.assertEqual(len({w["address"] for w in spaces}), 10)

    def test_exact_address_and_escaped_title_selectors(self):
        state = backend.snapshot(FakeWayfire())
        self.assertEqual(backend.select_view(state, "address:0x2a")["id"], 42)
        self.assertEqual(backend.select_view(state, 'title:^(a "quoted" title)$')["id"], 42)
        with self.assertRaises(ValueError):
            backend.select_view(state, "address:0x2b")

    def test_native_focus_close_and_workspace_requests(self):
        ipc = FakeWayfire()
        backend.dispatch(ipc, {"op": "focusWindow", "args": ["address:0x2a"]})
        self.assertEqual(ipc.calls[-1], ("window-rules/focus-view", {"id": 42}))
        backend.dispatch(ipc, {"op": "closeWindow", "args": ["address:0x2a"]})
        self.assertEqual(ipc.calls[-1], ("window-rules/close-view", {"id": 42}))
        backend.dispatch(ipc, {"op": "focusWorkspace", "args": ["5"]})
        self.assertEqual(ipc.calls[-1], ("vswitch/set-workspace", {"x": 4, "y": 0, "output-id": 4}))
        with self.assertRaises(ValueError):
            backend.dispatch(ipc, {"op": "focusWorkspace", "args": ["6"]})

    def test_move_to_workspace_includes_the_view(self):
        ipc = FakeWayfire()
        backend.dispatch(ipc, {"op": "moveToWorkspace", "args": ["3"]})
        self.assertEqual(ipc.calls[-1], ("vswitch/set-workspace", {"x": 2, "y": 0, "output-id": 4, "view-id": 42}))

    def test_resize_preserves_output_local_coordinates(self):
        ipc = FakeWayfire()
        backend.dispatch(ipc, {"op": "resizeTo", "args": [700, 500, "address:0x2a"]})
        self.assertEqual(ipc.calls[-1], ("window-rules/configure-view", {
            "id": 42, "geometry": {"x": -1200, "y": 20, "width": 700, "height": 500}}))

    def test_programmatic_retiling_never_invokes_the_unsafe_layout_api(self):
        ipc = FakeWayfire()
        with self.assertRaisesRegex(ValueError, "Super\\+F"):
            backend.dispatch(ipc, {"op": "floatOff"})
        self.assertFalse(any(method.startswith("simple-tile/") for method, _ in ipc.calls))

    def test_already_floating_windows_still_allow_resize_sequences(self):
        ipc = FakeWayfire()
        backend.dispatch(ipc, {"op": "floatOn"})
        self.assertTrue(all(method.startswith("window-rules/") for method, _ in ipc.calls))

    def test_sequences_use_pending_geometry_not_uncommitted_compositor_geometry(self):
        ipc = FakeWayfire()
        state = backend.snapshot(ipc)
        backend.dispatch(ipc, {"op": "resizeBy", "args": [100, 0]}, state)
        backend.dispatch(ipc, {"op": "moveBy", "args": [25, 0]}, state)
        self.assertEqual(ipc.calls[-1][1]["geometry"], {
            "x": -1175, "y": 20, "width": 700, "height": 400})

    def test_move_output_and_focus_free_raise_use_native_payloads(self):
        ipc = FakeWayfire()
        ipc.outputs.append(dict(ipc.outputs[0], id=7, name="DP-2"))
        backend.dispatch(ipc, {"op": "moveToMonitor", "args": ["+1"]})
        self.assertEqual(ipc.calls[-1], ("window-rules/configure-view", {"id": 42, "output_id": 7}))
        backend.dispatch(ipc, {"op": "raiseWindow", "args": ["address:0x2a"]})
        self.assertEqual(ipc.calls[-1], ("wm-actions/bring-to-front", {"view_id": 42, "state": True}))

    def test_unsupported_lua_controls_fail_without_running_lua(self):
        ipc = FakeWayfire()
        with self.assertRaisesRegex(ValueError, "Hyprland-only"):
            backend.dispatch(ipc, {"op": "tagWindow", "args": []})
        self.assertEqual(ipc.calls, [])

    def test_capture_and_cursor_query_formats(self):
        ipc = FakeWayfire()
        self.assertEqual(backend.query(ipc, ["cursorpos"]), "2020, 40")
        monitors, clients, active, shadows = map(json.loads, backend.query(ipc, ["capture"]).split("@@"))
        self.assertEqual(active["address"], "0x2a")
        self.assertEqual(clients[0]["workspace"]["address"], "wf:4:1")
        self.assertEqual(monitors[0]["name"], "DP-1")
        self.assertEqual(shadows, [])

    def test_fragmented_ipc_messages(self):
        client, server = socket.socketpair()
        ipc = backend.Wayfire.__new__(backend.Wayfire)
        ipc.socket = client
        reply = json.dumps({"result": "ok"}).encode()
        wire = struct.pack("<I", len(reply)) + reply

        def respond():
            with server:
                for byte in wire:
                    server.sendall(bytes([byte]))

        sender = threading.Thread(target=respond)
        sender.start()
        try:
            self.assertEqual(ipc.receive(), {"result": "ok"})
            with self.assertRaisesRegex(backend.IpcError, "closed"):
                ipc.receive()
        finally:
            ipc.close()
            sender.join()

    def test_ipc_errors_are_not_success_results(self):
        ipc = backend.Wayfire.__new__(backend.Wayfire)
        client, server = socket.socketpair()
        ipc.socket = client
        ipc.receive = lambda: {"error": "No such method found!"}
        try:
            with self.assertRaisesRegex(backend.IpcError, "No such method"):
                ipc.call("unavailable")
        finally:
            client.close()
            server.close()

    def test_invalid_frame_sizes_are_rejected(self):
        ipc = backend.Wayfire.__new__(backend.Wayfire)
        ipc.read_exact = lambda size: struct.pack("<I", 17 * 1024 * 1024)
        with self.assertRaisesRegex(backend.IpcError, "message size"):
            ipc.receive()


class RecorderTests(unittest.TestCase):
    def test_stalled_recorder_is_reaped_without_abandoning_a_child(self):
        child = Mock()
        child.poll.return_value = None
        child.wait.side_effect = [subprocess.TimeoutExpired("wf-recorder", 10), 0]
        with self.assertRaisesRegex(RuntimeError, "finalize"):
            recorder.finish(child)
        child.kill.assert_called_once()
        self.assertEqual(child.wait.call_count, 2)

    def run_recording(self, audio, fail_unload=False):
        with tempfile.TemporaryDirectory() as directory:
            modules = iter(("1", "2", "3"))
            calls = []

            def output(*args):
                if args[0] == "xdg-user-dir":
                    return directory
                if args[0] == "qs":
                    return "audio=" + audio + " countdown=0"
                if args[1] == "load-module":
                    return next(modules)
                return "default-device"

            def run(args, **kwargs):
                if args[:2] == ["pactl", "unload-module"]:
                    calls.append(args[2])
                    if fail_unload and args[2] == "3":
                        raise subprocess.CalledProcessError(1, args)

            child = Mock()
            child.wait.return_value = 0
            child.poll.return_value = 0
            with patch.object(recorder, "output", side_effect=output), \
                    patch.object(recorder, "Wayfire"), \
                    patch.object(recorder, "snapshot", return_value=backend.snapshot(FakeWayfire())), \
                    patch.object(recorder.shutil, "which", side_effect=lambda name: None if name == "pactl" and audio == "none" else "/bin/" + name), \
                    patch.object(recorder.signal, "signal"), \
                    patch.object(recorder.subprocess, "Popen", return_value=child) as popen, \
                    patch.object(recorder.subprocess, "run", side_effect=run), \
                    patch.object(recorder, "shell_call") as shell_call:
                if fail_unload:
                    with self.assertRaises(subprocess.CalledProcessError):
                        recorder.record("screen")
                else:
                    self.assertEqual(recorder.record("screen"), 0)
                    self.assertFalse(any(arg.startswith("--audio") for arg in popen.call_args.args[0]))
                shell_call.assert_called_with("recording", "false")
                self.assertFalse((Path(directory) / "Captures/.active-recording").exists())
            return calls

    def test_silent_video_does_not_require_audio_tools(self):
        self.assertEqual(self.run_recording("none"), [])

    def test_all_audio_modules_unload_even_when_one_cleanup_fails(self):
        self.assertEqual(self.run_recording("both", fail_unload=True), ["3", "2", "1"])


class LauncherTests(unittest.TestCase):
    def test_init_preserves_existing_wayfire_sessions_and_user_edits(self):
        with tempfile.TemporaryDirectory() as directory:
            env = dict(os.environ, HOME=directory, XDG_CONFIG_HOME=directory + "/config")
            env.pop("ZENWORKS_ROOT", None)
            existing = Path(env["XDG_CONFIG_HOME"]) / "wayfire.ini"
            existing.parent.mkdir()
            existing.write_text("existing session\n")
            command = [str(ROOT / "bin/zen-wayfire"), "--init"]
            subprocess.run(command, env=env, check=True, stdout=subprocess.DEVNULL)
            config = existing.parent / "zenworks-wayfire/wayfire.ini"
            self.assertIn("[core]", config.read_text())
            config.write_text("my edits\n")
            subprocess.run(command, env=env, check=True, stdout=subprocess.DEVNULL)
            self.assertEqual(config.read_text(), "my edits\n")
            self.assertEqual(existing.read_text(), "existing session\n")


if __name__ == "__main__":
    unittest.main()

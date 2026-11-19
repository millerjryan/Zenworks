import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Wayland

Item {
  id: root
  property var state: ({ monitors: [], workspaces: [], clients: [], focusedOutput: -1, focusedView: -1 })
  QtObject { id: monitorModel; property var values: [] }
  QtObject { id: workspaceModel; property var values: [] }
  QtObject { id: windowModel; property var values: [] }
  readonly property var monitors: monitorModel
  readonly property var workspaces: workspaceModel
  readonly property var toplevels: windowModel
  readonly property var focusedMonitor: monitors.values.find(m => m.id === state.focusedOutput) || null
  readonly property var focusedWorkspace: focusedMonitor ? focusedMonitor.activeWorkspace : null
  readonly property var activeToplevel: toplevels.values.find(t => t.id === state.focusedView) || null
  signal rawEvent(var event)

  function applyState(snapshot) {
    const previous = state;
    const previousOutput = previous.monitors.find(m => m.id === previous.focusedOutput);
    const previousWorkspace = previousOutput && previousOutput.activeWorkspace ? previousOutput.activeWorkspace.address : "";
    state = snapshot;
    const outputs = snapshot.monitors;
    const spaces = snapshot.workspaces;
    const handles = ToplevelManager.toplevels.values;
    const clients = snapshot.clients.map(c => Object.assign({}, c, {
      wayland: handles.find(t => t.title === c.title && t.appId === c.class) || null,
      workspace: spaces.find(w => w.id === c.workspace.id && w.monitorID === c.monitor)
    }));
    for (const w of spaces) {
      w.toplevels = { values: clients.filter(c => c.workspace === w) };
      w.hasFullscreen = w.toplevels.values.some(c => c.fullscreen);
      w.monitor = outputs.find(m => m.id === w.monitorID);
    }
    for (const m of outputs) m.activeWorkspace = spaces.find(w => w.monitorID === m.id && w.active);
    monitorModel.values = outputs;
    workspaceModel.values = spaces;
    windowModel.values = clients;
    const currentWorkspace = focusedWorkspace ? focusedWorkspace.address : "";
    if (previousWorkspace !== currentWorkspace || previous.focusedOutput !== snapshot.focusedOutput)
      rawEvent({ name: "workspacev2", data: focusedWorkspace ? focusedWorkspace.id + "," + focusedWorkspace.name : "" });
    for (const client of clients) {
      const old = previous.clients.find(c => c.id === client.id);
      if (!old) rawEvent({ name: "openwindow", data: client.address + "," + client.workspace.name + "," + client.class + "," + client.title });
      else if (old.floating !== client.floating || old.fullscreen !== client.fullscreen
               || JSON.stringify(old.at) !== JSON.stringify(client.at) || JSON.stringify(old.size) !== JSON.stringify(client.size))
        rawEvent({ name: "movewindowv2", data: client.address });
    }
    for (const old of previous.clients)
      if (!clients.some(c => c.id === old.id)) rawEvent({ name: "closewindow", data: old.address });
    rawEvent({ name: "activewindow", data: activeToplevel ? activeToplevel.class + "," + activeToplevel.title : "," });
  }
  Connections {
    target: ToplevelManager.toplevels
    function onValuesChanged() { root.applyState(root.state); }
  }
  function dispatch(command) {
    if (typeof command === "string") {
      Compositor.unavailable("Hyprland Lua dispatch");
      return;
    }
    Quickshell.execDetached(["python3", Compositor.bridge, "dispatch", JSON.stringify(command)]);
  }
  function refreshToplevels() {
    // The persistent event subscription supplies updates, without polling.
  }
  Process {
    id: events
    command: ["python3", Compositor.bridge, "watch"]
    running: true
    stdout: SplitParser {
      onRead: line => {
        try { root.applyState(JSON.parse(line)); }
        catch (error) { console.error("Wayfire state:", error); }
      }
    }
    stderr: SplitParser { onRead: line => console.error("Wayfire:", line) }
    onExited: (code, status) => {
      console.error("Wayfire event connection stopped:", code, status);
      reconnect.start();
    }
  }
  Timer { id: reconnect; interval: 3000; onTriggered: events.running = true }
  IpcHandler {
    target: "WayfireCapture"
    function record(mode: string): string {
      if (recorder.running) { recorder.running = false; return "stopping"; }
      if (mode === "stop") return "not recording";
      if (["screen", "region", "window"].indexOf(mode) < 0) return "unknown mode";
      recorder.command = ["python3", Quickshell.shellDir + "/compositor/record.py", mode];
      recorder.running = true;
      return "starting";
    }
  }
  Process {
    id: recorder
    stderr: SplitParser { onRead: line => console.warn("Wayfire recorder:", line) }
  }
}

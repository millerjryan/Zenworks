pragma Singleton

import QtQuick
import Quickshell
import Quickshell.Io
import "../morpheus/offspecial.js" as Off
import "../morpheus/room.js" as Room
import "commands.js" as Commands

Singleton {
  id: root
  readonly property bool isWayfire: Quickshell.env("ZENWORKS_COMPOSITOR") === "wayfire"
  readonly property string name: isWayfire ? "Wayfire" : "Hyprland"
  readonly property string bridge: Quickshell.shellDir + "/compositor/wayfire.py"
  readonly property var toplevels: backend.item ? backend.item.toplevels : emptyModel
  readonly property var workspaces: backend.item ? backend.item.workspaces : emptyModel
  readonly property var monitors: backend.item ? backend.item.monitors : emptyModel
  readonly property var activeToplevel: backend.item ? backend.item.activeToplevel : null
  readonly property var focusedWorkspace: backend.item ? backend.item.focusedWorkspace : null
  readonly property var focusedMonitor: backend.item ? backend.item.focusedMonitor : null
  signal rawEvent(var event)
  QtObject { id: emptyModel; readonly property var values: [] }

  Loader {
    id: backend
    source: root.isWayfire ? "Wayfire.qml" : "Hyprland.qml"
  }
  Connections {
    target: backend.item
    function onRawEvent(event) { root.rawEvent(event); }
  }
  function monitorFor(screen) {
    return root.monitors.values.find(m => screen && m.name === screen.name) || null;
  }
  function refreshToplevels() {
    if (backend.item) backend.item.refreshToplevels();
  }
  function dispatch(command) {
    if (!backend.item) {
      console.error("Zenworks: compositor backend is not ready");
      return;
    }
    backend.item.dispatch(command);
  }
  function query(args) {
    return root.isWayfire ? ["python3", root.bridge, "query"].concat(args.filter(a => a !== "hyprctl"))
                          : args;
  }
  function wanted(commands) {
    const list = Array.isArray(commands) ? commands : [commands];
    return root.isWayfire ? ["python3", root.bridge, "sequence", JSON.stringify(list)]
                          : Off.wanted(list.map(c => typeof c === "string" ? c : c.native));
  }
  function bundle(name, nativeCommand) {
    return root.isWayfire ? ["python3", root.bridge, "query", name] : nativeCommand;
  }
  function resizeRoom(address, room) {
    if (!root.isWayfire) {
      Room.dispatches(address, room).forEach(d => root.dispatch(d));
      return;
    }
    const selector = Commands.byAddress(address);
    Quickshell.execDetached(root.wanted([
      Commands.resizeBy(room.dw, 0, selector),
      Commands.moveBy(room.dx - room.dw / 2, 0, selector)
    ]));
  }
  function unavailable(feature) {
    const text = feature + " is not available on Wayfire. Edit the standalone zenworks-wayfire/wayfire.ini for compositor settings.";
    console.warn(text);
    Quickshell.execDetached(["notify-send", "-a", "Zenworks", "Wayfire", text]);
  }
}

import QtQuick
import Quickshell.Hyprland

Item {
  readonly property var toplevels: Hyprland.toplevels
  readonly property var workspaces: Hyprland.workspaces
  readonly property var monitors: Hyprland.monitors
  readonly property var activeToplevel: Hyprland.activeToplevel
  readonly property var focusedWorkspace: Hyprland.focusedWorkspace
  readonly property var focusedMonitor: Hyprland.focusedMonitor
  signal rawEvent(var event)
  function dispatch(command) { Hyprland.dispatch(typeof command === "string" ? command : command.native); }
  function refreshToplevels() { Hyprland.refreshToplevels(); }
  Connections {
    target: Hyprland
    function onRawEvent(event) { rawEvent(event); }
  }
}

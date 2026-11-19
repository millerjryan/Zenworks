import QtQuick

Item {
  id: root
  property bool active: false
  property var windows: []
  signal cleared()
  property bool hadFocus: false
  onActiveChanged: if (!active) hadFocus = false
  Loader {
    id: nativeGrab
    active: !Compositor.isWayfire
    source: "HyprlandGrab.qml"
    onLoaded: {
      item.active = Qt.binding(() => root.active);
      item.windows = Qt.binding(() => root.windows);
    }
    Connections {
      target: nativeGrab.item
      ignoreUnknownSignals: true
      function onCleared() { root.cleared(); }
    }
  }
  // Wayfire has no Hyprland focus-grab protocol. Layer-shell owns keyboard
  // focus; dismiss once focus leaves a popup that has received it.
  Timer {
    interval: 100
    repeat: true
    running: Compositor.isWayfire && root.active
    onTriggered: {
      const focused = root.windows.some(w => w && w.active);
      if (focused) root.hadFocus = true;
      else if (root.hadFocus) {
        root.hadFocus = false;
        root.cleared();
      }
    }
  }
}

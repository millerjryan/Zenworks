.pragma library
.import "../morpheus/hypr.js" as Native

// Keep native serialization at this boundary, not in the Wayfire backend.
function request(op, args) {
  return { op: op, args: args, native: Native[op].apply(null, args) };
}
function lua(s) { return Native.lua(s); }
function byTitle(s) { return Native.byTitle(s); }
function byClass(s) { return Native.byClass(s); }
function byAddress(s) { return Native.byAddress(s); }
function workspaceSelector(s) { return Native.workspaceSelector(s); }
function focusWindow(s) { return request("focusWindow", [s]); }
function focusTitle(s) { return request("focusTitle", [s]); }
function focusWorkspace(s) { return request("focusWorkspace", [s]); }
function focusNamedWorkspace(s) { return request("focusNamedWorkspace", [s]); }
function raiseWindow(s) { return request("raiseWindow", [s]); }
function closeWindow(s) { return request("closeWindow", [s]); }
function tagWindow(s, tag, on) { return request("tagWindow", [s, tag, on]); }
function toggleSpecial(s) { return request("toggleSpecial", [s]); }
function fullscreen() { return request("fullscreen", []); }
function floatToggle() { return request("floatToggle", []); }
function floatOn() { return request("floatOn", []); }
function floatOff() { return request("floatOff", []); }
function center() { return request("center", []); }
function moveToWorkspace(s) { return request("moveToWorkspace", [s]); }
function moveToMonitor(s) { return request("moveToMonitor", [s]); }
function resizeBy(x, y, s) { return request("resizeBy", [x, y, s]); }
function moveBy(x, y, s) { return request("moveBy", [x, y, s]); }
function resizeTo(x, y, s) { return request("resizeTo", [x, y, s]); }
function moveTo(x, y, s) { return request("moveTo", [x, y, s]); }
function execWith(cmd, rules) { return request("execWith", [cmd, rules]); }
function placeWindow(a, p) { return Native.placeWindow(a, p); }
function submap(s) { return request("submap", [s]); }
function dpms(on) { return request("dpms", [on]); }

function bindings(text) {
  const sections = {};
  let section = "";
  for (const raw of String(text).split("\n")) {
    const line = raw.trim();
    if (!line || line.startsWith("#") || line.startsWith(";")) continue;
    if (/^\[.*\]$/.test(line)) {
      section = line.slice(1, -1);
      sections[section] = sections[section] || {};
      continue;
    }
    const equal = line.indexOf("=");
    if (equal >= 0 && section) sections[section][line.slice(0, equal).trim()] = line.slice(equal + 1).trim();
  }
  const out = [];
  for (const group of Object.keys(sections)) {
    const options = sections[group];
    for (const key of Object.keys(options)) {
      if (!/(?:KEY_|BTN_)/.test(options[key])) continue;
      if (key.startsWith("command_")) continue;
      options[key].split("|").forEach((value, index) => {
        const chord = value.trim().replace(/<([^>]+)>/g, (_, m) => m.toUpperCase() + " +")
          .replace(/KEY_/g, "").replace(/\bENTER\b/g, "RETURN").replace(/\bESC\b/g, "ESCAPE")
          .replace(/\bSYSRQ\b/g, "PRINT").replace(/\s+/g, " ");
        out.push({ id: group + ":" + key + ":" + index, chord: chord,
          label: options[key.replace(/^binding_/, "command_")] || key.replace(/_/g, " "),
          group: group.toUpperCase() });
      });
    }
  }
  return out;
}

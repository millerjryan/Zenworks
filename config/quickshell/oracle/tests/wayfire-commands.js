"use strict";

module.exports = {
  module: "compositor/commands.js",
  cases(c, t) {
    const request = c.focusTitle('title "quoted"');
    t.eq("Wayfire receives structured commands", request.op, "focusTitle");
    t.eq("titles stay data", request.args, ['title "quoted"']);
    t.eq("Hyprland keeps its native serialization", request.native, c.Native.focusTitle('title "quoted"'));
    for (const [op, args] of [
      ["focusWindow", ["address:0x42"]], ["raiseWindow", ["address:0x42"]],
      ["closeWindow", ["address:0x42"]], ["focusWorkspace", ["3"]],
      ["focusNamedWorkspace", ["3"]], ["moveToWorkspace", ["2"]],
      ["moveToMonitor", ["+1"]], ["resizeBy", [40, 0, "address:0x42"]],
      ["moveBy", [-20, 0, "address:0x42"]], ["resizeTo", [640, 480]],
      ["moveTo", [10, 20]], ["fullscreen", []], ["floatOn", []],
      ["floatOff", []], ["floatToggle", []], ["center", []], ["dpms", [false]],
      ["submap", ["reset"]], ["toggleSpecial", ["special"]]
    ]) {
      t.eq(op + " keeps native behavior", c[op].apply(null, args).native, c.Native[op].apply(null, args));
    }
    const bindings = c.bindings(`
[command]
binding_files = <super> KEY_E
command_files = qs ipc call Terminus spawn ''
binding_disabled = none
[core]
close_top_view = <super> KEY_Q | <alt> KEY_F4
[vswitch]
binding_2 = <super> <shift> KEY_2
`);
    t.eq("sheet includes all key alternatives, not disabled bindings", bindings.length, 4);
    t.eq("command labels come from the matching command", bindings[0].label, "qs ipc call Terminus spawn ''");
    t.eq("chords use the existing sheet vocabulary", bindings[3].chord, "SUPER + SHIFT + 2");
    t.eq("Wayfire's native close alternative is retained", bindings[2].chord, "ALT + F4");
  }
};

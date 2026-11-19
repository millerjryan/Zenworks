#!/bin/sh
set -eu

children=""
shell_pid=""
start() {
    "$@" &
    children="$children $!"
}
cleanup() {
    trap - EXIT INT TERM
    for pid in $children $shell_pid; do
        if kill -0 "$pid" 2>/dev/null; then kill -TERM "$pid"; fi
    done
    wait
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

if command -v wl-paste >/dev/null && command -v cliphist >/dev/null; then
    start wl-paste --type text --watch cliphist store
    start wl-paste --type image --watch cliphist store
else
    echo "zen-wayfire: clipboard history needs wl-clipboard and cliphist" >&2
fi
if command -v wl-clip-persist >/dev/null; then
    start wl-clip-persist --clipboard regular
fi
if [ -x /usr/lib/hyprpolkitagent/hyprpolkitagent ]; then
    start /usr/lib/hyprpolkitagent/hyprpolkitagent
elif [ -x /usr/lib/polkit-gnome/polkit-gnome-authentication-agent-1 ]; then
    start /usr/lib/polkit-gnome/polkit-gnome-authentication-agent-1
elif command -v lxqt-policykit-agent >/dev/null; then
    start lxqt-policykit-agent
else
    echo "zen-wayfire: install a polkit agent for privileged desktop actions" >&2
fi

export ZENWORKS_WAYFIRE_SUPERVISED=1
while [ -S "$WAYFIRE_SOCKET" ]; do
    python3 "$ZENWORKS_ROOT/quickshell/compositor/wayfire.py" query monitors >/dev/null || break
    "$ZENWORKS_ROOT/quickshell/scripts/launch.sh" -n &
    shell_pid=$!
    status=0
    wait "$shell_pid" || status=$?
    shell_pid=""
    [ -S "$WAYFIRE_SOCKET" ] || break
    echo "zen-wayfire: shell exited ($status); restarting in 2 seconds" >&2
    sleep 2
done

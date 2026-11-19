<p align="center">
  <img src="zenworks.png" alt="Zenworks" width="800">
</p>

<h3><p align="center">
A zen Arch-based ecosystem in Quickshell
</p></h3>

---

Zenworks is a desktop environment for Arch Linux, built on
[Quickshell](https://quickshell.org) and [Hyprland](https://hyprland.org).

## Wayfire session

This fork also supports **Zenworks (Wayfire)**. The original `zen` command,
Hyprland configuration and desktop entry are unchanged. The additional
configuration lives in `config/wayfire/`; `zen-wayfire` seeds
`~/.config/zenworks-wayfire/wayfire.ini` on first use, and always launches
Wayfire with that explicit path. It never writes `~/.config/wayfire.ini`,
`~/.config/wayfire/`, or another Wayfire session's configuration.
Existing Zenworks app settings and data are shared; this is a separate
compositor configuration, not an isolated desktop profile. Default-app
choices are kept separately in `zenworks-wayfire/defaults.lua`; Oracle's
settings bundles skip Hyprland compositor files in this session. Back up
the Wayfire INI separately.

Install the existing Zenworks app dependencies, plus Wayfire 0.11 or newer,
Python 3, `xdg-desktop-portal-wlr`, `xdg-desktop-portal-gtk`, and a polkit
agent (`hyprpolkitagent`, `polkit-gnome`, or `lxqt-policykit`). Capture uses
`grim`, `slurp`, `wf-recorder`, `wl-clipboard`, and `pactl` from
`libpulse`; output power control uses `wlopm`. Clipboard history needs
`cliphist`. Hyprland is not needed to run the Wayfire session; an existing
`zenworks` AUR package may still depend on it.

From a checkout, prepare the independent configuration with:

```sh
./bin/zen-wayfire --init
./bin/zen-wayfire --where
```

Then run `./bin/zen-wayfire` from a text console. For a persistent login
screen entry, install this fork separately from the original Zenworks:

```sh
sudo install -d /usr/local/share/zenworks-wayfire
sudo cp -a config/. /usr/local/share/zenworks-wayfire/
sudo install -Dm755 bin/zen-wayfire /usr/local/bin/zen-wayfire
sudo install -Dm644 share/wayland-sessions/zenworks-wayfire.desktop /usr/share/wayland-sessions/zenworks-wayfire.desktop
sudo install -Dm644 share/xdg-desktop-portal/zenworks-wayfire-portals.conf /usr/share/xdg-desktop-portal/zenworks-wayfire-portals.conf
```

Install the dedicated portal preference file above for screen sharing even
when launching from a checkout.

Select **Zenworks (Wayfire)** at login. `ZENWORKS_ROOT` can select another
installation's `config` directory. Later updates do not overwrite your
Wayfire INI; merge changes from the shipped file yourself. Wayfire watches
its configuration for edits. Never remove `ipc`, `ipc-rules`,
`foreign-toplevel`, or `session-lock` from the plugin list.

### Features and substitutions

The Quickshell pill, launcher, desktop/backgrounds, notifications, tray,
clipboard, audio/media, network/Bluetooth controls, settings, lock/idle
handling and suite apps are retained. The Wayfire backend subscribes to IPC
events for windows, workspaces and output focus, rather than polling.
Screenshots, OCR/QR, annotation, and recording/editing retain the existing
apps. Hardware-dependent features still require their usual dependencies.

| Feature | Wayfire behavior |
| --- | --- |
| Workspace keys and bar | Five workspaces per output; Super+1...5 switches, Shift also moves the window |
| Tiling and floating | Native simple-tile; Super+F toggles; Super+arrows focuses; Super+Ctrl+Left/Right snaps |
| Window switching | Native fast-switcher on Super+Tab / Super+Shift+Tab |
| Special workspace | Replaced by Expo overview on Super+grave; not a scratchpad |
| Fullscreen / maximize | Super+Shift+F / Super+Z |
| Screenshots | Screen, region, focused-window rectangle; no Hyprland-only isolated-window shadows |
| Recording | Super+R screen, Super+Ctrl+R region via slurp, Super+Shift+R focused window; press again to stop; Argus countdown, audio choices and camera overlay remain |
| Shortcuts sheet | Super+/ lists the active Wayfire INI bindings; edit the INI rather than Oracle's Hyprland shortcut editor |
| Settings | Shell/app settings work; compositor-only rows explain where to configure Wayfire instead |
| Popup dismissal | Layer-shell keyboard focus and Escape replace Hyprland's exclusive pointer-grab protocol; outside-click dismissal is best effort |
| Theme | Shell, app, GTK/Qt and terminal colors remain; compositor decoration/effects are configured in the Wayfire INI |

Wayfire's terminal/browser shortcuts use the commands in the INI; changing
a default application in Oracle does not rewrite those native shortcuts.
Launcher snapping/layout presets and its floating toggle are unavailable;
use Wayfire's native shortcuts instead. Programmatic simple-tile layout
replacement crashed the compositor during the Wayfire 0.11 smoke check,
so the adapter deliberately does not call that API. Floating suite windows
can still resize for their own sidebars and split panes.

Hyprland Lua rules, dynamic launcher hotkeys, Hyper-key remapping, app
restore/placement at login, Caps Lock detection, dynamic large recording
cursors, Oracle's automatic fcitx5 setup, special-workspace behavior and Hyprland shader/blur styles are not
ported. Their Hyprland controls are unavailable on Wayfire. Configure
startup commands under `[autostart]` and rules under `[window-rules]`.
For input methods, configure fcitx5 and its application environment manually
and add `fcitx5 -d` under `[autostart]`.
The original Hyprland implementation remains available by logging into
**Zenworks** instead.

For features without an exact equivalent, these are the available choices:

- **Effects:** use the bundled native `animate`/`blur` plugins (default),
  add Wayfire's `wobbly`/`cube` plugins, or disable effects for lower GPU use.
- **Night light:** add `wlsunset` with explicit coordinates or sunrise/sunset
  times under `[autostart]`, use an external gamma-control application,
  or leave it off. Hermes' Hyprsunset controls are disabled.
- **Scratchpad:** use Expo (default), reserve workspace 5 for parked windows,
  or install a separate Wayfire scratchpad extension after reviewing it.

Output layout, physical keyboard bindings, GPU effects, locking/resume,
audio/video capture and portals should be checked in a real login before
using this as your daily session. Headless checks cannot certify those
hardware-dependent paths.

To roll back, select your original session at login. This port requires no
changes to an existing Wayfire or Hyprland configuration. Removing the
additional desktop entry and `zen-wayfire` stops advertising this session;
your data remains in place.

### Wayfire development checks

```sh
node config/quickshell/oracle/test.js
python3 config/quickshell/oracle/tests/wayfire.py
sh -n bin/zen-wayfire config/wayfire/session.sh
```

## Install

Zenworks is on the AUR. With an AUR helper:

```sh
paru -S zenworks
```

Everything it needs comes with it: Hyprland, Quickshell, the portals, the
fonts and the tools the suite uses. A few extras are optional; they are
listed when the install finishes, and most are installed for you the first
time you use what needs them.

On NVIDIA, also install your driver (`nvidia-open` or `nvidia`, with
`nvidia-utils`).

## Start

Log out and pick **Zenworks** on your login screen, or run `zen` from a
text console. (`zenworks`, its older name, still works.)

A login screen set up to run one fixed command (greetd with
`--cmd start-hyprland`, for instance) needs that command changed to `zen`.

The very first start opens the shortcuts cheat sheet; **Super + /** brings
it back any time, and typing filters it. A moment later Zenworks asks
whether you want its terminal setup: zsh with a fast prompt, suggestions
and fuzzy completion. Your own setup is kept as a backup. Oracle › Default
apps › Terminal setup offers it again later.

## Getting around

| Keys | What they do |
| --- | --- |
| Super + Space | Cynosure, the launcher |
| Super + / | Every shortcut on one sheet |
| Super + Tab | The window switcher: hold Super, tap Tab to step, let go to switch (Shift goes back) |
| Super + Ctrl + Tab | The same, for the windows of the app in front |
| Super + 1 … 5 | Go to a workspace; a strip of your workspaces shows as you switch |
| Super + Return | The terminal |
| Super + E | Terminus, the file manager |
| Super + Q | Close the window |
| Super + Escape | Lock the screen |

Every shortcut can be changed in Oracle › Shortcuts. The workspace strip
can be turned off in Oracle › Windows.

## Your settings

Everything you change lives in `~/.config/zenworks`: your themes, monitors,
shortcuts, input, Plato's plugins, and your own kitty lines
(`~/.config/zenworks/kitty/custom.conf`). An update never touches it.

To start over, log out and run `zen --reset` from a text console: your
settings are moved to `~/zenworks-reset-<date>`, never deleted, and the
next start is a first start again.

## Update

Zenworks updates like any other package: Ceres' Updates lists a new version
beside the rest (Oracle › About › Check for updates opens it), or run
`paru -Syu`.

## Remove

```sh
sudo pacman -Rns zenworks
```

Your settings stay in `~/.config/zenworks`; delete that directory too for a
clean slate.

## Working on Zenworks

To run a working copy instead of the installed Zenworks, put the path of
its `config` directory in `~/.config/zenworks/dev`, one line:

```sh
mkdir -p ~/.config/zenworks
echo ~/Projects/Zenworks/config > ~/.config/zenworks/dev
zen --where
```

Log in again and that copy runs, with Quickshell's live reload. Remove the
file to go back to the installed one.

## Credits

Zenworks stands on [Quickshell](https://quickshell.org) and
[Hyprland](https://hyprland.org), and on Qt, PipeWire and the many tools it
brings along.

Plato, the editor, runs on [Neovim](https://neovim.io) and these plugins,
fetched from their authors' own repositories on first start, each under its
own license:

- [vim-fugitive](https://github.com/tpope/vim-fugitive) by Tim Pope (Vim license)
- [multicursor.nvim](https://github.com/jake-stewart/multicursor.nvim) by jake-stewart (MIT)
- [conform.nvim](https://github.com/stevearc/conform.nvim) by Steven Arcangeli (MIT)
- [nvim-lint](https://github.com/mfussenegger/nvim-lint) by Mathias Fußenegger (GPL-3.0)
- [guess-indent.nvim](https://github.com/NMAC427/guess-indent.nvim) by Nicolas Camenisch (MIT)
- [SchemaStore.nvim](https://github.com/b0o/SchemaStore.nvim) by Maddison Cohodas (Apache-2.0)
- [lazydev.nvim](https://github.com/folke/lazydev.nvim) by Folke Lemaitre (Apache-2.0)
- [diffbandit.nvim](https://github.com/CoreyKaylor/diffbandit.nvim) by Corey Kaylor (Apache-2.0)
- [mini.nvim](https://github.com/nvim-mini/mini.nvim) by Evgeni Chasnovski (MIT)
- [nvim-lspconfig](https://github.com/neovim/nvim-lspconfig) by the Neovim team (Apache-2.0)
- [nvim-treesitter](https://github.com/nvim-treesitter/nvim-treesitter) by its contributors (Apache-2.0)

## License

GPL-3.0-or-later. See [LICENSE](LICENSE).


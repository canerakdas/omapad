#!/usr/bin/env bash
# Install omapad: uinput permissions, user config, and the systemd user
# service. Safe to re-run - every step is idempotent.
set -euo pipefail

REPO="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/omapad"
BIN_DIR="$HOME/.local/bin"

say() { printf '\033[1m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[33m==> %s\033[0m\n' "$*"; }

# --- 0. the checkout path ----------------------------------------------------
# It is written into the systemd unit at step 5 and into the config stub at
# step 2, and `omapad/unit.py` is the one place that decides which characters
# survive that (a space and a `%` do not: systemd would read them). Asked here
# rather than there, so a checkout that cannot be installed says so before this
# has written a file or asked for a password.
"$REPO/bin/omapad" unit check >/dev/null

# --- 1. uinput ---------------------------------------------------------------
# The daemon writes to /dev/uinput to create the virtual mouse and keyboard.
# Without this it would have to run as root, which it should not.
#
# The rule is written from these bytes, never copied out of the checkout. The
# checkout is writable by the user who is running this, and `sudo` opens the
# source path only when it finally runs - on the far side of a password prompt
# someone stood waiting at. Another process of the same user can swap the file
# in that window, and a udev rule carries `RUN+=`, which is to say it can name
# something to execute as root. A quoted here-document has no window at all:
# what is installed is what is in the installer that is running.
# `udev/99-omapad-uinput.rules` is the same rule for packagers, and
# `tests/test_packaging.py` is what keeps the two identical.
UINPUT_RULES=/etc/udev/rules.d/99-omapad-uinput.rules
UINPUT_RULE="$(cat <<'RULE'
# omapad needs to create virtual mouse and keyboard devices, which means
# write access to /dev/uinput. Granting it to the "input" group avoids running
# the daemon as root; static_node applies the same mode before the module has
# been loaded on demand.
KERNEL=="uinput", SUBSYSTEM=="misc", GROUP="input", MODE="0660", OPTIONS+="static_node=uinput"
RULE
)"

if [[ ! -e /dev/uinput ]] || ! [[ -w /dev/uinput ]]; then
  say "Granting the input group access to /dev/uinput (needs sudo)"
  sudo install -d -m755 /etc/udev/rules.d
  printf '%s\n' "$UINPUT_RULE" | sudo tee "$UINPUT_RULES" >/dev/null
  sudo chmod 644 "$UINPUT_RULES"
  # Read back before anything acts on it: `udevadm trigger` below is what makes
  # a rule real, and a rule that is not the one above must never get that far.
  if ! printf '%s\n' "$UINPUT_RULE" | sudo cmp -s - "$UINPUT_RULES"; then
    warn "$UINPUT_RULES is not the rule this installer wrote; stopping."
    exit 1
  fi
  echo uinput | sudo tee /etc/modules-load.d/omapad-uinput.conf >/dev/null
  sudo modprobe uinput
  sudo udevadm control --reload-rules
  sudo udevadm trigger --subsystem-match=misc --action=add
else
  say "/dev/uinput is already writable"
fi

if ! id -nG "$USER" | tr ' ' '\n' | grep -qx input; then
  say "Adding $USER to the input group (needs sudo)"
  sudo usermod -aG input "$USER"
  warn "Log out and back in for the new group to take effect."
fi

# --- 2. config ---------------------------------------------------------------
mkdir -p "$CONFIG_DIR"
# A stub, not a copy of the defaults: omapad merges the shipped config under
# whatever the user writes, so copying the whole file here would freeze today's
# defaults and shadow every later improvement.
if [[ -L "$CONFIG_DIR/config.toml" ]]; then
  # `-f` is true through a symlink and `cat >` writes through one, so a link
  # planted here would have this stub land on whatever it points at. Your own
  # link is left alone for the same reason: it is not this installer's to
  # follow.
  say "Keeping the link at $CONFIG_DIR/config.toml"
elif [[ -f "$CONFIG_DIR/config.toml" ]]; then
  say "Keeping your existing $CONFIG_DIR/config.toml"
else
  cat >"$CONFIG_DIR/config.toml" <<STUB
# omapad - your personal overrides.
#
# Anything you leave out falls back to the shipped defaults in
# $REPO/config/config.toml - read that file for the full list of settings, the
# action grammar, and the default bindings. Only write what you want to change
# here, so improvements to the defaults keep reaching you.
#
# After editing: systemctl --user restart omapad
STUB
  say "Wrote $CONFIG_DIR/config.toml"
fi

# --- 3. commands on PATH -----------------------------------------------------
mkdir -p "$BIN_DIR"
ln -sf "$REPO/bin/omapad" "$BIN_DIR/omapad"
say "Linked omapad into $BIN_DIR"
case ":$PATH:" in
  *":$BIN_DIR:"*) ;;
  *) warn "$BIN_DIR is not on your PATH; add it so the exec: bindings resolve." ;;
esac

# --- 4. shell plugin ---------------------------------------------------------
# The surfaces are drawn by a plugin inside the running omarchy-shell, so they
# inherit the active theme, the shell's corner radius and its gap to the
# screen edge. Symlinking rather than copying keeps this checkout the source of
# truth; the shell hot-reloads local plugins when their files change.
#
# What is linked is the checkout itself, not shell-plugin/: manifest.json sits
# at the root so `omarchy plugin add` - which clones a repo and looks for a
# manifest at its top - installs the daemon and the surfaces in one step. The
# manifest's entry points carry the shell-plugin/ prefix for the same reason.
PLUGIN_ID=canerakdas.omapad
PLUGIN_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/omarchy/plugins"
# The shell rejects a manifest it does not like on a console line nobody reads,
# and a rejected plugin looks exactly like a plugin that never drew. Ask
# Omarchy's own validator first, while there is still someone here to tell.
PLUGIN_OK=1
if command -v omarchy-plugin-validate >/dev/null 2>&1; then
  if ! omarchy-plugin-validate "$REPO"; then
    PLUGIN_OK=0
    warn "The shell plugin failed validation; skipping it. omapad itself still works."
  fi
fi
if [[ $PLUGIN_OK -eq 1 ]] && command -v omarchy-plugin-enable >/dev/null 2>&1; then
  mkdir -p "$PLUGIN_DIR"
  # `omarchy plugin add` clones the repo into the plugins directory itself, so
  # the checkout can already be where the link would go. Linking then would try
  # to overwrite a real directory and fail the whole install.
  if [[ $REPO -ef $PLUGIN_DIR/$PLUGIN_ID ]]; then
    say "This checkout already is $PLUGIN_DIR/$PLUGIN_ID"
  else
    ln -sfn "$REPO" "$PLUGIN_DIR/$PLUGIN_ID"
    say "Linked $PLUGIN_DIR/$PLUGIN_ID -> $REPO"
  fi
  omarchy-shell shell rescanPlugins >/dev/null 2>&1 || true
  omarchy-plugin-enable "$PLUGIN_ID" >/dev/null 2>&1 || true
  say "Enabled the $PLUGIN_ID shell plugin"
elif [[ $PLUGIN_OK -eq 1 ]]; then
  warn "omarchy-shell not found; the on-screen keyboard needs it to draw."
fi

# --- 5. service --------------------------------------------------------------
# The checkout path is baked into ExecStart, and both halves of doing that are
# decisions rather than glue, so both are in Python where a test can reach
# them (omapad/unit.py). This used to be `sed ... > "$UNIT_DIR/omapad.service"`:
# a path is not sed replacement syntax, and `>` opens the destination through
# whatever name is already there - a symlink planted at omapad.service made
# this truncate what it pointed at, and a Ctrl-C left half a unit behind.
UNIT="$("$REPO/bin/omapad" unit)"
say "Installed $UNIT"
systemctl --user daemon-reload
systemctl --user enable --now omapad.service
say "Service enabled. Check it with: systemctl --user status omapad"

echo
"$REPO/bin/omapad" check || true

#!/usr/bin/env bash
# Install omapad: uinput permissions, user config, and the systemd user
# service. Safe to re-run - every step is idempotent.
set -euo pipefail

REPO="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/omapad"
UNIT_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
BIN_DIR="$HOME/.local/bin"

say() { printf '\033[1m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[33m==> %s\033[0m\n' "$*"; }

# --- 1. uinput ---------------------------------------------------------------
# The daemon writes to /dev/uinput to create the virtual mouse and keyboard.
# Without this it would have to run as root, which it should not.
if [[ ! -e /dev/uinput ]] || ! [[ -w /dev/uinput ]]; then
  say "Granting the input group access to /dev/uinput (needs sudo)"
  sudo install -Dm644 "$REPO/udev/99-omapad-uinput.rules" \
    /etc/udev/rules.d/99-omapad-uinput.rules
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
if [[ -f "$CONFIG_DIR/config.toml" ]]; then
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
mkdir -p "$UNIT_DIR"
sed "s|__REPO__|$REPO|g" "$REPO/systemd/omapad.service" \
  > "$UNIT_DIR/omapad.service"
systemctl --user daemon-reload
systemctl --user enable --now omapad.service
say "Service enabled. Check it with: systemctl --user status omapad"

echo
"$REPO/bin/omapad" check || true

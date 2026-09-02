#!/usr/bin/env bash
# One command from nothing to a working omapad:
#
#   curl -fsSL https://raw.githubusercontent.com/canerakdas/omapad/main/boot.sh | bash
#
# It only fetches and hands over. The checkout lands *inside* the Omarchy
# plugins directory, so the clone itself is the plugin - manifest.json is at
# its root - and no symlink is involved. Everything after that is install.sh's
# job, including the one step that asks for sudo.
#
# Omarchy has no post-install hook for plugins: `omarchy plugin add` clones,
# validates and enables, and `omarchy plugin update` only pulls. Neither can
# grant /dev/uinput or install a user service, which is why this exists rather
# than the plugin installing itself.
set -euo pipefail

REPO_URL="${OMAPAD_REPO:-https://github.com/canerakdas/omapad.git}"
BRANCH="${OMAPAD_BRANCH:-main}"
PLUGIN_ID="${OMAPAD_PLUGIN_ID:-canerakdas.omapad}"
TARGET="${OMAPAD_DIR:-${XDG_CONFIG_HOME:-$HOME/.config}/omarchy/plugins/$PLUGIN_ID}"

say() { printf '\033[1m==>\033[0m %s\n' "$*"; }
fail() { printf '\033[31m==> %s\033[0m\n' "$*" >&2; exit 1; }

command -v git >/dev/null 2>&1 || fail "git is required to fetch omapad."

if [[ -d $TARGET/.git ]]; then
  say "Updating the checkout in $TARGET"
  # --ff-only: a checkout someone has edited is theirs, and a merge commit made
  # behind their back is worse than stopping here with the reason.
  git -C "$TARGET" pull --ff-only origin "$BRANCH" \
    || fail "$TARGET has local changes or has diverged; update it by hand."
elif [[ -e $TARGET ]]; then
  fail "$TARGET exists and is not a git checkout; move it aside first."
else
  say "Cloning omapad into $TARGET"
  mkdir -p "$(dirname "$TARGET")"
  git clone --branch "$BRANCH" -- "$REPO_URL" "$TARGET"
fi

say "Handing over to install.sh"
exec "$TARGET/install.sh"

#!/usr/bin/env bash
# One command from nothing to a working omapad - two lines, taken from the
# release being installed:
#
#   export OMAPAD_SHA=<the 40-character commit that release names>
#   curl -fsSL "https://raw.githubusercontent.com/canerakdas/omapad/$OMAPAD_SHA/boot.sh" | bash
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
#
# The commit to install is named from outside, and that is the whole point. A
# default SHA written into this file can never name the commit that contains
# it, so carrying one cost a commit per release whose only job was to move the
# pin: the submitted snapshot, the attested snapshot and the branch tip were
# then three different objects, and a reviewer could check none of them against
# another. Naming it in OMAPAD_SHA leaves this file identical from release to
# release, and the release notes carry both halves - the SHA in the URL fixes
# the script that runs, the SHA in the environment fixes the tree it installs.
set -euo pipefail

REPO_URL="${OMAPAD_REPO:-https://github.com/canerakdas/omapad.git}"
# The one knob with no default in place (conventions/bash.md 3.1): a default
# here would be this file choosing which snapshot to trust, which is the one
# decision it cannot make honestly.
SHA="${OMAPAD_SHA:-}"
PLUGIN_ID="${OMAPAD_PLUGIN_ID:-canerakdas.omapad}"
TARGET="${OMAPAD_DIR:-${XDG_CONFIG_HOME:-$HOME/.config}/omarchy/plugins/$PLUGIN_ID}"

say() { printf '\033[1m==>\033[0m %s\n' "$*"; }
fail() { printf '\033[31m==> %s\033[0m\n' "$*" >&2; exit 1; }

# A branch or tag name can move after this boot.sh is reviewed: what was
# reviewed is a snapshot, so only a snapshot may run. Requiring the full
# 40-character SHA up front is what keeps the rest of the script honest.
if [[ -z $SHA ]]; then
  fail "OMAPAD_SHA is not set; each release names the commit to install: https://github.com/canerakdas/omapad/releases"
fi

if ! [[ $SHA =~ ^[0-9a-f]{40}$ ]]; then
  fail "OMAPAD_SHA must be a full 40-character commit SHA, got: $SHA"
fi

command -v git >/dev/null 2>&1 || fail "git is required to fetch omapad."

if [[ -d $TARGET/.git ]]; then
  say "Updating the checkout in $TARGET"
  git -C "$TARGET" fetch --no-tags "$REPO_URL" \
    || fail "could not fetch from $REPO_URL; update $TARGET by hand."
  # A checkout someone has edited is theirs: resetting it would throw their
  # work away. Pin the tree to the reviewed commit only when it is clean, and
  # stop with an explanation rather than guessing.
  if ! git -C "$TARGET" diff --quiet || ! git -C "$TARGET" diff --cached --quiet; then
    fail "$TARGET has local changes; update it by hand."
  fi
  git -C "$TARGET" checkout --detach --force "$SHA" \
    || fail "commit $SHA is not in the fetched history; update it by hand."
elif [[ -e $TARGET ]]; then
  fail "$TARGET exists and is not a git checkout; move it aside first."
else
  say "Cloning omapad into $TARGET"
  mkdir -p "$(dirname "$TARGET")"
  git clone --no-checkout "$REPO_URL" "$TARGET"
  if ! git -C "$TARGET" checkout --detach --force "$SHA" 2>/dev/null; then
    # Nothing should run from a checkout that is not at the reviewed commit;
    # leave the directory clean rather than half-cloned.
    rm -rf "$TARGET"
    fail "commit $SHA is not in $REPO_URL; refusing to install."
  fi
fi

# The reviewed snapshot is the one that runs. If the pinned commit could not
# be checked out - a typo in OMAPAD_SHA, a rewritten history, a fork that
# never had it - nothing may execute from the remote.
if ! git -C "$TARGET" rev-parse --verify "${SHA}^{commit}" >/dev/null 2>&1 \
   || [[ "$(git -C "$TARGET" rev-parse HEAD)" != "$SHA" ]] \
   || ! git -C "$TARGET" diff --quiet; then
  fail "the checkout at $TARGET is not at reviewed commit $SHA; refusing to install."
fi

say "At reviewed commit ${SHA:0:12} - handing over to install.sh"
exec "$TARGET/install.sh"

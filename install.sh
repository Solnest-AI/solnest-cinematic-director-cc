#!/usr/bin/env bash
# Install the Solnest Cinematic Director into Claude Code (macOS / Linux).
# Claude runs this for the user; nobody has to type it. It symlinks the skill into
# ~/.claude/skills/ (so `git pull` updates it in place), then runs the doctor, which
# installs everything else the skill needs through uv (Python packages, a bundled ffmpeg,
# the headless browser). Windows: copy skill/solnest-cinematic-director into
# ~/.claude/skills/ instead, then run the doctor the same way.

set -euo pipefail

SRC="$(cd "$(dirname "$0")" && pwd)/skill/solnest-cinematic-director"
DEST="$HOME/.claude/skills/solnest-cinematic-director"

echo "Solnest Cinematic Director installer"
echo

UV="$(command -v uv || true)"
[ -z "$UV" ] && [ -x "$HOME/.local/bin/uv" ] && UV="$HOME/.local/bin/uv"
if [ -z "$UV" ]; then
  echo "  [MISS] uv. Install it with:  curl -LsSf https://astral.sh/uv/install.sh | sh"
  echo "         then run this installer again."
  exit 1
fi
echo "  [ok]   uv ($UV)"
[ -f "$SRC/SKILL.md" ] || { echo "  [MISS] SKILL.md not found at $SRC"; exit 1; }

mkdir -p "$HOME/.claude/skills"
if [ -e "$DEST" ] || [ -L "$DEST" ]; then
  if [ -L "$DEST" ]; then
    rm "$DEST"
  else
    BK="$DEST.bak-$(date +%Y%m%d-%H%M%S)"
    mv "$DEST" "$BK"
    echo "  Existing copy moved to $BK"
  fi
fi
ln -s "$SRC" "$DEST"
echo "  Installed: $DEST -> $SRC"
echo

"$UV" run "$SRC/scripts/doctor.py" --video || true
echo
echo "Restart Claude Code, then say:  make me a Solnest video for <listing url>"
echo "                            or:  make me a carousel for <listing url>"
echo "To uninstall:  rm \"$DEST\""

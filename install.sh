#!/usr/bin/env bash
# Install the Solnest Cinematic Director into Claude Code (macOS / Linux).
# Symlinks the skill into ~/.claude/skills/ so `git pull` updates it in place.
# Windows: copy skill/solnest-cinematic-director into %USERPROFILE%\.claude\skills\ instead.

set -euo pipefail

SRC="$(cd "$(dirname "$0")" && pwd)/skill/solnest-cinematic-director"
DEST="$HOME/.claude/skills/solnest-cinematic-director"

echo "Solnest Cinematic Director installer"
echo

ok=1
check() {  # name, command, fix
  if command -v "$2" >/dev/null 2>&1; then
    echo "  [ok]   $1"
  else
    echo "  [MISS] $1   $3"
    ok=0
  fi
}
check "ffmpeg " ffmpeg  "macOS: brew install ffmpeg   Linux: sudo apt install ffmpeg"
check "ffprobe" ffprobe "ships with ffmpeg"
check "python3" python3 "macOS: brew install python   Linux: sudo apt install python3"
check "curl   " curl    "required to download listing photos"
[ -f "$SRC/SKILL.md" ] || { echo "  [MISS] SKILL.md not found at $SRC"; ok=0; }

if [ "$ok" -ne 1 ]; then
  echo
  echo "Fix the items marked MISS above, then run this again."
  exit 1
fi

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
echo
echo "  Installed: $DEST -> $SRC"
echo

if python3 "$SRC/scripts/kie.py" --balance; then
  echo
  echo "KIE key works."
else
  echo
  echo "One step left: add your KIE key. Open this file (create it if needed):"
  echo "  $SRC/.env"
  echo "and add one line:"
  echo "  KIE_API_KEY=your_key_from_kie.ai"
  echo "Then check it with:  python3 \"$SRC/scripts/kie.py\" --balance"
fi
echo
if python3 -c "import playwright, PIL" >/dev/null 2>&1; then
  echo "Carousels: ready (Playwright + Pillow found)."
else
  echo "Carousels need two Python packages and a headless browser (videos do not)."
  echo "Run these once:"
  echo "  python3 -m pip install playwright pillow"
  echo "  python3 -m playwright install chromium"
fi
echo
echo "Restart Claude Code, then say:  make me a Solnest video for <listing url>"
echo "                            or:  make me a carousel for <listing url>"
echo "To uninstall:  rm \"$DEST\""

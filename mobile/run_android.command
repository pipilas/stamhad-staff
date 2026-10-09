#!/bin/bash
# Runs NUME on a connected Android phone (USB debugging on) or an Android emulator.
cd "$(dirname "$0")" || exit 1
fail() { printf "\n\033[31m%s\033[0m\n" "$1"; read -r -p "Press Enter to close…"; exit 1; }
command -v flutter >/dev/null || fail "Flutter isn't installed."
bash tool/setup_platforms.sh || fail "Setup failed (see above)."
DEV=$(flutter devices --machine 2>/dev/null | python3 -c 'import json,sys
d=[x for x in json.load(sys.stdin) if x.get("targetPlatform","").startswith("android")]
print(d[0]["id"] if d else "")')
if [ -z "$DEV" ]; then
  EMU=$(flutter emulators 2>/dev/null | awk -F'•' '/android/ {gsub(/ /,"",$1); print $1; exit}')
  [ -n "$EMU" ] || fail "No Android phone or emulator found. Plug in a phone with USB debugging, or create an emulator in Android Studio."
  flutter emulators --launch "$EMU"; sleep 25
  DEV=$(flutter devices --machine 2>/dev/null | python3 -c 'import json,sys
d=[x for x in json.load(sys.stdin) if x.get("targetPlatform","").startswith("android")]
print(d[0]["id"] if d else "")')
fi
flutter run -d "$DEV"

#!/bin/bash
# Opens the NUME app in the iPhone simulator (needs Xcode and Flutter on this Mac).
#
# Your Desktop is synced with iCloud, and iCloud adds hidden file tags that Apple's
# code signing refuses ("resource fork ... not allowed"). So we build from a copy in
# ~/Developer/nume-mobile (not synced). Keep editing the files here — this script
# copies the latest version over each time (the ios/android project folders live only
# there, so your Xcode signing settings are kept).
SRC="$(cd "$(dirname "$0")" && pwd)"
WORK="$HOME/Developer/nume-mobile"
fail() { printf "\n\033[31m%s\033[0m\n" "$1"; read -r -p "Press Enter to close…"; exit 1; }
command -v flutter >/dev/null || fail "Flutter isn't installed (https://docs.flutter.dev/get-started/install/macos)."
command -v xcodebuild >/dev/null || fail "Xcode isn't installed (App Store → Xcode)."

mkdir -p "$WORK"
rsync -a --delete \
  --exclude build/ --exclude .dart_tool/ --exclude /ios/ --exclude /android/ \
  --exclude firebase/node_modules/ --exclude .idea/ \
  "$SRC/" "$WORK/" || fail "Couldn't copy the app to $WORK"
xattr -cr "$WORK" 2>/dev/null
cd "$WORK" || exit 1

bash tool/setup_platforms.sh || fail "Setup failed (see above)."
open -a Simulator
sleep 6
DEV=$(flutter devices --machine 2>/dev/null | python3 -c 'import json,sys
d=[x for x in json.load(sys.stdin) if x.get("targetPlatform","").startswith("ios") and x.get("emulator")]
print(d[0]["id"] if d else "")')
[ -n "$DEV" ] || fail "No iPhone simulator is running. Open Simulator → File → Open Simulator → an iPhone, then run this again."
mkdir -p "$SRC/build"
echo "Building for the simulator (the first time takes several minutes)…"
if ! flutter build ios --simulator --debug -v > "$SRC/build/ios_build_log.txt" 2>&1; then
  grep -E "error:|Error:|failed:|Exited with|not allowed" "$SRC/build/ios_build_log.txt" | tail -25
  fail "The iPhone build failed. The full log is in mobile/build/ios_build_log.txt — tell Claude."
fi
flutter run -d "$DEV"

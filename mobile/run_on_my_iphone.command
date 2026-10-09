#!/bin/bash
# Installs NUME on your own iPhone (plugged in with a cable). Works with a free Apple ID;
# without the paid Apple Developer account the app stops opening after 7 days — just run
# this again to refresh it.
#
# One-time setup:
#   1. Xcode → Settings → Accounts → "+" → sign in with your Apple ID.
#      Select it → Manage Certificates → "+" → Apple Development.
#   2. Plug the iPhone in, unlock it, tap "Trust This Computer".
#   3. iPhone: Settings → Privacy & Security → Developer Mode → On (it restarts).
#   4. After the first install: iPhone Settings → General → VPN & Device Management →
#      your Apple ID → Trust.
SRC="$(cd "$(dirname "$0")" && pwd)"
WORK="$HOME/Developer/nume-mobile"          # outside iCloud (iCloud breaks code signing)
fail() { printf "\n\033[31m%s\033[0m\n" "$1"; read -r -p "Press Enter to close…"; exit 1; }
command -v flutter >/dev/null || fail "Flutter isn't installed."
command -v xcodebuild >/dev/null || fail "Xcode isn't installed (App Store → Xcode)."

mkdir -p "$WORK"
rsync -a --delete \
  --exclude build/ --exclude .dart_tool/ --exclude /ios/ --exclude /android/ \
  --exclude firebase/node_modules/ --exclude .idea/ \
  "$SRC/" "$WORK/" || fail "Couldn't copy the app to $WORK"
xattr -cr "$WORK" 2>/dev/null
cd "$WORK" || exit 1
bash tool/setup_platforms.sh || fail "Setup failed (see above)."

echo "Looking for your iPhone…"
DEV=$(flutter devices --machine 2>/dev/null | python3 -c 'import json,sys
d=[x for x in json.load(sys.stdin) if x.get("targetPlatform","").startswith("ios") and not x.get("emulator")]
print(d[0]["id"] if d else "")')
[ -n "$DEV" ] || fail "No iPhone found. Plug it in with a cable, unlock it, tap Trust, and turn on Developer Mode
(Settings → Privacy & Security → Developer Mode). Then run this again."

mkdir -p "$SRC/build"
echo "Building and installing on your iPhone (a few minutes the first time)…"
if ! flutter run --release -d "$DEV" 2>&1 | tee "$SRC/build/iphone_log.txt"; then
  :
fi
if grep -qiE "No valid code signing|Signing for \"Runner\" requires a development team|No development certificates" "$SRC/build/iphone_log.txt"; then
  open "$WORK/ios/Runner.xcworkspace"
  fail "Xcode needs your Apple ID to sign the app. In the Xcode window that just opened:
  Runner (left) → Signing & Capabilities → Team → choose your Apple ID (Personal Team).
Then run this again. (Full log: mobile/build/iphone_log.txt)"
fi
read -r -p "Done. Press Enter to close…"

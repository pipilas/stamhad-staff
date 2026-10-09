#!/bin/bash
# Creates / updates the iOS and Android project folders around lib/ and applies
# what Firebase needs. Safe to run again (never overwrites our own files).
set -e
cd "$(dirname "$0")/.."

flutter create --org com.stamhad --project-name nume --platforms=ios,android . >/dev/null

# Flutter now installs plugins with Swift Package Manager. Remove the old CocoaPods
# setup (from the first version of this script) so the two don't fight.
if [ -f ios/Podfile ] && grep -q "Firebase needs iOS 15" ios/Podfile; then
  if command -v pod >/dev/null; then (cd ios && pod deintegrate >/dev/null 2>&1 || true); fi
  rm -rf ios/Podfile ios/Podfile.lock ios/Pods
  cat > ios/Runner.xcworkspace/contents.xcworkspacedata <<'XML'
<?xml version="1.0" encoding="UTF-8"?>
<Workspace
   version = "1.0">
   <FileRef
      location = "group:Runner.xcodeproj">
   </FileRef>
</Workspace>
XML
  echo "Removed the old CocoaPods setup (Swift Package Manager is used now)."
fi

# ── Android ──
G=android/app/build.gradle.kts; [ -f "$G" ] || G=android/app/build.gradle
perl -0pi -e 's/minSdk\s*=\s*flutter\.minSdkVersion/minSdk = 23/; s/minSdkVersion\s+flutter\.minSdkVersion/minSdkVersion 23/' "$G"
M=android/app/src/main/AndroidManifest.xml
grep -q 'android.permission.INTERNET' "$M" || \
  perl -0pi -e 's#<application#<uses-permission android:name="android.permission.INTERNET"/>\n    <application#' "$M"
perl -0pi -e 's/android:label="[^"]*"/android:label="NUME"/' "$M"

# ── iOS ──
perl -0pi -e 's/IPHONEOS_DEPLOYMENT_TARGET = 1[0-4]\.0;/IPHONEOS_DEPLOYMENT_TARGET = 15.0;/g' ios/Runner.xcodeproj/project.pbxproj
P=ios/Runner/Info.plist
perl -0pi -e 's#(<key>CFBundleDisplayName</key>\s*<string>)[^<]*(</string>)#${1}NUME${2}#' "$P"

flutter pub get >/dev/null
dart run flutter_launcher_icons >/dev/null || echo "(icons not updated)"
echo "Platforms ready."

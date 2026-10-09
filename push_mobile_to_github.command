#!/bin/bash
# Uploads the NUME phone app (the mobile folder) to GitHub and waits for the
# build + tests. Doesn't touch the desktop release.
cd "$(dirname "$0")" || exit 1
REPO="pipilas/stamhad-staff"
API="https://api.github.com/repos/$REPO"
say() { printf "\n\033[1m%s\033[0m\n" "$1"; }
fail() { printf "\n\033[31m%s\033[0m\n" "$1"; read -r -p "Press Enter to close…"; exit 1; }

git add mobile .github/workflows/mobile.yml .github/workflows/release.yml publish_to_github.command push_mobile_to_github.command
BAD=$(git diff --cached --name-only | grep -Ei '\.(csv|stamhad|pem)$|rsa_key|google-services|GoogleService-Info')
if [ -n "$BAD" ]; then git reset -q; fail "Stopped: these shouldn't be uploaded:
$BAD"; fi
git diff --cached --quiet && say "Nothing new in the phone app." || git commit -q -m "NUME phone app" || fail "commit failed"
say "Uploading…"
git push origin main || fail "Upload failed."
SHA=$(git rev-parse HEAD)
say "GitHub is building the phone app (about 10–15 minutes)…"
open "https://github.com/$REPO/actions/workflows/mobile.yml"
for i in $(seq 1 50); do
  sleep 45
  OUT=$(curl -s -H "User-Agent: nume-push" "$API/actions/runs?head_sha=$SHA&per_page=10" | python3 -c '
import json, sys
try: runs = [r for r in json.load(sys.stdin).get("workflow_runs", []) if r.get("name") == "Mobile app"]
except Exception: runs = []
if not runs: print("waiting"); sys.exit()
r = runs[0]
print(r["status"] if r["status"] != "completed" else "done:" + str(r["conclusion"]))
')
  printf "   %s  %s\n" "$(date +%H:%M)" "$OUT"
  case "$OUT" in done:success) say "✓ Phone app built and all tests passed. The Android APK and iPhone simulator app are on the Actions page (Artifacts)."; read -r -p "Press Enter to close…"; exit 0;;
                 done:*) fail "Something failed — tell Claude (the Actions page shows which step).";; esac
done
fail "Gave up waiting — check the Actions page."

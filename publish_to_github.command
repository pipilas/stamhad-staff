#!/bin/bash
# Publish Stamhad Staff to GitHub.  Double-click this file.
#  1. uploads the code
#  2. waits for GitHub to build AND test both installers (nothing is published yet)
#  3. only if everything passed: tags the version in version.txt -> GitHub publishes the Release
#     (StamhadStaff-Setup.exe, portable .exe, Mac .pkg and .dmg). Apps then offer the update.

cd "$(dirname "$0")" || exit 1
REPO="pipilas/stamhad-staff"
URL="https://github.com/$REPO.git"
API="https://api.github.com/repos/$REPO"
V=$(tr -d '[:space:]' < version.txt)

say() { printf "\n\033[1m%s\033[0m\n" "$1"; }
fail() { printf "\n\033[31m%s\033[0m\n" "$1"; read -r -p "Press Enter to close…"; exit 1; }

say "Stamhad Staff $V → github.com/$REPO"
command -v git >/dev/null || fail "git isn't installed. Run:  xcode-select --install   then try again."

# ── the repo must exist ───────────────────────────────────────────────────────
if ! git ls-remote "$URL" >/dev/null 2>&1; then
  say "The repo doesn't exist yet. Opening GitHub so you can create it…"
  echo "   Name: stamhad-staff   ·   Public   ·   do NOT add a README / .gitignore / license"
  open "https://github.com/new?name=stamhad-staff&visibility=public"
  read -r -p "Press Enter after you've clicked “Create repository”… "
  git ls-remote "$URL" >/dev/null 2>&1 || fail "Still can't see $URL."
fi
[ -d .git ] || git init -q -b main || fail "git init failed"
git remote get-url origin >/dev/null 2>&1 || git remote add origin "$URL"
git config user.name  >/dev/null || git config user.name  "pipilas"
git config user.email >/dev/null || git config user.email "pipilas@users.noreply.github.com"

if git ls-remote --tags origin "refs/tags/v$V" | grep -q "v$V"; then
  fail "v$V is already released. For a new version: change version.txt, add a '## $V' section to CHANGELOG.md, then run this again."
fi
grep -q "^## $V" CHANGELOG.md || fail "CHANGELOG.md has no '## $V' section yet — add what's new (people see it in the update window)."

# ── never upload private data ─────────────────────────────────────────────────
git add -A
BAD=$(git diff --cached --name-only | grep -Ei '\.(csv|stamhad|stamhadtoast|pem)$|rsa_key|preset\.json|^keys/|^backups/|^logs/')
if [ -n "$BAD" ]; then git reset -q; fail "Stopped: these look like private data and must not be uploaded:
$BAD"; fi
git diff --cached --quiet || git commit -q -m "Stamhad Staff $V" || fail "commit failed"

say "Uploading the code…"
git push -u origin main || fail "Upload failed. If it asked for a password, use a GitHub token (github.com → Settings → Developer settings → Tokens)."
SHA=$(git rev-parse HEAD)

# ── wait for GitHub to build + test ──────────────────────────────────────────
say "GitHub is building and testing both installers (about 10 minutes)…"
open "https://github.com/$REPO/actions"
STATUS=""
for i in $(seq 1 40); do
  sleep 45
  OUT=$(curl -s -H "User-Agent: stamhad-publish" "$API/actions/runs?head_sha=$SHA&per_page=5" | python3 -c '
import json, sys
try:
    runs = [r for r in json.load(sys.stdin).get("workflow_runs", []) if r.get("head_branch") == "main" and r.get("name") == "Build & Release"]
except Exception:
    runs = []
if not runs: print("waiting"); sys.exit()
r = runs[0]
print(r["status"] if r["status"] != "completed" else "done:" + str(r["conclusion"]) + ":" + str(r["id"]))
')
  printf "   %s  %s\n" "$(date +%H:%M)" "$OUT"
  case "$OUT" in done:*) STATUS="$OUT"; break;; esac
done
case "$STATUS" in
  done:success:*) say "✓ All builds and installer tests passed.";;
  done:*) RUN=${STATUS##*:}
          curl -s -H "User-Agent: stamhad-publish" "$API/actions/runs/$RUN/jobs" | python3 -c '
import json, sys
for j in json.load(sys.stdin).get("jobs", []):
    bad = [s["name"] for s in j.get("steps", []) if s.get("conclusion") == "failure"]
    if bad: print("   ✗", j["name"], "→", ", ".join(bad))'
          fail "The build failed, so nothing was released. Tell Claude which step failed (shown above, details on the Actions page).";;
  *) fail "Gave up waiting. Check https://github.com/$REPO/actions and run this again when it's green.";;
esac

# ── publish ──────────────────────────────────────────────────────────────────
git tag -f "v$V" >/dev/null
git push origin "v$V" || fail "Couldn't push the tag v$V"
say "✓ Releasing v$V. In ~10 minutes the files are at: https://github.com/$REPO/releases/latest"
echo "   Running copies of the app will offer the update the next time they open."
read -r -p "Press Enter to close… "

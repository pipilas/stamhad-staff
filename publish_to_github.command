#!/bin/bash
# Publish Stamhad Staff to GitHub and start the build of the .exe and .dmg.
# Double-click this file. It uses your Mac's normal GitHub login.
#  - first time: puts the code on github.com/pipilas/stamhad-staff
#  - every time: tags the version in version.txt, which makes GitHub build
#    StamhadStaff.exe + the .dmg and publish them as a release.

cd "$(dirname "$0")" || exit 1
REPO="pipilas/stamhad-staff"
URL="https://github.com/$REPO.git"
V=$(tr -d '[:space:]' < version.txt)

say() { printf "\n\033[1m%s\033[0m\n" "$1"; }
fail() { printf "\n\033[31m%s\033[0m\n" "$1"; read -r -p "Press Enter to close…"; exit 1; }

say "Stamhad Staff $V → github.com/$REPO"

command -v git >/dev/null || fail "git isn't installed. Run:  xcode-select --install   then try again."

# 1. the repo must exist on GitHub
if ! git ls-remote "$URL" >/dev/null 2>&1; then
  say "The repo doesn't exist yet. Opening GitHub so you can create it…"
  echo "   Name: stamhad-staff   ·   Public   ·   do NOT add a README / .gitignore / license"
  open "https://github.com/new?name=stamhad-staff&visibility=public&description=Stamhad%20Staff%20-%20schedule%2C%20hours%20%26%20tips%2C%20inventory"
  read -r -p "Press Enter after you've clicked “Create repository”… "
  git ls-remote "$URL" >/dev/null 2>&1 || fail "Still can't see $URL. Check the name and that you're signed in as pipilas."
fi

# 2. local git setup (once)
if [ ! -d .git ]; then
  git init -q -b main || fail "git init failed"
fi
git remote get-url origin >/dev/null 2>&1 || git remote add origin "$URL"
git config user.name  >/dev/null || git config user.name  "pipilas"
git config user.email >/dev/null || git config user.email "pipilas@users.noreply.github.com"

# 3. safety: never upload restaurant data or keys (.gitignore covers these; double-check)
git add -A
BAD=$(git diff --cached --name-only | grep -Ei '\.(csv|stamhad|stamhadtoast|pem)$|rsa_key|preset\.json|^keys/|^backups/|^logs/')
if [ -n "$BAD" ]; then
  git reset -q
  fail "Stopped: these files look like private data and must not be uploaded:
$BAD"
fi
git diff --cached --quiet || git commit -q -m "Stamhad Staff $V" || fail "commit failed"

# 4. push the code
say "Uploading the code…"
git push -u origin main || fail "Upload failed. If it asks for a password, use a GitHub token (github.com → Settings → Developer settings → Tokens)."

# 5. tag → GitHub builds and publishes the release
if git ls-remote --tags origin "refs/tags/v$V" | grep -q "v$V"; then
  say "v$V is already released. To release a new version: change version.txt, add a ## section to CHANGELOG.md, run this again."
else
  git tag -f "v$V" >/dev/null
  git push origin "v$V" || fail "Couldn't push the tag v$V"
  say "✓ Done. GitHub is now building the Windows .exe and the Mac .dmg (about 10 minutes)."
  echo "   When it's green, the files are at: https://github.com/$REPO/releases/latest"
  open "https://github.com/$REPO/actions"
fi
read -r -p "Press Enter to close… "

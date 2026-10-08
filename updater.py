"""Check GitHub for a newer Stamhad Staff, ask, and install it safely.

Safety steps (so an update can't leave you with a broken app):
  1. Download to a temp file and check its size and SHA-256 (from SHA256SUMS.txt
     in the release). A bad download is thrown away; the app is untouched.
  2. Back up the data folder (zip) before touching anything.
  3. Mac: the new .app is copied out of the .dmg and checked BEFORE the app quits.
  4. A small helper waits until this app has closed, moves the old app aside,
     puts the new one in place and starts it. If anything fails it puts the old
     app back and starts that instead.
  5. On the next start the app reports whether the update worked.
Your data lives in a separate folder and is never touched by an update.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import ssl
import subprocess
import sys
import tempfile
import time
import urllib.request
import zipfile
from datetime import datetime
from pathlib import Path

REPO = "pipilas/stamhad-staff"
API_LATEST = f"https://api.github.com/repos/{REPO}/releases/latest"
RELEASES_PAGE = f"https://github.com/{REPO}/releases/latest"
APP_NAME = "Stamhad Staff"
EXE_NAME = "StamhadStaff.exe"
SUMS_NAME = "SHA256SUMS.txt"
IS_MAC = platform.system() == "Darwin"
IS_WIN = platform.system() == "Windows"


# ── versions ────────────────────────────────────────────────────────────────
def parse_version(v) -> tuple:
    out = []
    for p in str(v or "").strip().lstrip("vV").split("."):
        num = "".join(ch for ch in p if ch.isdigit())
        out.append(int(num) if num else 0)
    while len(out) < 3:
        out.append(0)
    return tuple(out[:3])


def is_newer(latest, current) -> bool:
    return parse_version(latest) > parse_version(current)


# ── network ─────────────────────────────────────────────────────────────────
def _ctx():
    try:
        import certifi  # bundled in the built app: avoids "certificate verify failed" on Mac
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


def _get(url, timeout=15, accept="application/vnd.github+json"):
    req = urllib.request.Request(url, headers={"User-Agent": "StamhadStaff-Updater", "Accept": accept})
    return urllib.request.urlopen(req, timeout=timeout, context=_ctx())


def check(current: str) -> dict:
    """-> {"available": bool, "version", "notes", "url", "size", "sha256", "name", "page"}.
    Raises ConnectionError if GitHub can't be reached."""
    try:
        with _get(API_LATEST) as r:
            rel = json.loads(r.read().decode("utf-8"))
    except Exception as e:
        raise ConnectionError(f"Can't reach GitHub ({e})") from e
    ver = str(rel.get("tag_name", "")).lstrip("vV")
    assets = rel.get("assets") or []
    asset = pick_asset(assets, ver, install_target()[0])
    info = {"available": False, "version": ver, "notes": (rel.get("body") or "").strip(),
            "page": rel.get("html_url") or RELEASES_PAGE, "url": "", "size": 0, "sha256": "", "name": ""}
    if not asset:
        return info
    info.update(url=asset["browser_download_url"], size=int(asset.get("size") or 0), name=asset["name"])
    dig = str(asset.get("digest") or "")
    if dig.startswith("sha256:"):
        info["sha256"] = dig.split(":", 1)[1]
    sums = next((a for a in assets if a.get("name") == SUMS_NAME), None)
    if sums and not info["sha256"]:
        try:
            with _get(sums["browser_download_url"], accept="application/octet-stream") as r:
                for line in r.read().decode("utf-8", "replace").splitlines():
                    parts = line.split()
                    if len(parts) >= 2 and parts[-1].lstrip("*") == asset["name"]:
                        info["sha256"] = parts[0].lower()
        except Exception:
            pass
    info["available"] = is_newer(ver, current)
    return info


def pick_asset(assets, ver, kind):
    """Which release file this copy of the app needs.
    mac -> the .dmg   ·   win-installed -> StamhadStaff-Setup.exe   ·   win (portable) -> the portable .exe"""
    def named(pred):
        c = [a for a in assets if pred(a.get("name", "").lower())]
        return next((a for a in c if ver and ver in a.get("name", "")), None) or (c[0] if c else None)
    if IS_MAC:
        return named(lambda n: n.endswith(".dmg"))
    if kind == "win-installed":
        return named(lambda n: n.endswith(".exe") and "setup" in n)
    return named(lambda n: n.endswith(".exe") and "setup" not in n)


def download(info: dict, progress=None, tries=3) -> Path:
    """Download to temp with size + SHA-256 check. Retries; raises on failure."""
    dest = Path(tempfile.gettempdir()) / "StamhadStaffUpdate"
    dest.mkdir(exist_ok=True)
    final = dest / info["name"]
    last = None
    for attempt in range(1, tries + 1):
        part = final.with_suffix(final.suffix + ".part")
        try:
            sha = hashlib.sha256()
            got = 0
            with _get(info["url"], timeout=60, accept="application/octet-stream") as r, open(part, "wb") as f:
                total = int(r.headers.get("Content-Length") or info.get("size") or 0)
                while True:
                    chunk = r.read(256 * 1024)
                    if not chunk:
                        break
                    f.write(chunk)
                    sha.update(chunk)
                    got += len(chunk)
                    if progress:
                        progress(got, total)
            if info.get("size") and got != info["size"]:
                raise IOError(f"download incomplete ({got} of {info['size']} bytes)")
            if info.get("sha256") and sha.hexdigest().lower() != info["sha256"].lower():
                raise IOError("download is damaged (checksum doesn't match)")
            if final.exists():
                final.unlink()
            part.replace(final)
            return final
        except Exception as e:
            last = e
            try:
                part.unlink()
            except Exception:
                pass
            time.sleep(1.5 * attempt)
    raise IOError(f"Download failed after {tries} tries: {last}")


# ── where is the running app? ───────────────────────────────────────────────
def install_target() -> tuple[str, Path | None, str]:
    """-> (kind, path, problem). kind: 'win' | 'mac' | 'source'. problem = '' when we can update in place."""
    if not getattr(sys, "frozen", False):
        return "source", None, "You're running the app from its Python files, not the installed app."
    if IS_WIN:
        exe = Path(sys.executable).resolve()
        if (exe.parent / "unins000.exe").exists():           # installed with StamhadStaff-Setup.exe
            return "win-installed", exe, ""
        return "win", exe, ("" if _writable(exe.parent) else f"Can't write to {exe.parent}")
    if IS_MAC:
        app = Path(sys.executable).resolve().parents[2]          # X.app/Contents/MacOS/X
        s = str(app)
        if "AppTranslocation" in s or s.startswith("/Volumes/"):
            return "mac", app, ("The app is running from the download / disk image. Drag Stamhad Staff "
                                "into the Applications folder, open it from there, then update.")
        return "mac", app, ("" if _writable(app.parent) else f"Can't write to {app.parent}")
    return "source", None, "Updates are only for the Windows and Mac apps."


def _writable(folder: Path) -> bool:
    try:
        t = folder / f".stamhad-write-test-{os.getpid()}"
        t.write_text("x")
        t.unlink()
        return True
    except Exception:
        return False


# ── data backup ─────────────────────────────────────────────────────────────
def backup_data(root: Path, reason="update") -> Path:
    bdir = Path(root) / "backups"
    bdir.mkdir(exist_ok=True)
    out = bdir / f"{reason}-{datetime.now():%Y%m%d-%H%M%S}.zip"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for p in Path(root).rglob("*"):
            rel = p.relative_to(root)
            if p.is_file() and rel.parts[0] not in ("backups", "logs") and p.suffix != ".tmp":
                z.write(p, rel.as_posix())
    olds = sorted(bdir.glob("*.zip"))
    for p in olds[:-15]:                      # keep the last 15 backups
        try:
            p.unlink()
        except Exception:
            pass
    return out


# ── install ─────────────────────────────────────────────────────────────────
def prepare_and_launch(pkg: Path, root: Path, version: str, status=None) -> None:
    """Get everything ready and start the helper. The caller must then quit the app
    right away (the helper waits for it to close)."""
    status = status or (lambda m: None)
    kind, target, problem = install_target()
    if problem:
        raise RuntimeError(problem)
    result_file = Path(root) / "update-result.json"
    log_file = Path(root) / "logs" / "update.log"
    log_file.parent.mkdir(exist_ok=True)
    result_file.write_text(json.dumps({"to": version, "status": "started",
                                       "at": datetime.now().isoformat(timespec="seconds")}))
    before = log_file.stat().st_size if log_file.exists() else 0
    if kind == "win-installed":
        marker = _launch_windows_setup(pkg, target, result_file, log_file, version)
        started = lambda: marker.exists()                                   # Setup writes its log at once
    elif kind == "win":
        _launch_windows(pkg, target, result_file, log_file, version)
        started = lambda: log_file.exists() and log_file.stat().st_size > before
    else:
        _launch_mac(pkg, target, result_file, log_file, version, status)
        started = lambda: log_file.exists() and log_file.stat().st_size > before
    # Don't quit until the updater is really running; otherwise the app would just vanish.
    status("Starting the updater\u2026")
    for _ in range(60):                     # up to 15 s
        if started():
            return
        time.sleep(0.25)
    try:
        result_file.unlink()
    except Exception:
        pass
    raise RuntimeError("The updater didn't start (it may have been blocked by antivirus). "
                       "Nothing was changed. You can install the new version yourself from the download page.")


def _log_line(logf: Path, msg: str):
    try:
        with open(logf, "a", encoding="utf-8") as f:
            f.write(f"{datetime.now():%Y-%m-%dT%H:%M:%S}  {msg}\n")
    except Exception:
        pass


def _launch_windows(new_exe: Path, exe: Path, result: Path, logf: Path, version: str):
    pids = [os.getpid()]
    try:
        pids.append(os.getppid())          # the one-file launcher process
    except Exception:
        pass
    ps = Path(tempfile.gettempdir()) / "StamhadStaffUpdate" / "install-update.ps1"

    def q(p):
        return "'" + str(p).replace("'", "''") + "'"
    ps.write_text(f"""
$ErrorActionPreference = 'Stop'
$exe = {q(exe)}; $new = {q(new_exe)}; $bak = $exe + '.old'; $log = {q(logf)}; $res = {q(result)}
function Write-UpdLog($m) {{ try {{ Add-Content -Path $log -Encoding UTF8 -Value ((Get-Date -Format s) + '  ' + $m) }} catch {{}} }}
function Set-UpdResult($s, $m) {{ Set-Content -Path $res -Encoding UTF8 -Value ('{{"to": "{version}", "status": "' + $s + '", "detail": "' + ($m -replace '"', "'") + '"}}') }}
Write-UpdLog 'update to {version}: waiting for the app to close'
foreach ($p in @({",".join(str(p) for p in pids)})) {{ try {{ Wait-Process -Id $p -Timeout 90 -ErrorAction SilentlyContinue }} catch {{}} }}
Start-Sleep -Milliseconds 800
$moved = $false
for ($i = 0; $i -lt 60; $i++) {{
  try {{ if (Test-Path $bak) {{ Remove-Item $bak -Force }}; Move-Item $exe $bak -Force; $moved = $true; break }}
  catch {{ Start-Sleep -Milliseconds 500 }}
}}
if (-not $moved) {{ Write-UpdLog 'could not move the old app (still in use)'; Set-UpdResult 'failed' 'The old app was still in use.'; Start-Process $exe; exit 1 }}
try {{
  Copy-Item $new $exe -Force
  try {{ Unblock-File $exe }} catch {{}}
  if ((Get-Item $exe).Length -ne (Get-Item $new).Length) {{ throw 'copied file has the wrong size' }}
}} catch {{
  Write-UpdLog ('install failed: ' + $_); try {{ Remove-Item $exe -Force }} catch {{}}
  try {{ Move-Item $bak $exe -Force }} catch {{ Write-UpdLog ('could not put the old app back: ' + $_) }}
  Set-UpdResult 'failed' ('' + $_); Start-Process $exe; exit 1
}}
Write-UpdLog 'installed, starting new version'; Set-UpdResult 'ok' ''
Start-Process $exe
Start-Sleep -Seconds 2
try {{ Remove-Item $new -Force }} catch {{}}
""", encoding="utf-8-sig")      # BOM: PowerShell 5 reads non-English paths correctly
    # Own hidden console (CREATE_NO_WINDOW) in its own group. NOT DETACHED_PROCESS: PowerShell
    # without any console can fail to start, which is what broke the 0.7.1 updater.
    flags = 0x00000200 | 0x08000000                 # NEW_PROCESS_GROUP | NO_WINDOW
    subprocess.Popen(["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                      "-File", str(ps)], creationflags=flags, close_fds=True)
    return logf


def _launch_windows_setup(setup: Path, exe: Path, result: Path, logf: Path, version: str):
    """Installed copy: start the new StamhadStaff-Setup.exe directly (no script in between).
    /UPDATE=1 makes Setup reopen the app when it's done; /RESULT tells it where to report.
    Setup closes this app itself (Restart Manager) and undoes its own changes if it fails."""
    setup_log = logf.parent / "setup.log"
    try:
        if setup_log.exists():
            setup_log.unlink()
    except Exception:
        pass
    _log_line(logf, f"update to {version} (installer): starting {setup.name}")
    subprocess.Popen([str(setup), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/CLOSEAPPLICATIONS",
                      "/UPDATE=1", f"/RESULT={result}", f"/LOG={setup_log}"],
                     creationflags=0x00000008 | 0x00000200, close_fds=True)   # DETACHED | NEW_PROCESS_GROUP
    return setup_log


def _launch_mac(dmg: Path, app: Path, result: Path, logf: Path, version: str, status):
    stage = Path(tempfile.gettempdir()) / "StamhadStaffUpdate" / "stage"
    shutil.rmtree(stage, ignore_errors=True)
    stage.mkdir(parents=True)
    status("Opening the disk image…")
    r = subprocess.run(["hdiutil", "attach", str(dmg), "-nobrowse", "-noautoopen", "-plist"],
                       capture_output=True, timeout=120)
    if r.returncode != 0:
        raise RuntimeError(f"Couldn't open the disk image: {r.stderr.decode(errors='replace')[:200]}")
    import plistlib
    mounts = [e.get("mount-point") for e in plistlib.loads(r.stdout).get("system-entities", []) if e.get("mount-point")]
    if not mounts:
        raise RuntimeError("The disk image didn't mount.")
    mnt = mounts[0]
    try:
        src = next((Path(mnt) / n for n in os.listdir(mnt) if n.endswith(".app")), None)
        if not src:
            raise RuntimeError("No app found inside the disk image.")
        status("Copying the new version…")
        new_app = stage / app.name
        c = subprocess.run(["ditto", str(src), str(new_app)], capture_output=True, timeout=300)
        if c.returncode != 0:
            raise RuntimeError(f"Copy failed: {c.stderr.decode(errors='replace')[:200]}")
    finally:
        subprocess.run(["hdiutil", "detach", mnt, "-quiet", "-force"], capture_output=True, timeout=60)
    # check the copy before we quit
    import plistlib as _pl
    try:
        info = _pl.loads((new_app / "Contents" / "Info.plist").read_bytes())
        exe = new_app / "Contents" / "MacOS" / info["CFBundleExecutable"]
        if not exe.exists():
            raise RuntimeError("the program file is missing")
    except Exception as e:
        raise RuntimeError(f"The new app looks damaged ({e}).")
    subprocess.run(["xattr", "-dr", "com.apple.quarantine", str(new_app)], capture_output=True)
    sh = stage.parent / "install-update.sh"

    def q(p):
        return "'" + str(p).replace("'", "'\\''") + "'"
    sh.write_text(f"""#!/bin/bash
APP={q(app)}; NEW={q(new_app)}; BAK="$APP.previous"; LOG={q(logf)}; RES={q(result)}
w() {{ echo "$(date '+%Y-%m-%dT%H:%M:%S')  $1" >> "$LOG"; }}
r() {{ printf '{{"to": "{version}", "status": "%s", "detail": "%s"}}' "$1" "$2" > "$RES"; }}
exec 2>>"$LOG"            # any error message from mv/ditto/open goes into update.log
w "update to {version}: waiting for the app to close (user $(id -un), app owner $(stat -f %Su "$APP" 2>/dev/null))"
for i in $(seq 1 180); do kill -0 {os.getpid()} 2>/dev/null || break; sleep 0.5; done
sleep 1
rm -rf "$BAK"
if ! mv "$APP" "$BAK"; then w "could not move the old app"; r failed "could not move the old app"; open "$APP"; exit 1; fi
if ditto "$NEW" "$APP" && [ -d "$APP/Contents/MacOS" ]; then
  xattr -dr com.apple.quarantine "$APP" 2>/dev/null
  w "installed, starting new version"; r ok ""
  rm -rf "$BAK" "$NEW"
  open "$APP"
else
  w "install failed, putting the old version back"; rm -rf "$APP"; mv "$BAK" "$APP"
  r failed "copy into place failed"; open "$APP"; exit 1
fi
""")
    os.chmod(sh, 0o755)
    subprocess.Popen(["/bin/bash", str(sh)], start_new_session=True, close_fds=True,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return logf


# ── after a restart ─────────────────────────────────────────────────────────
def startup_cleanup(root: Path) -> dict | None:
    """Remove leftovers; return the result of the last update (once), if any."""
    kind, target, _ = install_target()
    if kind in ("win", "win-installed") and target:
        old = Path(str(target) + ".old")
        try:
            if old.exists():
                old.unlink()
        except Exception:
            pass
    rf = Path(root) / "update-result.json"
    if not rf.exists():
        return None
    try:
        res = json.loads(rf.read_text(encoding="utf-8-sig", errors="replace"))
    except Exception:
        res = {"status": "unknown"}
    try:
        rf.unlink()
    except Exception:
        pass
    return res

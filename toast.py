"""
Stamhad Staff — Toast time-entry import.

Reads Toast "TimeEntries" CSVs (manual export or the nightly SFTP export) and
turns them into editable day entries. Nothing is saved until the user confirms
the preview, and every imported value stays editable afterwards.
"""

from __future__ import annotations

import csv
import json
import os
import io
from pathlib import Path

from core import detect_shift, norm_time, to_float
from store import gen_id, payroll_data_dir, data_dir


def parse_csv_text(text: str) -> list[dict]:
    """-> [{"name", "job", "time_in", "time_out", "hours"}]"""
    rows = list(csv.reader(io.StringIO(text)))
    if len(rows) < 2:
        return []
    header = [h.strip().lower() for h in rows[0]]

    def col(*names):
        for n in names:
            if n in header:
                return header.index(n)
        return -1

    i_emp = col("employee", "employee name")
    i_job = col("job title", "job")
    i_in = col("in date", "time in", "clock in")
    i_out = col("out date", "time out", "clock out")
    i_hrs = col("payable hours", "total hours", "regular hours")

    def g(r, i):
        return r[i].strip() if 0 <= i < len(r) else ""

    out = []
    for r in rows[1:]:
        name = g(r, i_emp)
        if not name:
            continue
        out.append({
            "name": name, "job": g(r, i_job),
            "time_in": norm_time(g(r, i_in)), "time_out": norm_time(g(r, i_out)),
            "hours": to_float(g(r, i_hrs), 0.0) or 0.0,
        })
    return out


def parse_csv_file(path) -> list[dict]:
    with open(path, newline="", encoding="utf-8-sig") as f:
        return parse_csv_text(f.read())


# ── name matching ───────────────────────────────────────────────────────────
def _norm(name: str) -> str:
    name = name.strip().strip('"')
    if "," in name:
        last, first = name.split(",", 1)
        name = f"{first.strip()} {last.strip()}"
    return " ".join(name.lower().split())


def match_employee(toast_name: str, employees: list[dict]):
    n = _norm(toast_name)
    for e in employees:
        if e.get("toast_name") and _norm(e["toast_name"]) == n:
            return e
    for e in employees:
        if _norm(e["name"]) == n:
            return e
    parts = n.split()
    for e in employees:
        ep = _norm(e["name"]).split()
        if len(parts) >= 2 and len(ep) >= 2 and parts[0] == ep[0] and parts[-1] == ep[-1]:
            return e
    # reversed order ("Beltran Isael" vs "Isael Beltran")
    for e in employees:
        if sorted(_norm(e["name"]).split()) == sorted(parts):
            return e
    return None


def display_name(raw: str) -> str:
    """'BONILLA FERNANDO, EFRAIN' -> 'Efrain Bonilla Fernando'."""
    raw = " ".join(raw.strip().strip('"').split())
    if "," in raw:
        last, first = raw.split(",", 1)
        raw = f"{first.strip()} {last.strip()}"
    if raw.isupper() or raw.islower():
        raw = " ".join(w.capitalize() for w in raw.split())
    return raw


def map_job(job: str, settings: dict, positions: list[dict]) -> str:
    """Toast job title -> one of our positions (learned map first, then same name)."""
    if not job:
        return ""
    jm = settings.get("job_map", {})
    if job.lower() in jm:
        return jm[job.lower()]
    for p in positions:
        if p["name"].lower() == job.lower():
            return p["name"]
    return ""


def pick_position(emp: dict, job: str, shift: str, settings: dict | None = None,
                  positions: list[dict] | None = None) -> str:
    pos = emp.get("positions", [])
    chosen = ""
    if job:
        mapped = map_job(job, settings or {}, positions or []) or job
        chosen = next((p for p in pos if p.lower() in (job.lower(), mapped.lower())), "")
    if not chosen:
        main = emp.get("main_position")
        chosen = main if main and main in pos else (pos[0] if pos else job)
    # prefer a "(Morning)" variant for day shifts if the employee has one
    if shift != "Dinner" and chosen:
        base = chosen.lower().split("(")[0].strip()
        for q in pos:
            if "(morning)" in q.lower() and q.lower().startswith(base):
                return q
    return chosen


def rows_to_entries(rows: list[dict], employees: list[dict], day: str, settings: dict,
                    positions: list[dict] | None = None) -> list[dict]:
    """Preview rows -> entries (unmatched rows keep emp_id None)."""
    positions = positions or []
    out = []
    for r in rows:
        emp = match_employee(r["name"], employees)
        shift = detect_shift(r["time_in"], day, settings, r["time_out"])
        if emp:
            pos = pick_position(emp, r["job"], shift, settings, positions)
        else:
            pos = map_job(r["job"], settings, positions) or r["job"]
        out.append({
            "id": gen_id(), "emp_id": emp["id"] if emp else None,
            "toast_raw_name": r["name"], "toast_job": r["job"],
            "position": pos, "shift": shift, "time_in": r["time_in"], "time_out": r["time_out"],
            "toast_hours": r["hours"], "toast_in": r["time_in"], "toast_out": r["time_out"],
            "source": "toast",
        })
    return out


# ── SFTP ────────────────────────────────────────────────────────────────────
def find_key(settings: dict) -> Path | None:
    cands = []
    if settings.get("toast", {}).get("key_path"):
        cands.append(Path(settings["toast"]["key_path"]))
    cands += [data_dir() / "keys" / "toast_rsa_key",
              Path.home() / "toast_rsa_key",
              Path.home() / ".ssh" / "toast_rsa_key",
              payroll_data_dir() / "keys" / "toast_rsa_key",
              payroll_data_dir() / "toast_rsa_key"]
    for c in cands:
        if c.exists():
            return c
    return None


SETUP_EXT = ".stamhadtoast"


def _looks_like_private_key(text: str) -> bool:
    return "PRIVATE KEY" in text and "BEGIN" in text


def install_key_text(text: str) -> Path:
    """Save a private key into the app's own folder (so no path needs to match between PCs)."""
    if not _looks_like_private_key(text):
        raise ValueError("That isn't a private SSH key.\nPick the file WITHOUT .pub at the end.")
    dest = data_dir() / "keys" / "toast_rsa_key"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(text if text.endswith("\n") else text + "\n", encoding="utf-8")
    try:
        os.chmod(dest, 0o600)
    except OSError:
        pass
    return dest


def install_key_file(src) -> Path:
    return install_key_text(Path(src).read_text(encoding="utf-8", errors="ignore"))


def export_setup(settings: dict, key_path: Path, out_path):
    t = settings.get("toast", {})
    data = {"type": "stamhad-toast-setup", "version": 1,
            "host": t.get("host", ""), "port": t.get("port", 22),
            "username": t.get("username", ""), "export_id": t.get("export_id", ""),
            "key": Path(key_path).read_text(encoding="utf-8", errors="ignore")}
    Path(out_path).write_text(json.dumps(data, indent=2), encoding="utf-8")
    try:
        os.chmod(out_path, 0o600)
    except OSError:
        pass


def import_setup(path, settings: dict) -> Path:
    """Load a setup file: installs the key and fills in host / username / export ID."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("type") != "stamhad-toast-setup":
        raise ValueError("That isn't a Stamhad Toast setup file.")
    dest = install_key_text(data["key"])
    t = settings.setdefault("toast", {})
    for k in ("host", "port", "username", "export_id"):
        if data.get(k):
            t[k] = data[k]
    t["key_path"] = str(dest)
    return dest


def load_key_or_setup(path, settings: dict) -> Path:
    """Accept either a setup file or a raw private key file."""
    p = Path(path)
    if p.suffix == SETUP_EXT or p.read_text(encoding="utf-8", errors="ignore").lstrip().startswith("{"):
        return import_setup(p, settings)
    dest = install_key_file(p)
    settings.setdefault("toast", {})["key_path"] = str(dest)
    return dest


def sftp_download(settings: dict, key_path: Path, yyyymmdd: str) -> str:
    import paramiko  # imported lazily so the app runs without it
    t = settings["toast"]
    pkey = paramiko.RSAKey.from_private_key_file(str(key_path))
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(hostname=t["host"], port=int(t.get("port", 22)), username=t["username"],
                   pkey=pkey, look_for_keys=False, allow_agent=False, timeout=30)
    try:
        sftp = client.open_sftp()
        folder = str(t.get("export_id", "")).strip("/ ")
        try:
            folders = [f for f in sftp.listdir("/") if not f.startswith(".")]
        except Exception:
            folders = []
        if folders and folder not in folders:
            if len(folders) == 1:
                folder = folders[0]                 # only one restaurant on this login -> use it
                t["export_id"] = folder
            else:
                raise FileNotFoundError(f"Export ID \u201c{folder}\u201d isn't on this Toast login.\n"
                                        f"Folders there: {', '.join(folders)}\n"
                                        "Put the right one in Settings \u2192 Toast \u2192 Export ID.")
        remote = f"/{folder}/{yyyymmdd}/TimeEntries.csv"
        try:
            sftp.stat(remote)
        except FileNotFoundError:
            # explain what IS there, so it's clear what's wrong
            def ls(path):
                try:
                    return sorted(x for x in sftp.listdir(path) if not x.startswith("."))
                except Exception:
                    return None
            root = ls("/")
            dates = ls(f"/{folder}")
            files = ls(f"/{folder}/{yyyymmdd}")
            lines = [f"No TimeEntries.csv for that day on Toast.", f"Looked for: {remote}", ""]
            if dates is None:
                lines.append(f"There is no folder \u201c{folder}\u201d on this Toast login.")
                lines.append(f"Folders there: {', '.join(root) if root else '(none yet)'}")
                lines.append("If it's empty, Toast data exports may not be switched on yet, "
                             "or the first files come tonight.")
            elif not dates:
                lines.append(f"Folder {folder} is empty \u2014 Toast builds the first export overnight.")
            else:
                pretty = [f"{d[4:6]}/{d[6:8]}" if len(d) == 8 and d.isdigit() else d for d in dates[-10:]]
                lines.append(f"Days available: {', '.join(pretty)}")
                if files is not None:
                    lines.append(f"Files for that day: {', '.join(files) if files else '(none)'}")
            raise FileNotFoundError("\n".join(lines))
        with sftp.open(remote, "r") as f:
            return f.read().decode("utf-8-sig")
    finally:
        client.close()

"""Share / Receive / Sync — move all the app's data between computers as ONE file.

Share   -> "<name>.stamhad" (a zip): employees, positions, schedule/hours/tips weeks,
           inventory, settings and the error log. The Toast key is never included.
Receive -> open a .stamhad file. Your current data is backed up first, then:
           Replace = make this computer exactly like the file (Toast connection kept),
           Sync    = merge: add what's missing; where both have the same thing,
                     the one changed more recently wins. Sync never deletes.
"""

from __future__ import annotations

import copy
import json
import platform
import socket
import zipfile
from datetime import datetime
from pathlib import Path

EXT = ".stamhad"
KIND = "stamhad-staff-data"
DATA_FILES = ("settings.json", "employees.json", "positions.json", "inventory.json")
LOCAL_SETTINGS = ("toast", "applied_presets", "update_check", "skipped_version")   # stay per-computer


def _computer():
    try:
        return socket.gethostname().split(".")[0]
    except Exception:
        return "computer"


def _data_paths(root: Path):
    for n in DATA_FILES:
        p = root / n
        if p.exists():
            yield n, p
    for p in sorted((root / "weeks").glob("*.json")):
        yield f"weeks/{p.name}", p


def default_name() -> str:
    return f"NUME {_computer()} {datetime.now():%Y-%m-%d %H%M}{EXT}"


# ── share ───────────────────────────────────────────────────────────────────
def make_package(store, dest: Path, version: str, note: str = "") -> dict:
    root = Path(store.root)
    mtimes, counts = {}, {}
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as z:
        for rel, p in _data_paths(root):
            if rel == "settings.json":
                s = json.loads(p.read_text(encoding="utf-8"))
                (s.get("toast") or {}).pop("key_path", None)          # never share where the key is
                z.writestr("data/settings.json", json.dumps(s, indent=2, ensure_ascii=False))
            else:
                z.write(p, "data/" + rel)
            mtimes[rel] = p.stat().st_mtime
        for p in sorted((root / "logs").glob("*.log*")):
            z.write(p, "logs/" + p.name)
        counts = {"employees": len(store.employees), "positions": len(store.positions),
                  "weeks": len([r for r in mtimes if r.startswith("weeks/")])}
        man = {"kind": KIND, "app_version": version, "created": datetime.now().isoformat(timespec="seconds"),
               "computer": _computer(), "os": f"{platform.system()} {platform.release()}",
               "note": note, "counts": counts, "mtimes": mtimes}
        z.writestr("manifest.json", json.dumps(man, indent=2))
    return man


# ── receive ─────────────────────────────────────────────────────────────────
class Package:
    def __init__(self, path: Path):
        self.path = Path(path)
        try:
            self.z = zipfile.ZipFile(self.path)
            self.man = json.loads(self.z.read("manifest.json"))
        except Exception as e:
            raise ValueError(f"This isn't a NUME file ({e}).") from e
        if self.man.get("kind") != KIND:
            raise ValueError("This file wasn't made by NUME → Share files.")
        self.files = {n[5:]: n for n in self.z.namelist() if n.startswith("data/") and n.endswith(".json")}

    def json(self, rel, default=None):
        n = self.files.get(rel)
        if not n:
            return default
        try:
            return json.loads(self.z.read(n).decode("utf-8"))
        except Exception:
            return default

    def mtime(self, rel) -> float:
        return float((self.man.get("mtimes") or {}).get(rel, 0))

    def weeks(self):
        return sorted(r for r in self.files if r.startswith("weeks/"))

    def logs(self):
        return [n for n in self.z.namelist() if n.startswith("logs/")]

    def extract_logs(self, folder: Path) -> Path:
        out = Path(folder) / f"logs from {self.man.get('computer', 'other')} {self.man.get('created', '')[:10]}"
        out.mkdir(parents=True, exist_ok=True)
        for n in self.logs():
            (out / Path(n).name).write_bytes(self.z.read(n))
        return out

    def close(self):
        self.z.close()


def compare(store, pkg: Package) -> list[str]:
    """Short lines describing what's in the file vs this computer."""
    root = Path(store.root)
    emp = pkg.json("employees.json", []) or []
    here_ids = {e["id"] for e in store.employees}
    new_emp = [e for e in emp if e.get("id") not in here_ids]
    lines = [f"From {pkg.man.get('computer', '?')}  ·  {pkg.man.get('created', '')[:16].replace('T', ' ')}"
             f"  ·  app {pkg.man.get('app_version', '?')}"]
    if pkg.man.get("note"):
        lines.append(f"Note: {pkg.man['note']}")
    lines.append(f"Employees: {len(emp)} in the file, {len(store.employees)} here"
                 + (f"  ({len(new_emp)} not here yet)" if new_emp else ""))
    wk = pkg.weeks()
    here_wk = {f"weeks/{p.name}" for p in (root / "weeks").glob("*.json")}
    newer = [r for r in wk if r in here_wk and pkg.mtime(r) > (root / r).stat().st_mtime + 1]
    only = [r for r in wk if r not in here_wk]
    lines.append(f"Weeks: {len(wk)} in the file  ·  {len(only)} not here  ·  {len(newer)} changed there more recently")
    inv = pkg.json("inventory.json", {}) or {}
    lines.append(f"Inventory: {len(inv.get('items', []))} items, {len(inv.get('orders', []))} past orders")
    if pkg.logs():
        lines.append(f"Includes the error log ({len(pkg.logs())} file{'s' if len(pkg.logs()) != 1 else ''})")
    return lines


def _write(root: Path, rel: str, data, mtime: float | None = None):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(p)


def _keep_local_settings(incoming: dict, local: dict) -> dict:
    out = copy.deepcopy(incoming)
    for k in LOCAL_SETTINGS:
        if k in local:
            out[k] = copy.deepcopy(local[k])
        else:
            out.pop(k, None)
    return out


def replace_all(store, pkg: Package) -> str:
    root = Path(store.root)
    local_settings = json.loads((root / "settings.json").read_text(encoding="utf-8")) \
        if (root / "settings.json").exists() else {}
    for rel in pkg.files:
        data = pkg.json(rel)
        if data is None:
            continue
        if rel == "settings.json":
            data = _keep_local_settings(data, local_settings)
        _write(root, rel, data)
    incoming_weeks = set(pkg.weeks())
    removed = 0
    for p in (root / "weeks").glob("*.json"):
        if f"weeks/{p.name}" not in incoming_weeks:
            p.rename(p.with_suffix(".json.replaced"))          # kept on disk, just not used
            removed += 1
    return f"Replaced with the data from {pkg.man.get('computer', 'the file')}." + \
        (f" {removed} week(s) that weren't in the file were set aside." if removed else "")


def _merge_list(here, there, key, there_newer):
    """Union by key; when both have it, the newer side's version wins."""
    out = [copy.deepcopy(x) for x in here]
    idx = {x.get(key): i for i, x in enumerate(out) if x.get(key) is not None}
    added = changed = 0
    for x in there:
        k = x.get(key)
        if k is None:
            continue
        if k not in idx:
            out.append(copy.deepcopy(x))
            idx[k] = len(out) - 1
            added += 1
        elif there_newer and out[idx[k]] != x:
            out[idx[k]] = copy.deepcopy(x)
            changed += 1
    return out, added, changed


def _empty_day(d):
    return not d or (not d.get("entries") and not any(
        (v or {}).get("floor") or (v or {}).get("bar") for v in (d.get("tips") or {}).values()))


def _merge_week(here: dict, there: dict, there_newer: bool) -> dict:
    out = copy.deepcopy(here)
    for part in ("schedule", "days"):
        out.setdefault(part, {})
        for day, val in (there.get(part) or {}).items():
            mine = out[part].get(day)
            empty_mine = (not mine) if part == "schedule" else _empty_day(mine)
            empty_theirs = (not val) if part == "schedule" else _empty_day(val)
            if empty_theirs:
                continue
            if empty_mine or there_newer:
                out[part][day] = copy.deepcopy(val)
    out.setdefault("adjustments", {})
    for k, v in (there.get("adjustments") or {}).items():
        if k not in out["adjustments"] or there_newer:
            out["adjustments"][k] = copy.deepcopy(v)
    return out


def sync(store, pkg: Package) -> str:
    root = Path(store.root)
    report = []

    def newer(rel):
        p = root / rel
        return pkg.mtime(rel) > (p.stat().st_mtime if p.exists() else 0)

    for rel, key, label in (("employees.json", "id", "employees"), ("positions.json", "name", "positions")):
        there = pkg.json(rel)
        if there is None:
            continue
        here = json.loads((root / rel).read_text(encoding="utf-8")) if (root / rel).exists() else []
        merged, a, c = _merge_list(here, there, key, newer(rel))
        if a or c:
            _write(root, rel, merged)
            report.append(f"{label}: {a} added, {c} updated")
    inv_t = pkg.json("inventory.json")
    if inv_t is not None:
        p = root / "inventory.json"
        inv_h = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
        nw = newer("inventory.json")
        items, a1, c1 = _merge_list(inv_h.get("items", []), inv_t.get("items", []), "id", nw)
        orders, a2, _ = _merge_list(inv_h.get("orders", []), inv_t.get("orders", []), "id", False)
        out = copy.deepcopy(inv_h)
        out["items"], out["orders"] = items, orders
        if nw:
            for k in ("draft", "settings"):
                if k in inv_t:
                    out[k] = copy.deepcopy(inv_t[k])
        if out != inv_h:
            _write(root, "inventory.json", out)
            report.append(f"inventory: {a1} items added, {c1} updated, {a2} past orders added")
    wa = wc = 0
    for rel in pkg.weeks():
        there = pkg.json(rel) or {}
        p = root / rel
        if not p.exists():
            _write(root, rel, there)
            wa += 1
            continue
        here = json.loads(p.read_text(encoding="utf-8"))
        merged = _merge_week(here, there, newer(rel))
        if merged != here:
            _write(root, rel, merged)
            wc += 1
    if wa or wc:
        report.append(f"weeks: {wa} added, {wc} updated")
    st = pkg.json("settings.json")
    if st is not None and newer("settings.json"):
        p = root / "settings.json"
        local = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
        merged = _keep_local_settings(st, local)
        if merged != local:
            _write(root, "settings.json", merged)
            report.append("settings updated (tips, shifts, schedule times)")
    return ("Synced — " + "; ".join(report) + ".") if report else "Already in sync — nothing to change."

"""
Stamhad Staff — local storage.

Everything is plain JSON in the user data folder, saved immediately on every
change (no "unsaved changes" state):

  <data>/settings.json
  <data>/employees.json
  <data>/positions.json
  <data>/weeks/<monday>.json   -> {"schedule": {...}, "days": {...}, "adjustments": {...}}
"""

from __future__ import annotations

import copy
import json
import os
import platform
import random
import string
from datetime import date
from pathlib import Path

from core import DAYS, DEFAULT_SETTINGS


def data_dir() -> Path:
    env = os.environ.get("STAMHAD_STAFF_DATA")
    if env:
        d = Path(env)
    elif platform.system() == "Darwin":
        d = Path.home() / "Library" / "Application Support" / "StamhadStaff"
    elif platform.system() == "Windows":
        d = Path(os.environ.get("APPDATA", str(Path.home()))) / "StamhadStaff"
    else:
        d = Path.home() / ".stamhad-staff"
    d.mkdir(parents=True, exist_ok=True)
    return d


def payroll_data_dir() -> Path:
    """Stamhad Payroll's data folder (where its Toast SSH key lives)."""
    if platform.system() == "Darwin":
        return Path.home() / "Library" / "Application Support" / "StamhadPayroll"
    if platform.system() == "Windows":
        return Path(os.environ.get("APPDATA", str(Path.home()))) / "StamhadPayroll"
    return Path.home() / ".stamhad-payroll"


def gen_id(n=8) -> str:
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=n))


def _deep_merge(base: dict, over: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


DEFAULT_POSITIONS = [
    {"name": "Server", "department": "FOH", "tip_points": 10, "receives_bar_tips": False, "bar_tip_share_pct": 0},
    {"name": "Bartender", "department": "FOH", "tip_points": 5, "receives_bar_tips": True, "bar_tip_share_pct": 0},
    {"name": "Runner", "department": "FOH", "tip_points": 7, "receives_bar_tips": False, "bar_tip_share_pct": 0},
    {"name": "Busser", "department": "FOH", "tip_points": 5, "receives_bar_tips": False, "bar_tip_share_pct": 0},
    {"name": "Barback", "department": "FOH", "tip_points": 2, "receives_bar_tips": False, "bar_tip_share_pct": 20},
    {"name": "Host", "department": "FOH", "tip_points": 0, "receives_bar_tips": False, "bar_tip_share_pct": 0},
    {"name": "Kitchen", "department": "BOH", "tip_points": 0, "receives_bar_tips": False, "bar_tip_share_pct": 0},
    {"name": "Dishwasher", "department": "BOH", "tip_points": 0, "receives_bar_tips": False, "bar_tip_share_pct": 0},
]


def default_position(name: str) -> dict:
    """Sensible tip settings for a job name coming from Toast."""
    n = name.lower()
    p = {"name": name, "department": "FOH", "tip_points": 0, "receives_bar_tips": False, "bar_tip_share_pct": 0}
    if any(k in n for k in ("cook", "kitchen", "chef", "dish", "prep", "porter", "line", "fry", "pizza", "sushi")):
        p["department"] = "BOH"
    elif "barback" in n or "bar back" in n:
        p.update(tip_points=2, bar_tip_share_pct=20)
    elif "bartend" in n:
        p.update(tip_points=5, receives_bar_tips=True)
    elif "server" in n or "waiter" in n or "waitress" in n:
        p["tip_points"] = 10
    elif "runner" in n:
        p["tip_points"] = 7
    elif "bus" in n:
        p["tip_points"] = 5
    return p


class Store:
    def __init__(self, root: Path | None = None):
        self.root = root or data_dir()
        (self.root / "weeks").mkdir(parents=True, exist_ok=True)
        saved = self._load("settings.json", None)
        self.settings = _deep_merge(DEFAULT_SETTINGS, saved or {})
        if saved is not None and "tip_method" not in saved:
            # made before the choice existed -> it was splitting by time; keep it that way
            self.settings["tip_method"] = "time"
            self._save("settings.json", self.settings)
        self.positions = self._load("positions.json", None)
        self.employees = self._load("employees.json", None)
        self.first_run = self.positions is None and self.employees is None
        if self.positions is None:
            self.positions = copy.deepcopy(DEFAULT_POSITIONS)
        if self.employees is None:
            self.employees = []
        self._weeks: dict[str, dict] = {}

    # ── files ──────────────────────────────────────────────────────────────
    def _load(self, name, default):
        p = self.root / name
        if not p.exists():
            return default
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return default

    def _save(self, name, data):
        p = self.root / name
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(p)

    def save_settings(self):
        self._save("settings.json", self.settings)

    def save_positions(self):
        self._save("positions.json", self.positions)

    def save_employees(self):
        self._save("employees.json", self.employees)

    # ── lookups ────────────────────────────────────────────────────────────
    def pos_map(self) -> dict:
        return {p["name"]: p for p in self.positions}

    def emp(self, eid):
        return next((e for e in self.employees if e["id"] == eid), None)

    def active_employees(self):
        return sorted([e for e in self.employees if e.get("active", True)],
                      key=lambda e: (self.emp_dept(e) != "FOH", e.get("sort_order", 0), e["name"]))

    def all_employees_sorted(self):
        return sorted(self.employees,
                      key=lambda e: (not e.get("active", True), self.emp_dept(e) != "FOH",
                                     e.get("sort_order", 0), e["name"]))

    def emp_dept(self, e) -> str:
        main = e.get("main_position") or (e.get("positions") or [""])[0]
        return self.pos_map().get(main, {}).get("department", "FOH")

    def emp_main_position(self, e) -> str:
        return e.get("main_position") or (e.get("positions") or [""])[0]

    def rename_position(self, old, new):
        for e in self.employees:
            e["positions"] = [new if p == old else p for p in e.get("positions", [])]
            if e.get("main_position") == old:
                e["main_position"] = new
        self.save_employees()

    # ── weeks ──────────────────────────────────────────────────────────────
    def week(self, mon: date) -> dict:
        key = mon.isoformat()
        if key not in self._weeks:
            w = self._load(f"weeks/{key}.json", None) or {}
            w.setdefault("schedule", {})
            w.setdefault("days", {})
            w.setdefault("adjustments", {})
            self._weeks[key] = w
        return self._weeks[key]

    def save_week(self, mon: date):
        self._save(f"weeks/{mon.isoformat()}.json", self.week(mon))

    def day(self, mon: date, day: str) -> dict:
        d = self.week(mon)["days"].setdefault(day, {})
        d.setdefault("entries", [])
        d.setdefault("tips", {})
        return d

    def schedule_day(self, mon: date, day: str) -> list:
        return self.week(mon)["schedule"].setdefault(day, [])

    # ── import from a Toast employee export ────────────────────────────────
    @staticmethod
    def read_toast_employees(csv_path) -> list[dict]:
        """Toast Web \u2192 Employees \u2192 Export CSV  ->  [{first, last, jobs[], phone, guid}]"""
        import csv as _csv
        out = []
        with open(csv_path, newline="", encoding="utf-8-sig") as f:
            for r in _csv.DictReader(f):
                first = " ".join((r.get("First Name") or "").split())
                last = " ".join((r.get("Last Name") or "").split())
                if not first and not last:
                    continue
                jobs = [j.strip() for j in (r.get("Job Descriptions") or "").split(";") if j.strip()]
                phone = (r.get("Phone Number") or "").strip()
                out.append({"first": first, "last": last, "jobs": jobs, "phone": phone,
                            "guid": (r.get("GUID") or "").strip()})
        return out

    def import_toast_employees(self, csv_path, replace=True) -> tuple[int, int]:
        """Add employees + positions from a Toast export. replace=True removes the current
        employees and positions first (their past hours stay in old weeks)."""
        rows = self.read_toast_employees(csv_path)
        old_pos = {p["name"].lower(): p for p in self.positions}
        if replace:
            self.positions = []
            self.employees = []
        have_pos = {p["name"].lower() for p in self.positions}
        for r in rows:
            for j in r["jobs"]:
                if j.lower() in have_pos:
                    continue
                self.positions.append(old_pos.get(j.lower()) or default_position(j))
                have_pos.add(j.lower())
        have_emp = {e.get("toast_guid") for e in self.employees if e.get("toast_guid")} | \
                   {e["name"].lower() for e in self.employees}
        n = 0
        for i, r in enumerate(rows):
            last_ok = r["last"] if len(r["last"].strip(". ")) > 0 else ""
            name = " ".join(x for x in (r["first"], last_ok) if x)
            if r["guid"] in have_emp or name.lower() in have_emp:
                continue
            pos_names = [next(p["name"] for p in self.positions if p["name"].lower() == j.lower()) for j in r["jobs"]]
            self.employees.append({
                "id": gen_id(), "name": name, "positions": pos_names,
                "main_position": pos_names[0] if pos_names else "",
                "toast_name": f"{r['last']}, {r['first']}" if r["last"] else r["first"],
                "toast_guid": r["guid"], "phone": r["phone"], "active": True,
                "sort_order": i})
            n += 1
        self.save_positions()
        self.save_employees()
        return n, len(self.positions)

    # ── import from Stamhad Payroll ────────────────────────────────────────
    def import_from_payroll(self, config_dir: Path) -> tuple[int, int]:
        """Copy employees + positions (without wages) from a Stamhad Payroll config folder."""
        emps = json.loads((config_dir / "employees.json").read_text(encoding="utf-8"))
        poss = json.loads((config_dir / "positions.json").read_text(encoding="utf-8"))
        existing_pos = {p["name"] for p in self.positions}
        np = 0
        for p in poss:
            if p.get("name") in ("SYSTEM",) or p.get("name") in existing_pos:
                continue
            self.positions.append({
                "name": p["name"], "department": p.get("department", "FOH"),
                "tip_points": p.get("tip_points", 0) or 0,
                "receives_bar_tips": bool(p.get("receives_bar_tips")),
                "bar_tip_share_pct": p.get("bar_tip_share_pct", 0) or 0,
            })
            existing_pos.add(p["name"])
            np += 1
        existing_emp = {e["name"].strip().lower() for e in self.employees}
        ne = 0
        for e in emps:
            if e["name"].strip().lower() in existing_emp:
                continue
            positions = [a["position_name"] if isinstance(a, dict) else a
                         for a in e.get("positions", [])]
            positions = [p for p in positions if p != "SYSTEM"]
            if not positions:
                continue
            self.employees.append({
                "id": e.get("id") or gen_id(), "name": e["name"].strip(),
                "positions": positions,
                "main_position": e.get("main_position") or (positions[0] if positions else ""),
                "toast_name": "", "phone": "", "active": True,
                "sort_order": e.get("sort_order", len(self.employees)),
            })
            ne += 1
        self.save_positions()
        self.save_employees()
        return ne, np


def find_payroll_config() -> Path | None:
    """Look for a Stamhad Payroll config folder next to this app."""
    here = Path(__file__).resolve().parent
    for cand in [here.parent / "anemi-payroll" / "config",
                 here.parent / "payroll app" / "config",
                 here.parent / "stamhad-payroll" / "config"]:
        if (cand / "employees.json").exists() and (cand / "positions.json").exists():
            return cand
    return None

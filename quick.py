"""Quick-add dialogs — create an employee (and a new position if needed) without
leaving what you're doing."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox

from core import to_float
from store import gen_id
import toast
from ui import *  # noqa: F401,F403

NEW_EMP = "+ New employee…"


def emp_names(store, include=None) -> list[str]:
    """Active employees A–Z (plus `include` if it's inactive), with '+ New employee…' first."""
    names = sorted((e["name"] for e in store.employees if e.get("active", True)), key=str.lower)
    if include and include not in names:
        names.append(include)
    return [NEW_EMP] + names


SEP = "\u2500" * 14


def pos_values(store, emp) -> list[str]:
    """Employee's own positions first, then every other position (picking one adds it to them)."""
    own = list((emp or {}).get("positions", []))
    others = sorted((p["name"] for p in store.positions if p["name"] not in own), key=str.lower)
    return own + ([SEP] + others if own and others else others)


def ensure_position(store, emp, pos) -> bool:
    """Add pos to emp's positions if it's new for them. Returns True if changed."""
    if emp and pos and pos != SEP and pos not in emp.get("positions", []):
        emp.setdefault("positions", []).append(pos)
        store.save_employees()
        return True
    return False


def quick_add_employee(app, parent, raw_name: str = "", job: str = "", on_done=None):
    """Small dialog: name, position (existing or new). Calls on_done(emp) after saving."""
    s = app.store
    dlg = Dialog(parent, "New employee", width=520)
    b = dlg.body
    b.columnconfigure(1, weight=1)

    dlg.label(b, "Full name").grid(row=0, column=0, columnspan=2, sticky="w")
    name = Inp(b, width=40, font=(FONT, 12))
    name.set(toast.display_name(raw_name) if raw_name else "")
    name.grid(row=1, column=0, columnspan=2, sticky="we", ipady=4, pady=(2, 10))

    if raw_name:
        tk.Label(b, text=f"Toast name: {raw_name}  — will be matched automatically next time",
                 bg=BG_PAGE, fg=FG_SEC, font=(FONT, 9)).grid(row=2, column=0, columnspan=2, sticky="w", pady=(0, 8))

    dlg.label(b, "Position").grid(row=3, column=0, columnspan=2, sticky="w")
    pos_names = sorted((p["name"] for p in s.positions), key=str.lower)
    guess = toast.map_job(job, s.settings, s.positions) or job
    pc = ttk.Combobox(b, values=pos_names, width=28)          # editable: type a new one
    pc.set(guess)
    pc.grid(row=4, column=0, columnspan=2, sticky="w", pady=(2, 2))
    hint = tk.Label(b, text="", bg=BG_PAGE, fg=FG_SEC, font=(FONT, 9))
    hint.grid(row=5, column=0, columnspan=2, sticky="w")

    newbox = tk.Frame(b, bg="#FFFFFF", highlightbackground=BORDER, highlightthickness=1, padx=10, pady=8)
    tk.Label(newbox, text="New position", bg="#FFFFFF", fg=FG_HDR, font=(FONT, 10, "bold")).grid(
        row=0, column=0, columnspan=4, sticky="w")
    tk.Label(newbox, text="Dept", bg="#FFFFFF", fg=FG_SEC).grid(row=1, column=0, sticky="w", pady=4)
    dept = ttk.Combobox(newbox, values=["FOH", "BOH"], state="readonly", width=6)
    kitchenish = any(k in (guess or "").lower() for k in ("cook", "kitchen", "chef", "dish", "prep", "frier", "fry", "clean", "porter"))
    dept.set("BOH" if kitchenish else "FOH")
    dept.grid(row=1, column=1, sticky="w", padx=(4, 16))
    tk.Label(newbox, text="Tip points", bg="#FFFFFF", fg=FG_SEC).grid(row=1, column=2, sticky="w")
    pts = Inp(newbox, width=6)
    pts.set("0" if kitchenish else "")
    pts.grid(row=1, column=3, sticky="w", padx=4, ipady=2)

    def refresh_new(*_):
        v = pc.get().strip()
        is_new = bool(v) and v not in pos_names
        if is_new:
            newbox.grid(row=6, column=0, columnspan=2, sticky="we", pady=(6, 0))
            hint.config(text=f"“{v}” isn't a position yet — it will be created.")
        else:
            newbox.grid_forget()
            hint.config(text="Pick one, or type a new position name.")
    pc.bind("<<ComboboxSelected>>", refresh_new)
    pc.bind("<KeyRelease>", refresh_new)
    refresh_new()

    known_job = bool(toast.map_job(job, s.settings, s.positions))
    remember = tk.BooleanVar(value=bool(job) and not known_job)
    if job and not known_job:
        tk.Checkbutton(b, text=f"Always treat Toast job “{job}” as this position",
                       variable=remember, bg=BG_PAGE, font=(FONT, 10)).grid(
            row=7, column=0, columnspan=2, sticky="w", pady=(10, 0))

    def save():
        nm = " ".join(name.get().split())
        pos = pc.get().strip()
        if not nm:
            messagebox.showwarning("Name", "Enter a name.", parent=dlg)
            return
        if not pos:
            messagebox.showwarning("Position", "Pick or type a position.", parent=dlg)
            return
        if any(e["name"].lower() == nm.lower() for e in s.employees):
            if not messagebox.askyesno("Already exists",
                                       f"There is already an employee called {nm}.\nAdd another one anyway?",
                                       parent=dlg):
                return
        if pos not in pos_names:
            s.positions.append({"name": pos, "department": dept.get() or "FOH",
                                "tip_points": to_float(pts.get(), 0.0) or 0.0,
                                "receives_bar_tips": "bartend" in pos.lower(),
                                "bar_tip_share_pct": 0})
            s.save_positions()
        if job and remember.get() and job.lower() != pos.lower():
            s.settings.setdefault("job_map", {})[job.lower()] = pos
            s.save_settings()
        emp = {"id": gen_id(), "name": nm, "positions": [pos], "main_position": pos,
               "toast_name": raw_name if raw_name and not toast.match_employee(raw_name, [{"name": nm}]) else "",
               "phone": "", "active": True, "sort_order": len(s.employees)}
        s.employees.append(emp)
        s.save_employees()
        dlg.destroy()
        app.notice.show(f"Added {nm} ({pos})")
        if on_done:
            on_done(emp)

    dlg.buttons("Add employee", save)
    dlg.show(focus=name)
    return dlg

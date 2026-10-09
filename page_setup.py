"""Setup pages — Employees, Positions, Settings."""

from __future__ import annotations

import os
import platform
import subprocess
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from pathlib import Path

from core import DAYS, SHIFTS, norm_time, to_float
from store import gen_id
from ui import *  # noqa: F401,F403
import applog
import sharing
import account
import updater
import update_ui


# ═════════════════════════════════════════════════════════════════════════════
#  EMPLOYEES
# ═════════════════════════════════════════════════════════════════════════════
class EmployeesPage:
    FILTERS = ["Active", "Inactive", "All"]

    def __init__(self, app, parent):
        self.app, self.s, self.parent = app, app.store, parent
        self.filter = getattr(app, "_emp_filter", "Active")
        self.query = ""
        self.build()

    def build(self):
        for w in self.parent.winfo_children():
            w.destroy()
        s = self.s
        n_act = len([e for e in s.employees if e.get("active", True)])
        h = PageHeader(self.parent, "Employees", f"{n_act} active")
        Btn(h.actions, "+ Add employee", lambda: self.edit(None), tip=f"{MOD_SYM}N").pack(side="right")
        MenuBtn(h.actions, "More", [("Import from a Toast employee export\u2026", self.import_toast)],
                "ghost").pack(side="right", padx=8)

        bar = tk.Frame(self.parent, bg=BG_PAGE, padx=28)
        bar.pack(fill="x", pady=(0, 10))
        counts = {"Active": n_act, "Inactive": len(s.employees) - n_act, "All": len(s.employees)}
        Segmented(bar, self.FILTERS, self.filter, self.set_filter, badges=counts, size=10).pack(side="left")
        self.search_box = SearchBox(bar, lambda q: (setattr(self, "query", q), self.render(), self.sf.to_top()),
                                    "Find a name or position", width=24, value=self.query)
        self.search_box.pack(side="right")

        self.sf = ScrollFrame(self.parent)
        self.sf.pack(fill="both", expand=True, padx=28, pady=(0, 16))
        self.render()

    def import_toast(self):
        path = filedialog.askopenfilename(parent=self.app, title="Toast employee export (CSV)",
                                          filetypes=[("CSV", "*.csv"), ("All files", "*.*")])
        if not path:
            return
        try:
            rows = self.s.read_toast_employees(path)
        except Exception as ex:
            messagebox.showerror("Can't read file", str(ex), parent=self.app)
            return
        if not rows:
            messagebox.showinfo("Nothing found", "No employees in that file.", parent=self.app)
            return
        jobs = sorted({j for r in rows for j in r["jobs"]})
        dlg = Dialog(self.app, "Import from Toast", width=520)
        tk.Label(dlg.body, text=f"{len(rows)} employees  \u00b7  {len(jobs)} jobs", bg=BG_PAGE, fg=FG,
                 font=(FONT, 14, "bold")).pack(anchor="w")
        tk.Label(dlg.body, text="Jobs: " + ", ".join(jobs), bg=BG_PAGE, fg=FG_SEC, font=(FONT, 10),
                 wraplength=470, justify="left").pack(anchor="w", pady=(4, 10))
        rep = tk.BooleanVar(value=True)
        tk.Checkbutton(dlg.body, text="Replace my current employees and positions", variable=rep, bg=BG_PAGE,
                       font=(FONT, 11)).pack(anchor="w")
        tk.Label(dlg.body, text="Untick to only add people who aren't here yet. Past hours stay in old weeks.",
                 bg=BG_PAGE, fg=FG_SEC, font=(FONT, 9)).pack(anchor="w")

        def go():
            n, np = self.s.import_toast_employees(path, replace=rep.get())
            dlg.destroy()
            self.app.notice.show(f"Imported {n} employees \u00b7 {np} positions \u2014 check tip points in Positions")
            self.build()
        dlg.buttons("Import", go)
        dlg.show(focus=dlg)

    def set_filter(self, f):
        self.filter = f
        self.app._emp_filter = f
        self.build()

    def render(self):
        for w in self.sf.winfo_children():
            w.destroy()
        s = self.s
        emps = s.all_employees_sorted()
        if self.filter == "Active":
            emps = [e for e in emps if e.get("active", True)]
        elif self.filter == "Inactive":
            emps = [e for e in emps if not e.get("active", True)]
        if self.query:
            emps = [e for e in emps if matches(self.query, e["name"], *e.get("positions", []), e.get("phone", ""))]
        if not s.employees:
            empty_state(self.sf, "\U0001F465", "No employees yet", "+ Add employee", lambda: self.edit(None),
                        sub="Add people one by one, or import a Toast employee export (More ▾).")
            return
        if not emps:
            tk.Label(self.sf, text="Nobody matches.", bg=BG_PAGE, fg=FG_SEC, font=(FONT, 12), pady=30).pack()
            return
        cur = None
        card = None
        for idx, e in enumerate(emps):
            dept = s.emp_dept(e)
            if dept != cur:
                cur = dept
                tk.Label(self.sf, text="Front of House" if dept == "FOH" else "Back of House", bg=BG_PAGE,
                         fg=FOH_BG if dept == "FOH" else BOH_BG, font=(FONT, 10, "bold")).pack(anchor="w", pady=(10, 4))
                card = Card(self.sf, padx=0, pady=0)
                card.pack(fill="x")
            r = tk.Frame(card, bg=BG_CARD, cursor="hand2")
            r.pack(fill="x")
            tk.Frame(card, bg=BORDER_LT if False else "#F1F3F6", height=1).pack(fill="x")
            active = e.get("active", True)
            nm = tk.Label(r, text=e["name"], bg=BG_CARD, fg=FG if active else FG_SEC, font=(FONT, 12, "bold"),
                          anchor="w", padx=16, pady=0, cursor="hand2")
            nm.grid(row=0, column=0, sticky="w", pady=(9, 0))
            others = [p for p in e.get("positions", []) if p != s.emp_main_position(e)]
            sub = s.emp_main_position(e) + (f"  +{len(others)} more" if others else "") + ("" if active else "  · inactive")
            sl = tk.Label(r, text=sub, bg=BG_CARD, fg=FG_SEC, font=(FONT, 10), anchor="w", padx=16, cursor="hand2")
            sl.grid(row=1, column=0, sticky="w", pady=(0, 9))
            r.columnconfigure(0, weight=1)
            arrows = tk.Frame(r, bg=BG_CARD)
            arrows.grid(row=0, column=1, rowspan=2, padx=14)
            parts = [r, nm, sl, arrows]
            for sym, d, tip in (("▲", -1, "Move up (schedule order)"), ("▼", 1, "Move down")):
                a = tk.Label(arrows, text=sym, bg=BG_CARD, fg="#C4C9D4", font=(FONT, 9), cursor="hand2", padx=3)
                a.pack(side="left")
                a.bind("<Button-1>", lambda ev, e=e, d=d: (self.move(e, d), "break")[1])
                Tooltip(a, tip)
                parts.append(a)
            for w in (r, nm, sl):
                w.bind("<Button-1>", lambda ev, e=e: self.edit(e))
            hover(parts, BG_CARD, "#F5F7FF")

    def move(self, emp, d):
        s = self.s
        same = [e for e in s.all_employees_sorted() if s.emp_dept(e) == s.emp_dept(emp)
                and e.get("active", True) == emp.get("active", True)]
        i = same.index(emp)
        j = i + d
        if 0 <= j < len(same):
            same[i], same[j] = same[j], same[i]
            for k, e in enumerate(same):
                e["sort_order"] = k
            s.save_employees()
            keep = self.sf.position()
            self.render()
            self.sf.restore(keep)

    def edit(self, emp):
        s = self.s
        app = self.app
        new = emp is None
        emp = emp or {"id": gen_id(), "name": "", "positions": [], "main_position": "",
                      "toast_name": "", "phone": "", "active": True, "sort_order": len(s.employees)}
        dlg = Dialog(app, "Add employee" if new else emp["name"], width=600)
        b = dlg.body
        b.columnconfigure(0, weight=1)
        fields = {}
        for i, (key, lbl, hint) in enumerate([("name", "Full name", ""),
                                              ("toast_name", "Toast name", "only if Toast spells it differently"),
                                              ("phone", "Phone", "optional")]):
            field_label(b, lbl, hint).grid(row=i * 2, column=0, sticky="w", pady=(8 if i else 0, 2))
            ent = Inp(b, width=42)
            ent.set(emp.get(key, ""))
            ent.grid(row=i * 2 + 1, column=0, sticky="we", ipady=4)
            fields[key] = ent
        hdr = tk.Frame(b, bg=BG_PAGE)
        hdr.grid(row=6, column=0, sticky="we", pady=(14, 4))
        field_label(hdr, "Positions", "tick all they can work").pack(side="left")
        pbox = tk.Frame(b, bg=BG_CARD, highlightbackground=BORDER, highlightthickness=1, padx=8, pady=6)
        pbox.grid(row=7, column=0, sticky="we")
        pvars = {}

        def add_pos_cb(p, ticked):
            i = len(pvars)
            v = tk.BooleanVar(value=ticked)
            v.trace_add("write", lambda *a: sync_main())
            tk.Checkbutton(pbox, text=p["name"], variable=v, bg=BG_CARD, anchor="w",
                           font=(FONT, 11)).grid(row=i // 3, column=i % 3, sticky="w", padx=4, pady=1)
            pvars[p["name"]] = v

        def sync_main():
            ticked = [n for n, v in pvars.items() if v.get()]
            main_cb.config(values=ticked)
            if main_cb.get() not in ticked:
                main_cb.set(ticked[0] if ticked else "")

        def new_position():
            PositionsPage.position_dialog(app, None, on_saved=lambda p: (add_pos_cb(p, True), sync_main()),
                                          parent=dlg)

        for p in sorted(s.positions, key=lambda p: (p.get("department") != "FOH", p["name"])):
            add_pos_cb(p, p["name"] in emp.get("positions", []))
        Btn(hdr, "+ New position", new_position, "ghost", small=True).pack(side="right")
        row = tk.Frame(b, bg=BG_PAGE)
        row.grid(row=8, column=0, sticky="we", pady=(12, 0))
        field_label(row, "Main position").pack(side="left")
        main_cb = ttk.Combobox(row, values=[n for n, v in pvars.items() if v.get()], state="readonly", width=22)
        main_cb.set(emp.get("main_position", ""))
        main_cb.pack(side="left", padx=10)
        act = tk.BooleanVar(value=emp.get("active", True))
        tk.Checkbutton(row, text="Active", variable=act, bg=BG_PAGE, font=(FONT, 11)).pack(side="right")

        def save():
            name = " ".join(fields["name"].get().split())
            if not name:
                messagebox.showwarning("Missing name", "Enter a name.", parent=dlg)
                return
            poss = [n for n, v in pvars.items() if v.get()]
            if not poss:
                messagebox.showwarning("No position", "Tick at least one position.", parent=dlg)
                return
            emp.update({"name": name, "toast_name": fields["toast_name"].get().strip(),
                        "phone": fields["phone"].get().strip(), "positions": poss,
                        "main_position": main_cb.get() if main_cb.get() in poss else poss[0],
                        "active": act.get()})
            if new:
                s.employees.append(emp)
            s.save_employees()
            dlg.destroy()
            app.notice.show(f"Saved {name}")
            self.build()

        def delete():
            if messagebox.askyesno("Delete employee",
                                   f"Delete {emp['name']}?\n\nPast hours stay in old weeks. "
                                   "Tip: untick Active instead to keep them in the records.", parent=dlg):
                s.employees = [e for e in s.employees if e["id"] != emp["id"]]
                s.save_employees()
                dlg.destroy()
                app.notice.show(f"Deleted {emp['name']}")
                self.build()

        dlg.buttons("Save", save)
        if not new:
            Btn(dlg.bar, "Delete", delete, "ghost", small=True).pack(side="left")
        dlg.show(focus=fields["name"])

    def add_new(self):
        self.edit(None)


# ═════════════════════════════════════════════════════════════════════════════
#  POSITIONS
# ═════════════════════════════════════════════════════════════════════════════
class PositionsPage:
    def __init__(self, app, parent):
        self.app, self.s, self.parent = app, app.store, parent
        self.build()

    def build(self):
        for w in self.parent.winfo_children():
            w.destroy()
        s = self.s
        h = PageHeader(self.parent, "Positions", "Points decide each person's share of the floor tips")
        Btn(h.actions, "+ Add position", self.add_new, tip=f"{MOD_SYM}N").pack(side="right")
        self.sf = ScrollFrame(self.parent)
        self.sf.pack(fill="both", expand=True, padx=28, pady=(0, 16))
        for dept, title, color in (("FOH", "Front of House", FOH_BG), ("BOH", "Back of House", BOH_BG)):
            ps = sorted([p for p in s.positions if p.get("department", "FOH") == dept],
                        key=lambda p: (-(to_float(p.get("tip_points"), 0) or 0), p["name"]))
            if not ps:
                continue
            tk.Label(self.sf, text=title, bg=BG_PAGE, fg=color, font=(FONT, 10, "bold")).pack(anchor="w", pady=(10, 4))
            card = Card(self.sf, padx=0, pady=0)
            card.pack(fill="x")
            for p in ps:
                r = tk.Frame(card, bg=BG_CARD, cursor="hand2")
                r.pack(fill="x")
                tk.Frame(card, bg="#F1F3F6", height=1).pack(fill="x")
                nm = tk.Label(r, text=p["name"], bg=BG_CARD, fg=FG, font=(FONT, 12, "bold"), anchor="w",
                              padx=16, pady=10, cursor="hand2")
                nm.pack(side="left")
                pts = to_float(p.get("tip_points"), 0) or 0
                extra = []
                if pts:
                    extra.append(f"{pts:g} pts")
                if to_float(p.get("bar_tip_share_pct"), 0):
                    extra.append(f"{to_float(p.get('bar_tip_share_pct'), 0):g}% of bar")
                elif p.get("receives_bar_tips"):
                    extra.append("bar tips")
                n = len([e for e in s.employees if p["name"] in e.get("positions", [])])
                info = tk.Label(r, text=" · ".join(extra) or "no tips", bg=BG_CARD,
                                fg=ACCENT if extra else FG_SEC, font=(FONT, 11, "bold" if extra else "normal"),
                                padx=16, cursor="hand2")
                info.pack(side="right")
                cnt = tk.Label(r, text=f"{n} people", bg=BG_CARD, fg=FG_SEC, font=(FONT, 10), cursor="hand2")
                cnt.pack(side="right", padx=10)
                parts = [r, nm, info, cnt]
                for w in parts:
                    w.bind("<Button-1>", lambda e, p=p: self.position_dialog(self.app, p, on_saved=lambda _: self.build(),
                                                                              on_deleted=self.build))
                hover(parts, BG_CARD, "#F5F7FF")

    def add_new(self):
        self.position_dialog(self.app, None, on_saved=lambda _: self.build())

    @staticmethod
    def position_dialog(app, pos, on_saved=None, on_deleted=None, parent=None):
        s = app.store
        new = pos is None
        pos = pos or {"name": "", "department": "FOH", "tip_points": 0,
                      "receives_bar_tips": False, "bar_tip_share_pct": 0}
        dlg = Dialog(parent or app, "Add position" if new else pos["name"], width=440)
        b = dlg.body
        field_label(b, "Name").grid(row=0, column=0, sticky="w")
        nm = Inp(b, width=34)
        nm.set(pos["name"])
        nm.grid(row=1, column=0, columnspan=2, sticky="we", ipady=4)
        field_label(b, "Department").grid(row=2, column=0, sticky="w", pady=(12, 2))
        dept = ttk.Combobox(b, values=["FOH", "BOH"], state="readonly", width=8)
        dept.set(pos.get("department", "FOH"))
        dept.grid(row=3, column=0, sticky="w")
        field_label(b, "Tip points", "0 = no floor tips").grid(row=4, column=0, sticky="w", pady=(12, 2))
        pts = Inp(b, width=8)
        pts.set(f"{to_float(pos.get('tip_points'), 0):g}")
        pts.grid(row=5, column=0, sticky="w", ipady=4)
        more = tk.Frame(b, bg=BG_PAGE)
        more.grid(row=6, column=0, columnspan=2, sticky="w", pady=(14, 0))
        rb = tk.BooleanVar(value=bool(pos.get("receives_bar_tips")))
        tk.Checkbutton(more, text="Splits the bar tips (bartender)", variable=rb, bg=BG_PAGE,
                       font=(FONT, 11)).pack(anchor="w")
        bf = tk.Frame(more, bg=BG_PAGE)
        bf.pack(anchor="w", pady=(6, 0))
        tk.Label(bf, text="Takes a fixed", bg=BG_PAGE, fg=FG_HDR, font=(FONT, 11)).pack(side="left")
        bsp = Inp(bf, width=5)
        bsp.set(f"{to_float(pos.get('bar_tip_share_pct'), 0):g}")
        bsp.pack(side="left", padx=4, ipady=2)
        tk.Label(bf, text="% of bar tips (barback)", bg=BG_PAGE, fg=FG_HDR, font=(FONT, 11)).pack(side="left")

        def save():
            name = " ".join(nm.get().split())
            if not name:
                return
            if (new or name != pos.get("name")) and name in s.pos_map():
                messagebox.showwarning("Exists", "A position with that name exists.", parent=dlg)
                return
            old = pos.get("name")
            pos.update({"name": name, "department": dept.get() or "FOH",
                        "tip_points": to_float(pts.get(), 0.0) or 0.0, "receives_bar_tips": rb.get(),
                        "bar_tip_share_pct": to_float(bsp.get(), 0.0) or 0.0})
            if new:
                s.positions.append(pos)
            elif old and old != name:
                s.rename_position(old, name)
            s.save_positions()
            dlg.destroy()
            if on_saved:
                on_saved(pos)

        def delete():
            users = [e["name"] for e in s.employees if pos["name"] in e.get("positions", [])]
            if users:
                messagebox.showwarning("In use", f"{pos['name']} is used by: {', '.join(users[:8])}"
                                       + ("…" if len(users) > 8 else "")
                                       + "\n\nRemove it from those employees first.", parent=dlg)
                return
            if messagebox.askyesno("Delete position", f"Delete {pos['name']}?", parent=dlg):
                s.positions.remove(pos)
                s.save_positions()
                dlg.destroy()
                if on_deleted:
                    on_deleted()

        dlg.buttons("Save", save)
        if not new:
            Btn(dlg.bar, "Delete", delete, "ghost", small=True).pack(side="left")
        dlg.show(focus=nm)


# ═════════════════════════════════════════════════════════════════════════════
#  SETTINGS
# ═════════════════════════════════════════════════════════════════════════════
class SettingsPage:
    TABS = ["Tips & shifts", "Schedule", "Toast", "Data", "Account"]

    def __init__(self, app, parent):
        self.app, self.s, self.parent = app, app.store, parent
        self.tab = getattr(app, "_settings_tab", "Tips & shifts")
        self.build()

    def build(self):
        for w in self.parent.winfo_children():
            w.destroy()
        h = PageHeader(self.parent, "Settings")
        bar = tk.Frame(self.parent, bg=BG_PAGE, padx=28)
        bar.pack(fill="x", pady=(0, 12))
        Segmented(bar, self.TABS, self.tab, self.set_tab, size=10).pack(side="left")
        self.sf = ScrollFrame(self.parent)
        self.sf.pack(fill="both", expand=True, padx=28, pady=(0, 16))
        self.save_fn = None
        {"Tips & shifts": self.tab_tips, "Schedule": self.tab_schedule, "Toast": self.tab_toast,
         "Data": self.tab_data, "Account": self.tab_account}[self.tab]()
        if self.save_fn:
            Btn(h.actions, "Save", self.save_fn, "success", tip=f"Enter  or  {MOD_SYM}S").mark_default().pack(side="right")

    def set_tab(self, t):
        self.tab = t
        self.app._settings_tab = t
        self.build()

    def save(self):
        if self.save_fn:
            self.save_fn()

    def _card(self, title, text=None):
        c = Card(self.sf, padx=20, pady=16)
        c.pack(fill="x", pady=(0, 12))
        tk.Label(c, text=title, bg=BG_CARD, fg=FG, font=(FONT, 13, "bold")).pack(anchor="w")
        if text:
            tk.Label(c, text=text, bg=BG_CARD, fg=FG_SEC, font=(FONT, 10), wraplength=720,
                     justify="left").pack(anchor="w", pady=(2, 10))
        body = tk.Frame(c, bg=BG_CARD)
        body.pack(fill="x")
        return body

    def _enter_saves(self, widgets):
        for e in widgets:
            e.bind("<Return>", lambda ev: (self.save(), "break")[1])
            e.bind("<KP_Enter>", lambda ev: (self.save(), "break")[1])

    def _saved(self):
        self.s.save_settings()
        self.app.notice.show("Settings saved")

    # ── share / receive ───────────────────────────────────────────────────
    def share_files(self):
        start = Path.home() / "Desktop"
        path = filedialog.asksaveasfilename(
            parent=self.app, title="Share files — save as", initialdir=str(start if start.exists() else Path.home()),
            initialfile=sharing.default_name(), defaultextension=sharing.EXT,
            filetypes=[("NUME data", "*" + sharing.EXT)])
        if not path:
            return
        try:
            man = sharing.make_package(self.s, Path(path), self.app.version)
        except Exception as ex:
            applog.log.exception("share failed")
            messagebox.showerror("Couldn't share", str(ex), parent=self.app)
            return
        applog.log.info("shared data to %s", path)
        c = man["counts"]
        d = Dialog(self.app, "File ready", width=460)
        tk.Label(d.body, text="✓  File ready to send", bg=BG_PAGE, fg=SUCCESS_FG,
                 font=(FONT, 14, "bold")).pack(anchor="w")
        tk.Label(d.body, text=f"{Path(path).name}\n{c['employees']} employees · {c['weeks']} weeks · "
                              f"inventory · error log", bg=BG_PAGE, fg=FG_SEC, font=(FONT, 10),
                 justify="left", wraplength=420).pack(anchor="w", pady=(4, 6))
        tk.Label(d.body, text="Send it by email, WhatsApp or AirDrop. On the other computer: "
                              "Settings → Data → Receive files.", bg=BG_PAGE, fg=FG, font=(FONT, 10),
                 justify="left", wraplength=420).pack(anchor="w")
        d.buttons("Show the file", lambda: (self._reveal(path), d.destroy()), "primary", cancel_text="Close")
        d.show()

    def receive_files(self):
        path = filedialog.askopenfilename(
            parent=self.app, title="Receive files",
            filetypes=[("NUME data", "*" + sharing.EXT), ("All files", "*.*")])
        if not path:
            return
        try:
            pkg = sharing.Package(Path(path))
        except Exception as ex:
            messagebox.showerror("Can't open this file", str(ex), parent=self.app)
            return
        d = Dialog(self.app, "Receive files", width=560)
        tk.Label(d.body, text=Path(path).name, bg=BG_PAGE, fg=FG, font=(FONT, 13, "bold"),
                 wraplength=520, justify="left").pack(anchor="w")
        box = tk.Frame(d.body, bg="#FFFFFF", highlightthickness=1, highlightbackground=BORDER, padx=12, pady=8)
        box.pack(fill="x", pady=(8, 10))
        for ln in sharing.compare(self.s, pkg):
            tk.Label(box, text=ln, bg="#FFFFFF", fg=FG, font=(FONT, 10), anchor="w", justify="left",
                     wraplength=500).pack(anchor="w", pady=1)
        choice = tk.StringVar(value="sync")
        for val, title, sub in (
                ("sync", "Sync (merge)", "Add what's missing here. Where both have the same thing, the one changed "
                                         "more recently wins. Nothing is deleted."),
                ("replace", "Replace everything", "Make this computer exactly like the file. The Toast connection on "
                                                  "this computer is kept.")):
            f = tk.Frame(d.body, bg=BG_PAGE)
            f.pack(fill="x", pady=2)
            tk.Radiobutton(f, text=title, variable=choice, value=val, bg=BG_PAGE, font=(FONT, 11, "bold"),
                           anchor="w").pack(anchor="w")
            tk.Label(f, text=sub, bg=BG_PAGE, fg=FG_SEC, font=(FONT, 10), wraplength=500, justify="left").pack(
                anchor="w", padx=(24, 0))
        tk.Label(d.body, text="Your current data is backed up first, so this can be undone.", bg=BG_PAGE,
                 fg=FG_SEC, font=(FONT, 9)).pack(anchor="w", pady=(8, 0))

        def do():
            try:
                bk = updater.backup_data(self.s.root, "before-receive")
                msg = sharing.sync(self.s, pkg) if choice.get() == "sync" else sharing.replace_all(self.s, pkg)
                applog.log.info("received %s (%s): %s  [backup %s]", path, choice.get(), msg, bk.name)
            except Exception as ex:
                applog.log.exception("receive failed")
                messagebox.showerror("Couldn't receive", f"{ex}\n\nYour data wasn't changed or is in the "
                                     f"backups folder.", parent=d)
                return
            finally:
                pkg.close()
            d.destroy()
            self.app.reload_store()
            messagebox.showinfo("Done", msg + "\n\nA backup of how it was before is in the data "
                                "folder → backups.", parent=self.app)
        if pkg.logs():
            def save_logs():
                folder = filedialog.askdirectory(parent=d, title="Save their error log to…",
                                                 initialdir=str(Path.home() / "Desktop"))
                if folder:
                    self._reveal(pkg.extract_logs(Path(folder)))
            Btn(d.bar, "Save their error log…", save_logs, "ghost").pack(side="left")
        d.buttons("Receive", do, "primary")
        d.show()

    def tab_tips(self):
        st = self.s.settings
        timed = st.get("tip_method", "points") == "time"
        bm = self._card("How are tips split?",
                        "Choose how each shift's floor tips are shared. Bar tips follow the same choice "
                        "(after the barback's %). You can change this any time; it applies to every day.")
        meth = tk.StringVar(value="time" if timed else "points")

        def set_method():
            if meth.get() != st.get("tip_method", "points"):
                st["tip_method"] = meth.get()
                self.s.save_settings()
                self.app.notice.show("Tips are now split " + ("by time worked \u00d7 points" if meth.get() == "time"
                                                              else "by points only"))
                self.build()
        for val, title, sub in (
                ("points", "By points only",
                 "Everyone who worked the shift gets their position's points, however long they stayed. "
                 "E.g. two servers with 9 points get the same."),
                ("time", "By time worked \u00d7 points",
                 "Points \u00d7 the hours someone worked, so who came earlier or stayed longer gets more. "
                 "You set when the tip clock starts and stops below.")):
            f = tk.Frame(bm, bg=BG_CARD)
            f.pack(fill="x", pady=2)
            tk.Radiobutton(f, text=title, variable=meth, value=val, command=set_method, bg=BG_CARD,
                           font=(FONT, 12, "bold"), anchor="w").pack(anchor="w")
            tk.Label(f, text=sub, bg=BG_CARD, fg=FG_SEC, font=(FONT, 10), wraplength=700, justify="left").pack(
                anchor="w", padx=(26, 0))
        fst, sst = {}, {}
        if timed:
            b = self._card("When does the tip clock start and stop?",
                           "Clocking in before the start time counts from the start time (e.g. 4:05 PM gives a "
                           "few minutes of space). After the stop time the clock stops \u2014 anyone still working "
                           "gets the full share. Leave blank to count real clock-in / clock-out. Worked hours are "
                           "never changed.")
            tk.Label(b, text="Starts", bg=BG_CARD, fg=FG_SEC, font=(FONT, 10, "bold")).grid(row=0, column=1, sticky="w", padx=10)
            tk.Label(b, text="Stops", bg=BG_CARD, fg=FG_SEC, font=(FONT, 10, "bold")).grid(row=0, column=2, sticky="w", padx=10)
            for i, sh in enumerate(SHIFTS, start=1):
                shift_pill(b, sh, 10).grid(row=i, column=0, sticky="w", pady=4)
                e0 = Inp(b, width=10)
                e0.set((st.get("tip_start_time") or {}).get(sh) or "")
                e0.grid(row=i, column=1, sticky="w", padx=10, ipady=3)
                sst[sh] = smart_time_field(e0, lambda sh=sh: {"near": (st["default_times"].get(sh) or [""])[0] or None,
                                                              "start": True})
                e = Inp(b, width=10)
                e.set(st["full_share_time"].get(sh) or "")
                e.grid(row=i, column=2, sticky="w", padx=10, ipady=3)
                fst[sh] = smart_time_field(e, lambda sh=sh, e0=e0: {
                    "after": e0.get() or (st["default_times"].get(sh) or [""])[0] or None})
        b2 = self._card("Brunch days", "On these days the day shift is called Brunch instead of Morning.")
        bvars = {}
        for d in DAYS:
            v = tk.BooleanVar(value=d in st.get("brunch_days", []))
            tk.Checkbutton(b2, text=d[:3], variable=v, bg=BG_CARD, font=(FONT, 11)).pack(side="left", padx=(0, 6))
            bvars[d] = v
        b3 = self._card("Day shift or dinner?",
                        "Toast clock-ins go to the shift whose usual hours (Schedule tab) they cover most. "
                        "When there's no clock-out yet, clock-ins before this time count as the day shift.")
        cut = Inp(b3, width=10)
        cut.set(st.get("day_shift_cutoff", "2:00 PM"))
        cut.pack(anchor="w", ipady=3)
        smart_time_field(cut, lambda: {"near": "2:00 PM"})

        def save():
            fix_times(list(sst.values()) + list(fst.values()) + [cut])
            bad = [e.get() for e in list(fst.values()) + list(sst.values()) + [cut] if e.get().strip() and not norm_time(e.get())]
            if bad:
                messagebox.showwarning("Check times", f"Can't read: {', '.join(bad)}\nUse e.g. 11:00 PM",
                                       parent=self.app)
                return
            if fst:
                st["full_share_time"] = {sh: (norm_time(e.get()) or None) for sh, e in fst.items()}
                st["tip_start_time"] = {sh: (norm_time(e.get()) or None) for sh, e in sst.items()}
            st["brunch_days"] = [d for d, v in bvars.items() if v.get()]
            st["day_shift_cutoff"] = norm_time(cut.get()) or "2:00 PM"
            self._saved()
        self.save_fn = save
        self._enter_saves(list(fst.values()) + list(sst.values()) + [cut])

    def tab_schedule(self):
        st = self.s.settings
        b = self._card("Usual shift times", "Used when you schedule someone, and to tell brunch and dinner apart.")
        dt = {}
        for i, sh in enumerate(SHIFTS):
            shift_pill(b, sh, 10).grid(row=i, column=0, sticky="w", pady=4)
            a = Inp(b, width=10)
            a.set(st["default_times"][sh][0])
            a.grid(row=i, column=1, padx=10, ipady=3)
            tk.Label(b, text="to", bg=BG_CARD, fg=FG_SEC).grid(row=i, column=2)
            z = Inp(b, width=10)
            z.set(st["default_times"][sh][1])
            z.grid(row=i, column=3, padx=10, ipady=3)
            smart_time_field(a, lambda: {"start": True})
            smart_time_field(z, lambda a=a: {"after": a.get() or None})
            dt[sh] = (a, z)

        def save():
            fix_times([x for p in dt.values() for x in p])
            bad = [x.get() for p in dt.values() for x in p if x.get().strip() and not norm_time(x.get())]
            if bad:
                messagebox.showwarning("Check times", f"Can't read: {', '.join(bad)}", parent=self.app)
                return
            st["default_times"] = {sh: [norm_time(a.get()), norm_time(z.get())] for sh, (a, z) in dt.items()}
            self._saved()
        self.save_fn = save
        self._enter_saves([x for p in dt.values() for x in p])

    def tab_toast(self):
        import toast
        st = self.s.settings
        b = self._card("Toast connection", "Copy these from Toast Web \u2192 Reports \u2192 Settings "
                                           "(SSH Keys page for the username, Data Exports for the Export ID).")
        tv = {}
        for i, (k, lbl) in enumerate([("host", "Host"), ("username", "SFTP username"), ("export_id", "Export ID")]):
            tk.Label(b, text=lbl, bg=BG_CARD, fg=FG_HDR, font=(FONT, 11)).grid(row=i, column=0, sticky="w", pady=4)
            e = Inp(b, width=56)
            e.set(st["toast"].get(k, ""))
            e.grid(row=i, column=1, sticky="w", padx=10, ipady=3)
            tv[k] = e

        kb = self._card("SSH key", "The private key file (the one WITHOUT .pub). The app keeps its own copy, "
                                   "so it keeps working even if you move or delete the original.")
        key = toast.find_key(st)
        status = tk.Label(kb, text=(f"\u2713 Key ready  ({key})" if key else "No key yet"), bg=BG_CARD,
                          fg=SUCCESS_FG if key else DANGER, font=(FONT, 11, "bold"), wraplength=700, justify="left")
        status.pack(anchor="w")

        def choose():
            path = filedialog.askopenfilename(title="Choose your Toast private key (not the .pub)", parent=self.app)
            if not path:
                return
            try:
                dest = toast.install_key_file(path)
            except Exception as ex:
                messagebox.showerror("Can't use that file", str(ex), parent=self.app)
                return
            st["toast"]["key_path"] = str(dest)
            self.s.save_settings()
            self.app.notice.show("Key saved")
            self.build()
        Btn(kb, "Choose key file\u2026", choose, "outline", small=True).pack(anchor="w", pady=(8, 0))

        mb = self._card("Use it on another computer",
                        "Save a setup file here, copy it to the other PC (USB stick or AirDrop \u2014 not email), "
                        "then Load it there. It holds the key and the connection details, so the other PC is ready "
                        "in one step. Keep the file private: anyone with it can download your Toast data.")
        row = tk.Frame(mb, bg=BG_CARD)
        row.pack(anchor="w")

        def export():
            k = toast.find_key(st)
            if not k:
                messagebox.showwarning("No key yet", "Choose the key file first.", parent=self.app)
                return
            save()
            out = filedialog.asksaveasfilename(parent=self.app, title="Save Toast setup file",
                                               defaultextension=toast.SETUP_EXT,
                                               initialfile="Toast setup" + toast.SETUP_EXT,
                                               filetypes=[("Stamhad Toast setup", "*" + toast.SETUP_EXT)])
            if out:
                toast.export_setup(st, k, out)
                self.app.notice.show("Setup file saved \u2014 copy it to the other computer")

        def load():
            path = filedialog.askopenfilename(parent=self.app, title="Load Toast setup file",
                                              filetypes=[("Stamhad Toast setup", "*" + toast.SETUP_EXT),
                                                         ("All files", "*.*")])
            if not path:
                return
            try:
                toast.load_key_or_setup(path, st)
            except Exception as ex:
                messagebox.showerror("Can't load that file", str(ex), parent=self.app)
                return
            self.s.save_settings()
            self.app.notice.show("Toast is set up on this computer \u2713")
            self.build()
        Btn(row, "Save setup file\u2026", export, "primary", small=True).pack(side="left")
        Btn(row, "Load setup file\u2026", load, "outline", small=True).pack(side="left", padx=8)

        def save():
            for k, e in tv.items():
                st["toast"][k] = e.get().strip()
            self._saved()
        self.save_fn = save
        self._enter_saves(list(tv.values()))

    def _reveal(self, path):
        p = str(path)
        try:
            if platform.system() == "Darwin":
                subprocess.Popen(["open", "-R", p] if Path(p).is_file() else ["open", p])
            elif platform.system() == "Windows":
                if Path(p).is_file():
                    subprocess.Popen(["explorer", "/select,", p])
                else:
                    os.startfile(p)  # type: ignore[attr-defined]
            else:
                subprocess.Popen(["xdg-open", str(Path(p).parent if Path(p).is_file() else p)])
        except Exception as ex:
            messagebox.showerror("Can't open", str(ex), parent=self.app)

    def tab_account(self):
        gate = getattr(self.app, "gate", None)
        if gate is None:
            b = self._card("Account", "Sign-in isn't set up in this copy of the app.")
            return
        b = self._card("Your Stamhad account",
                       "Your subscription is checked when the app opens and every few hours. Without internet "
                       f"the app keeps working for {account.GRACE_DAYS} days after the last check.")
        g = tk.Frame(b, bg=BG_CARD)
        g.pack(anchor="w")
        for r, (k, v) in enumerate(gate.summary()):
            tk.Label(g, text=k, bg=BG_CARD, fg=FG_SEC, font=(FONT, 10, "bold")).grid(row=r, column=0, sticky="w", pady=2)
            tk.Label(g, text=v, bg=BG_CARD, fg=FG, font=(FONT, 11)).grid(row=r, column=1, sticky="w", padx=14, pady=2)
        row = tk.Frame(b, bg=BG_CARD)
        row.pack(anchor="w", pady=(12, 0))
        chk = Btn(row, "Check now", None, "outline", small=True)

        def check():
            chk._lbl.config(text="Checking\u2026")

            def done(res, err):
                if err is not None:
                    self.app.notice.show("Offline \u2014 couldn't check right now", bg=WARN_BG, fg=WARN_FG)
                elif res and res.get("state") == "ok":
                    self.app.notice.show("Subscription active \u2713")
                if self.app.page == "Settings" and getattr(self.app, "_settings_tab", "") == "Account":
                    self.build()
            gate.recheck(quiet=False, done=done)
        chk._cmd = check
        chk.pack(side="left")

        def reset():
            email = gate.session.data.get("email", "")
            try:
                account.send_password_reset(email)
                messagebox.showinfo("Check your email", f"We sent a link to {email} to set a new password.",
                                    parent=self.app)
            except account.Offline:
                messagebox.showwarning("Offline", "Can't reach the internet right now.", parent=self.app)
            except Exception as ex:
                messagebox.showerror("Couldn't send", str(ex), parent=self.app)
        Btn(row, "Change password\u2026", reset, "ghost", small=True).pack(side="left", padx=8)

        def out():
            if messagebox.askyesno("Sign out", "Sign out of NUME on this computer?\n\n"
                                   "Your data stays here. You'll need your email and password to sign in again.",
                                   parent=self.app):
                gate.sign_out()
        Btn(row, "Sign out", out, "ghost", small=True).pack(side="left")
        if gate.session.data.get("is_admin"):
            b2 = self._card("Customers (admin)",
                            "You're signed in with the Stamhad Software admin account. Create customer accounts, "
                            "turn subscriptions on or off and set until when they're paid. Only admins see this.")
            Btn(b2, "Manage customers\u2026", lambda: self.open_customers(gate), "primary", small=True).pack(anchor="w")

    def open_customers(self, gate):
        import admin_ui
        w = getattr(self.app, "_customers_win", None)
        if w is not None and w.winfo_exists():
            w.lift()
            w.focus_force()
            return
        self.app._customers_win = admin_ui.CustomersWindow(self.app, gate.session)

    def tab_data(self):
        # ── share / receive ───────────────────────────────────────────────
        b = self._card("Share & receive files",
                       "Share saves ALL the data (employees, schedule, hours & tips, inventory, settings) plus "
                       "the error log into one file you can send by email, WhatsApp or AirDrop — to another "
                       "computer or to get a problem checked. The Toast key is never included.\n"
                       "Receive opens such a file. Your data is backed up first, then you choose Sync (merge) "
                       "or Replace.")
        row = tk.Frame(b, bg=BG_CARD)
        row.pack(anchor="w")
        Btn(row, "Share files…", self.share_files, "primary", small=True).pack(side="left")
        Btn(row, "Receive files…", self.receive_files, "outline", small=True).pack(side="left", padx=8)

        # ── updates ───────────────────────────────────────────────────────
        b3 = self._card("Updates", f"You have version {self.app.version}. New versions come from GitHub; "
                                   "you're always asked first, and your data is backed up before updating.")
        row = tk.Frame(b3, bg=BG_CARD)
        row.pack(anchor="w", fill="x")
        chk_btn = Btn(row, "Check for updates", None, "outline", small=True)

        def label(t):
            try:
                chk_btn._lbl.config(text=t)
            except tk.TclError:
                pass

        def check():
            label("Checking\u2026")
            update_ui.manual_check(self.app, on_done=lambda: label("Check for updates"))
        chk_btn._cmd = check
        chk_btn.pack(side="left")
        v = tk.BooleanVar(value=self.s.settings.get("update_check", True))

        def toggle():
            self.s.settings["update_check"] = v.get()
            self.s.settings.pop("skipped_version", None)
            self.s.save_settings()
        tk.Checkbutton(row, text="Check when the app opens", variable=v, command=toggle, bg=BG_CARD,
                       font=(FONT, 11)).pack(side="left", padx=14)
        kind, _, problem = updater.install_target()
        if problem:
            tk.Label(b3, text=problem, bg=BG_CARD, fg=FG_SEC, font=(FONT, 10), wraplength=720,
                     justify="left").pack(anchor="w", pady=(8, 0))

        # ── where the data is + error log ─────────────────────────────────
        b4 = self._card("Your data & error log",
                        "Everything is saved automatically as plain files in this folder. Backups made before "
                        "updates and before receiving files are in its “backups” folder.")
        tk.Label(b4, text=str(self.s.root), bg=BG_CARD, fg=FG, font=(FONT, 11)).pack(anchor="w")
        row = tk.Frame(b4, bg=BG_CARD)
        row.pack(anchor="w", pady=(8, 0))
        Btn(row, "Open data folder", lambda: self._reveal(self.s.root), "ghost", small=True).pack(side="left")
        Btn(row, "Open error log", lambda: self._reveal(applog.log_file() or applog.log_dir(self.s.root)),
            "ghost", small=True).pack(side="left", padx=8)

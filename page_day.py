"""Hours & Tips — step 1 Hours, step 2 Tips, one shift at a time.
Click any row to open its side panel (tip hours, points, fixed tip, split, remove)."""

from __future__ import annotations

import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from pathlib import Path

from core import (DAYS, SHIFTS, shifts_for_day, norm_time, to_float, auto_hours, eff_hours,
                  auto_tip_hours, eff_tip_hours, auto_points, eff_points, split_day_tips, day_name,
                  double_split_time, split_entry, day_shift_name, parse_time as core_parse)
from quick import quick_add_employee, emp_names, NEW_EMP, pos_values, ensure_position, SEP
from store import gen_id
import toast
from ui import *  # noqa: F401,F403

NO_EMP = "— pick employee —"
STEPS = ["1  Hours", "2  Tips"]


class DayPage:
    def __init__(self, app, parent):
        self.app = app
        self.s = app.store
        self.parent = parent
        self.date = app.sel_date
        self.mon = app.mon
        self.day = day_name(self.date)
        self.dd = self.s.day(self.mon, self.day)
        self.step = getattr(app, "_day_step", "Hours")
        shifts = self.shift_list()
        want = getattr(app, "_day_shift", None)
        if want not in shifts:
            with_people = [sh for sh in shifts if any(e.get("shift") == sh for e in self.dd["entries"])]
            want = with_people[-1] if with_people else shifts[-1]
        self.shift = want
        self.drawer_entry = None
        self.build()

    # ── helpers ─────────────────────────────────────────────────────────────
    def save(self):
        self.s.save_week(self.mon)

    def pos_map(self):
        return self.s.pos_map()

    def shift_list(self):
        sh = shifts_for_day(self.day, self.s.settings)
        for e in self.dd["entries"]:
            if e.get("shift") and e["shift"] not in sh:
                sh.append(e["shift"])
        return sorted(sh, key=SHIFTS.index)

    def entry(self, eid):
        return next((x for x in self.dd["entries"] if x["id"] == eid), None)

    def shift_entries(self):
        es = [e for e in self.dd["entries"] if e.get("shift") == self.shift]
        return sorted(es, key=lambda e: (core_parse(e.get("time_in")) is None, core_parse(e.get("time_in")) or 0,
                                         (self.s.emp(e.get("emp_id")) or {}).get("name", "")))

    def set_step(self, st):
        self.app._commit_focus()
        self.step = "Tips" if "Tips" in st else "Hours"
        self.app._day_step = self.step
        self.build()

    def set_shift(self, sh):
        self.app._commit_focus()
        self.shift = sh
        self.app._day_shift = sh
        self.drawer_entry = None
        self.build()

    # ── layout ──────────────────────────────────────────────────────────────
    def build(self, focus_entry=None):
        keep = self.sf.position() if getattr(self, "sf", None) else 0.0
        for w in self.parent.winfo_children():
            w.destroy()
        self.order, self.rows, self.hour_lbls = [], {}, {}
        self.dw = {}

        h = PageHeader(self.parent, "Hours & Tips", self.date.strftime("%A, %B %d"))
        self.app.date_nav(h.actions).pack(side="right")

        bar = tk.Frame(self.parent, bg=BG_PAGE, padx=28)
        bar.pack(fill="x")
        Segmented(bar, STEPS, STEPS[0] if self.step == "Hours" else STEPS[1], self.set_step).pack(side="left")
        counts = {sh: len([e for e in self.dd["entries"] if e.get("shift") == sh]) for sh in self.shift_list()}
        colors = {sh: SHIFT_CLR.get(sh, (ACCENT, "#FFFFFF")) for sh in counts}
        Segmented(bar, list(counts), self.shift, self.set_shift, badges=counts, colors=colors).pack(side="left", padx=16)
        acts = tk.Frame(bar, bg=BG_PAGE)
        acts.pack(side="right")
        if self.step == "Hours":
            Btn(acts, "+ Add person", lambda: self.add_entry(self.shift), "outline",
                tip=f"{MOD_SYM}N").pack(side="right")
            MenuBtn(acts, "Get hours", [
                (f"Download from Toast   {MOD_SYM}D", self.download_toast),
                (f"Import a Toast CSV file…   {MOD_SYM}I", self.import_csv),
                None,
                ("Fill from the schedule", self.fill_from_schedule),
            ], "primary").pack(side="right", padx=8)

        self._alerts()

        body = tk.Frame(self.parent, bg=BG_PAGE)
        body.pack(fill="both", expand=True, pady=(10, 0))
        self.drawer = Drawer(body)
        self.sf = ScrollFrame(body)
        self.sf.pack(side="left", fill="both", expand=True, padx=(28, 12), pady=(0, 10))

        foot = tk.Frame(self.parent, bg="#FFFFFF", highlightbackground=BORDER, highlightthickness=1)
        foot.pack(fill="x", side="bottom")
        self.foot_lbl = tk.Label(foot, text="", bg="#FFFFFF", fg=FG, font=(FONT, 11, "bold"), padx=28, pady=9)
        self.foot_lbl.pack(side="left")

        if self.step == "Hours":
            self.render_hours()
        else:
            self.render_tips()
        if self.drawer_entry and self.entry(self.drawer_entry):
            self.open_drawer(self.entry(self.drawer_entry))
        if focus_entry and focus_entry in self.rows:
            w = self.rows[focus_entry]["emp"]
            self.app.after(60, lambda: (w.focus_set(), self.sf.scroll_into_view(w)))
        else:
            self.sf.restore(keep)
        self.recalc()

    def _alerts(self):
        sched = [sl for sl in self.s.schedule_day(self.mon, self.day) if sl["shift"] == self.shift]
        have = {e.get("emp_id") for e in self.dd["entries"]}
        miss = []
        for sl in sched:
            emp = self.s.emp(sl["emp_id"])
            if emp and sl["emp_id"] not in have and emp["name"] not in miss:
                miss.append(emp["name"])
        unmatched = [e for e in self.dd["entries"] if not e.get("emp_id") and e.get("shift") == self.shift]
        if not miss and not unmatched:
            return
        box = tk.Frame(self.parent, bg=BG_PAGE, padx=28)
        box.pack(fill="x", pady=(10, 0))
        if unmatched:
            l = tk.Label(box, text=f"  ⚠ {len(unmatched)} {'person needs' if len(unmatched) == 1 else 'people need'} "
                                   f"an employee picked — click to fix  ", bg="#FEE2E2", fg="#991B1B",
                         font=(FONT, 10, "bold"), pady=4, cursor="hand2")
            l.pack(side="left", padx=(0, 8))
            l.bind("<Button-1>", lambda e: self.open_drawer(unmatched[0]))
        if miss:
            names = ", ".join(miss[:3]) + (f" +{len(miss) - 3}" if len(miss) > 3 else "")
            l = tk.Label(box, text=f"  Scheduled but not here: {names}   ·  Add them  ", bg=WARN_BG, fg=WARN_FG,
                         font=(FONT, 10, "bold"), pady=4, cursor="hand2")
            l.pack(side="left")
            l.bind("<Button-1>", lambda e: self.fill_from_schedule())
            Tooltip(l, "Adds everyone scheduled today who has no hours yet, with their scheduled times")

    # ── step 1: hours ───────────────────────────────────────────────────────
    def render_hours(self):
        es = self.shift_entries()
        card = Card(self.sf, padx=0, pady=0)
        card.pack(fill="x")
        if not es:
            empty_state(card, "⏱", f"No one on {self.shift} yet",
                        sub="Use Get hours ▾ to download them from Toast or copy the schedule, "
                            "or + Add person to type them in.")
            return
        g = tk.Frame(card, bg=BG_CARD, padx=12, pady=8)
        g.pack(fill="x")
        g.columnconfigure(0, weight=1)
        for c, t in enumerate(["Employee", "Position", "In", "Out", "Hours", ""]):
            tk.Label(g, text=t, bg=BG_CARD, fg=FG_SEC, font=(FONT, 9, "bold"), anchor="w").grid(
                row=0, column=c, sticky="w", padx=6, pady=(0, 4))
        for r, e in enumerate(es, start=1):
            self._hours_row(g, r, e)

    def _hours_row(self, g, r, e):
        s = self.s
        w = {}
        self.order.append(e["id"])
        emp = s.emp(e.get("emp_id"))
        ec = ttk.Combobox(g, values=emp_names(s, include=emp["name"] if emp else None), state="readonly", width=20)
        ec.set(emp["name"] if emp else (f"? {e['toast_raw_name']}" if e.get("toast_raw_name") else NO_EMP))
        ec.grid(row=r, column=0, padx=6, pady=3, sticky="w")
        ec.bind("<<ComboboxSelected>>", lambda ev: self.commit_emp(e, ec.get()))
        w["emp"] = ec
        pv = pos_values(s, emp)
        if e.get("position") and e["position"] not in pv:
            pv.insert(0, e["position"])
        pc = ttk.Combobox(g, values=pv, state="readonly", width=13)
        pc.set(e.get("position", ""))
        pc.grid(row=r, column=1, padx=6, sticky="w")
        pc.bind("<<ComboboxSelected>>", lambda ev: self.commit_position(e, pc))
        for c, key in ((2, "time_in"), (3, "time_out")):
            t = Inp(g, width=8)
            t.set(e.get(key, ""))
            t.grid(row=r, column=c, padx=4, ipady=3)
            t.bind("<FocusOut>", lambda ev, k=key, t=t: self.commit_time(e, k, t))
            self._nav_keys(t, e, key, lambda k=key, t=t: self.commit_time(e, k, t))
            w[key] = t
        hl = tk.Label(g, text="", bg=BG_CARD, fg=FG, font=(FONT, 12, "bold"), width=6, anchor="e", padx=4)
        hl.grid(row=r, column=4, padx=6)
        self.hour_lbls[e["id"]] = hl
        more = tk.Label(g, text="Details", bg=BG_CARD, fg=ACCENT, font=(FONT, 10, "bold"), cursor="hand2", padx=6)
        more.grid(row=r, column=5, padx=(6, 0))
        more.bind("<Button-1>", lambda ev: self.open_drawer(e))
        hover([more], BG_CARD, "#EEF2FF")
        Tooltip(more, "Tip hours, points, fixed tip, split a double, remove")
        self.rows[e["id"]] = w

    def _nav_keys(self, widget, e, key, commit):
        def move(delta):
            commit()
            i = self.order.index(e["id"]) + delta
            if 0 <= i < len(self.order):
                nxt = self.rows[self.order[i]].get(key)
                if nxt:
                    nxt.focus_set()
                    self.sf.scroll_into_view(nxt)
            return "break"
        widget.bind("<Return>", lambda ev: move(+1))
        widget.bind("<KP_Enter>", lambda ev: move(+1))
        widget.bind("<Down>", lambda ev: move(+1))
        widget.bind("<Up>", lambda ev: move(-1))

    # ── step 2: tips ────────────────────────────────────────────────────────
    def render_tips(self):
        sh = self.shift
        tips = self.dd["tips"].setdefault(sh, {"floor": 0, "bar": 0})
        card = Card(self.sf, padx=20, pady=16)
        card.pack(fill="x")
        tk.Label(card, text=f"Tips for {sh}", bg=BG_CARD, fg=FG, font=(FONT, 14, "bold")).pack(anchor="w")
        row = tk.Frame(card, bg=BG_CARD)
        row.pack(fill="x", pady=(10, 4))
        self.tip_inputs = {}
        for key, lbl in (("floor", "Floor tips"), ("bar", "Bar tips")):
            f = tk.Frame(row, bg=BG_CARD)
            f.pack(side="left", padx=(0, 28))
            tk.Label(f, text=lbl, bg=BG_CARD, fg=FG_SEC, font=(FONT, 10, "bold")).pack(anchor="w")
            inner = tk.Frame(f, bg=BG_CARD)
            inner.pack(anchor="w")
            tk.Label(inner, text="$", bg=BG_CARD, fg=FG_SEC, font=(FONT, 18)).pack(side="left")
            ent = Inp(inner, width=10, font=(FONT, 18, "bold"))
            v = to_float(tips.get(key), 0)
            ent.set(f"{v:.2f}" if v else "")
            ent.pack(side="left", ipady=4, padx=(4, 0))
            ent.bind("<FocusOut>", lambda e, k=key, w=ent: self.commit_tip_pool(sh, k, w))
            ent.bind("<Return>", lambda e, k=key, w=ent: (self.commit_tip_pool(sh, k, w),
                                                          w.tk_focusNext().focus_set(), "break")[2])
            self.tip_inputs[key] = ent
        self.tip_summary = tk.Label(card, text="", bg=BG_CARD, fg=FG_SEC, font=(FONT, 10), anchor="w", justify="left")
        self.tip_summary.pack(anchor="w", pady=(6, 0))
        self.payout = tk.Frame(self.sf, bg=BG_PAGE)
        self.payout.pack(fill="x", pady=(12, 0))
        self.render_payout()
        if not (to_float(tips.get("floor"), 0) or to_float(tips.get("bar"), 0)):
            self.app.after(80, lambda: self.tip_inputs["floor"].focus_set())

    def render_payout(self):
        for w in self.payout.winfo_children():
            w.destroy()
        pm, st = self.pos_map(), self.s.settings
        split = split_day_tips(self.dd, pm, st).get(self.shift, {"rows": {}})
        es = self.shift_entries()
        inside, left_out = [], []
        for e in es:
            p = pm.get(e.get("position"), {})
            takes = (eff_points(e, pm) > 0 and p.get("department", "FOH") == "FOH") or p.get("receives_bar_tips") \
                or to_float(p.get("bar_tip_share_pct"), 0) or e.get("tip_override") is not None
            (inside if takes else left_out).append(e)
        card = Card(self.payout, padx=0, pady=0)
        card.pack(fill="x")
        if not inside:
            empty_state(card, "\U0001F4B5", "No one to share tips with yet",
                        sub="Add the front-of-house staff in step 1 (Hours).")
            return
        g = tk.Frame(card, bg=BG_CARD, padx=16, pady=10)
        g.pack(fill="x")
        g.columnconfigure(0, weight=1)
        for c, t in enumerate(["Name", "Position", "Tip hours", "Points", "Tip"]):
            tk.Label(g, text=t, bg=BG_CARD, fg=FG_SEC, font=(FONT, 9, "bold"), anchor="w" if c < 2 else "e").grid(
                row=0, column=c, sticky="we", padx=8, pady=(0, 4))
        rows = sorted(inside, key=lambda e: -(split["rows"].get(e["id"], {}).get("total", 0)))
        for r, e in enumerate(rows, start=1):
            emp = self.s.emp(e.get("emp_id"))
            res = split["rows"].get(e["id"], {"total": 0, "override": False})
            cells = [
                tk.Label(g, text=emp["name"] if emp else f"? {e.get('toast_raw_name', '')}", bg=BG_CARD,
                         fg=FG if emp else DANGER, font=(FONT, 11, "bold"), anchor="w"),
                tk.Label(g, text=e.get("position", ""), bg=BG_CARD, fg=FG_SEC, font=(FONT, 10), anchor="w"),
                tk.Label(g, text=f"{eff_tip_hours(e, st):.2f}", bg=MANUAL_BG if e.get("tip_hours_manual") is not None else BG_CARD,
                         fg=FG, font=(FONT, 11), anchor="e", width=8),
                tk.Label(g, text=f"{eff_points(e, pm):g}", bg=MANUAL_BG if e.get("points_manual") is not None else BG_CARD,
                         fg=FG, font=(FONT, 11), anchor="e", width=6),
                tk.Label(g, text=money(res["total"]) + ("  fixed" if res.get("override") else ""),
                         bg=MANUAL_BG if res.get("override") else BG_CARD, fg=SUCCESS_FG, font=(FONT, 12, "bold"),
                         anchor="e", width=14),
            ]
            for c, w in enumerate(cells):
                w.grid(row=r, column=c, sticky="we", padx=8, pady=4)
                w.config(cursor="hand2")
                w.bind("<Button-1>", lambda ev, e=e: self.open_drawer(e))
            hover([x for x in cells if x.cget("bg") == BG_CARD], BG_CARD, "#F5F7FF")
        if left_out:
            names = ", ".join((self.s.emp(e.get("emp_id")) or {}).get("name", "?") for e in left_out[:4])
            tk.Label(self.payout, text=f"Not in the tip split (0 points / kitchen): {names}"
                                       + (f" +{len(left_out) - 4}" if len(left_out) > 4 else ""),
                     bg=BG_PAGE, fg=FG_SEC, font=(FONT, 9)).pack(anchor="w", pady=(6, 0))

    # ── side panel ──────────────────────────────────────────────────────────
    def open_drawer(self, e):
        self.drawer_entry = e["id"]
        emp = self.s.emp(e.get("emp_id"))
        title = emp["name"] if emp else (e.get("toast_raw_name") or "New person")
        src = {"toast": "From Toast", "schedule": "From the schedule", "manual": "Typed in"}.get(e.get("source"), "")
        if e.get("toast_raw_name") and e.get("source") == "toast":
            src += f" as “{e['toast_raw_name']}”"
        self.drawer.open(title, lambda b: self._drawer_body(b, e), sub=src,
                         on_close=lambda: setattr(self, "drawer_entry", None))
        if getattr(self, "foot_lbl", None):
            self.recalc()

    def _drawer_body(self, b, e):
        s, pm, st = self.s, self.pos_map(), self.s.settings
        self.dw = {}
        emp = s.emp(e.get("emp_id"))

        def row(label, widget_fn, hint=None):
            field_label(b, label, hint).pack(anchor="w", pady=(10, 2))
            w = widget_fn()
            w.pack(anchor="w", fill="x")
            return w

        ec = row("Employee", lambda: ttk.Combobox(b, values=emp_names(s, include=emp["name"] if emp else None),
                                                  state="readonly"))
        ec.set(emp["name"] if emp else NO_EMP)
        ec.bind("<<ComboboxSelected>>", lambda ev: self.commit_emp(e, ec.get()))
        pv = pos_values(s, emp)
        if e.get("position") and e["position"] not in pv:
            pv.insert(0, e["position"])
        pc = row("Position", lambda: ttk.Combobox(b, values=pv, state="readonly"))
        pc.set(e.get("position", ""))
        pc.bind("<<ComboboxSelected>>", lambda ev: self.commit_position(e, pc))
        shc = row("Shift", lambda: ttk.Combobox(b, values=SHIFTS, state="readonly"))
        shc.set(e.get("shift", ""))
        shc.bind("<<ComboboxSelected>>", lambda ev: self.change_shift(e, shc.get()))
        tf = tk.Frame(b, bg=BG_CARD)
        field_label(b, "Clock in / out").pack(anchor="w", pady=(10, 2))
        tf.pack(anchor="w")
        for key in ("time_in", "time_out"):
            t = Inp(tf, width=10)
            t.set(e.get(key, ""))
            t.pack(side="left", padx=(0, 8), ipady=3)
            t.bind("<FocusOut>", lambda ev, k=key, t=t: self.commit_time(e, k, t))
            t.bind("<Return>", lambda ev, k=key, t=t: (self.commit_time(e, k, t), t.tk_focusNext().focus_set(), "break")[2])
            self.dw[key] = t

        tk.Frame(b, bg=BORDER, height=1).pack(fill="x", pady=(16, 4))
        tk.Label(b, text="Numbers used for tips", bg=BG_CARD, fg=FG, font=(FONT, 11, "bold")).pack(anchor="w")
        tk.Label(b, text="Worked out automatically. Type a number to override it; clear the box to go back "
                         "to automatic.", bg=BG_CARD, fg=FG_SEC, font=(FONT, 9), justify="left",
                 wraplength=290).pack(anchor="w")
        for key, lbl in (("hours_manual", "Hours worked"), ("tip_hours_manual", "Tip hours"),
                         ("points_manual", "Points"), ("tip_override", "Fixed tip $")):
            f = tk.Frame(b, bg=BG_CARD)
            f.pack(fill="x", pady=(8, 0))
            tk.Label(f, text=lbl, bg=BG_CARD, fg=FG_HDR, font=(FONT, 10, "bold"), width=12, anchor="w").pack(side="left")
            t = Inp(f, width=9, justify="right")
            t.pack(side="left", ipady=3)
            t.bind("<FocusOut>", lambda ev, k=key, t=t: self.commit_manual(e, k, t))
            t.bind("<Return>", lambda ev, k=key, t=t: (self.commit_manual(e, k, t), t.tk_focusNext().focus_set(), "break")[2])
            hint = tk.Label(f, text="", bg=BG_CARD, fg=FG_SEC, font=(FONT, 9))
            hint.pack(side="left", padx=8)
            self.dw[key] = t
            self.dw[key + "_hint"] = hint
        self.dw["tip_line"] = tk.Label(b, text="", bg=BG_CARD, fg=SUCCESS_FG, font=(FONT, 12, "bold"), anchor="w",
                                       justify="left")
        self.dw["tip_line"].pack(anchor="w", pady=(12, 0))

        tk.Frame(b, bg=BORDER, height=1).pack(fill="x", pady=(16, 10))
        acts = tk.Frame(b, bg=BG_CARD)
        acts.pack(fill="x")
        if double_split_time(e, self.day, st):
            Btn(acts, "✂ Split double", lambda: self.split_double(e), "outline", small=True,
                tip="Worked brunch and dinner? Split into two shifts so they get tips from both").pack(anchor="w", pady=2)
        Btn(acts, "↺ Back to automatic", lambda: self.reset_row(e), "ghost", small=True).pack(anchor="w", pady=2)
        Btn(acts, "Remove from this day", lambda: self.delete_entry(e), "danger", small=True).pack(anchor="w", pady=(10, 2))
        self.dw["entry"] = e["id"]

    def change_shift(self, e, sh):
        if e.get("shift") == sh:
            return
        e["shift"] = sh
        self.save()
        self.shift = sh
        self.app._day_shift = sh
        self.build()

    # ── recompute & paint ───────────────────────────────────────────────────
    def recalc(self):
        pm = self.pos_map()
        st = self.s.settings
        split = split_day_tips(self.dd, pm, st)
        try:
            focus = self.app.focus_get()
        except (KeyError, tk.TclError):
            focus = None
        for eid, lbl in self.hour_lbls.items():
            e = self.entry(eid)
            if e:
                manual = e.get("hours_manual") is not None
                lbl.config(text=f"{eff_hours(e):.2f}" if (e.get("time_in") and e.get("time_out")) or manual else "—",
                           bg=MANUAL_BG if manual else BG_CARD)
        # side panel
        e = self.entry(self.dw.get("entry")) if self.dw.get("entry") else None
        if e and self.drawer.is_open:
            res = split.get(e.get("shift"), {}).get("rows", {}).get(e["id"], {})
            vals = {"hours_manual": (eff_hours(e), auto_hours(e), "{:.2f}"),
                    "tip_hours_manual": (eff_tip_hours(e, st), auto_tip_hours(e, st), "{:.2f}"),
                    "points_manual": (eff_points(e, pm), auto_points(e, pm), "{:g}"),
                    "tip_override": (res.get("total", 0.0), None, "{:.2f}")}
            for k, (v, auto, f) in vals.items():
                w = self.dw.get(k)
                if not w or not w.winfo_exists():
                    continue
                manual = e.get(k) is not None
                w.config(bg=MANUAL_BG if manual else "#FFFFFF", highlightbackground=WARN_BORD if manual else BORDER)
                if w is not focus:
                    w.set(f.format(v))
                hint = self.dw[k + "_hint"]
                if manual and auto is not None:
                    hint.config(text=f"auto: {f.format(auto)}")
                elif manual:
                    hint.config(text="fixed amount")
                else:
                    hint.config(text="auto")
            if res and not res.get("override"):
                self.dw["tip_line"].config(text=f"Tip: {money(res['total'])}" +
                                           (f"   (floor {money(res['floor'])} + bar {money(res['bar'])})" if res.get("bar") else ""))
            elif res:
                self.dw["tip_line"].config(text=f"Tip: {money(res['total'])}  (fixed)")
            else:
                self.dw["tip_line"].config(text="")
        # tips step
        if self.step == "Tips" and getattr(self, "tip_summary", None) and self.tip_summary.winfo_exists():
            t = self.dd["tips"].get(self.shift, {})
            fl, br = to_float(t.get("floor"), 0) or 0, to_float(t.get("bar"), 0) or 0
            r = split.get(self.shift)
            if r and (fl or br):
                paid = sum(x["total"] for x in r["rows"].values())
                txt = f"Total {money(fl + br)}  ·  paid out {money(paid)}"
                if r["value_per_point_hour"]:
                    txt += f"  ·  {money(r['value_per_point_hour'])} per point-hour"
                warn = []
                if r["floor_unassigned"]:
                    warn.append(f"{money(r['floor_unassigned'])} floor tips with nobody to get them")
                if r["bar_unassigned"]:
                    warn.append(f"{money(r['bar_unassigned'])} bar tips — no bartender on this shift")
                if r["overflow"]:
                    warn.append(f"fixed amounts are {money(r['overflow'])} more than the tips")
                self.tip_summary.config(text=txt + ("\n⚠ " + "; ".join(warn) if warn else ""),
                                        fg=DANGER if warn else FG_SEC)
            else:
                self.tip_summary.config(text="Type the tips for this shift — the split below updates as you go.",
                                        fg=FG_SEC)
        # footer
        es = [e for e in self.dd["entries"] if e.get("shift") == self.shift]
        tot_h = sum(eff_hours(e) for e in es)
        tot_t = sum(x["total"] for x in split.get(self.shift, {}).get("rows", {}).values())
        day_h = sum(eff_hours(e) for e in self.dd["entries"])
        self.foot_lbl.config(text=f"{self.shift}:  {len(es)} people  ·  {tot_h:.2f} h  ·  {money(tot_t)} tips"
                                  f"          Whole day: {day_h:.2f} h")

    # ── commits ─────────────────────────────────────────────────────────────
    def commit_tip_pool(self, sh, key, w):
        v = to_float(w.get(), None)
        if w.get().strip() and v is None:
            self.app.notice.warn("Tips must be a number")
            return
        v = v or 0.0
        t = self.dd["tips"].setdefault(sh, {})
        if to_float(t.get(key), 0) != v:
            t[key] = round(v, 2)
            self.save()
        w.set(f"{v:.2f}" if v else "")
        if getattr(self, "payout", None) and self.payout.winfo_exists():
            self.render_payout()
        self.recalc()

    def commit_emp(self, e, name):
        if name == NEW_EMP:
            def done(emp):
                self.commit_emp(e, emp["name"])
            quick_add_employee(self.app, self.app, e.get("toast_raw_name", ""), e.get("toast_job", ""),
                               on_done=done)
            # put the old value back in case they cancel
            self.app.after(10, self.recalc_names)
            return
        emp = next((x for x in self.s.employees if x["name"] == name), None)
        if not emp:
            return
        e["emp_id"] = emp["id"]
        if e.get("position") not in emp.get("positions", []):
            e["position"] = toast.pick_position(emp, e.get("toast_job", ""), e.get("shift", "Dinner"),
                                                self.s.settings, self.s.positions)
        if e.get("toast_raw_name") and not emp.get("toast_name") and \
                not toast.match_employee(e["toast_raw_name"], [emp]):
            if messagebox.askyesno("Remember match",
                                   f"Always match Toast name “{e['toast_raw_name']}” to {emp['name']}?",
                                   parent=self.app):
                emp["toast_name"] = e["toast_raw_name"]
                self.s.save_employees()
        self.save()
        self.build()

    def recalc_names(self):
        for eid, w in self.rows.items():
            e = next((x for x in self.dd["entries"] if x["id"] == eid), None)
            if not e:
                continue
            emp = self.s.emp(e.get("emp_id"))
            cur = emp["name"] if emp else (f"? {e['toast_raw_name']}" if e.get("toast_raw_name") else NO_EMP)
            if w["emp"].get() != cur:
                w["emp"].set(cur)

    def split_double(self, e):
        at = double_split_time(e, self.day, self.s.settings)
        if not at:
            return
        emp = self.s.emp(e.get("emp_id"))
        if not messagebox.askyesno("Split double",
                                   f"Split {emp['name'] if emp else 'this entry'} ({e['time_in']} \u2013 {e['time_out']}) "
                                   f"at {at} into {day_shift_name(self.day, self.s.settings)} + Dinner?\n\n"
                                   "They'll get tips from both shifts.", parent=self.app):
            return
        a, b = split_entry(e, at, self.day, self.s.settings, gen_id())
        i = self.dd["entries"].index(e)
        self.dd["entries"][i:i + 1] = [a, b]
        self.drawer_entry = None
        self.save()
        self.build()
        self.app.notice.show("Split into two shifts \u2014 adjust the times if needed")

    def commit_position(self, e, pc):
        v = pc.get()
        if v == SEP:
            pc.set(e.get("position", ""))
            return
        emp = self.s.emp(e.get("emp_id"))
        if ensure_position(self.s, emp, v):
            self.app.notice.show(f"Added {v} to {emp['name']}'s positions")
        self.commit_field(e, "position", v, rebuild=False)

    def commit_field(self, e, key, val, rebuild):
        if e.get(key) == val:
            return
        e[key] = val
        self.save()
        self.build() if rebuild else self.recalc()

    def commit_time(self, e, key, w):
        raw = w.get().strip()
        v = norm_time(raw)
        if raw and not v:
            self.app.notice.warn(f"Can't read time “{raw}” — use e.g. 4:05 PM")
            w.set(e.get(key, ""))
            return
        w.set(v)
        if e.get(key, "") != v:
            e[key] = v
            self.save()
            # keep the table and the side panel showing the same time
            others = [self.rows.get(e["id"], {}).get(key)]
            if self.dw.get("entry") == e["id"]:
                others.append(self.dw.get(key))
            for o in others:
                if o is not None and o is not w and o.winfo_exists():
                    o.set(v)
        self.recalc()

    def commit_manual(self, e, key, w):
        raw = w.get().strip()
        pm, st = self.pos_map(), self.s.settings
        if not raw:
            new = None
        else:
            new = to_float(raw)
            if new is None:
                self.app.notice.warn(f"“{raw}” is not a number")
                self.recalc()
                return
            if key == "tip_override":
                auto = self._auto_tip_total(e)
            else:
                auto = {"hours_manual": auto_hours(e),
                        "tip_hours_manual": auto_tip_hours(e, st),
                        "points_manual": auto_points(e, pm)}[key]
            if e.get(key) is None and abs(new - auto) < 0.005:
                new = None          # unchanged automatic value, not an override
        if e.get(key) != new:
            e[key] = new
            self.save()
            if self.step == "Tips" and getattr(self, "payout", None) and self.payout.winfo_exists():
                self.render_payout()
        self.recalc()

    def _auto_tip_total(self, e):
        saved = e.get("tip_override")
        e["tip_override"] = None
        r = split_day_tips(self.dd, self.pos_map(), self.s.settings)
        e["tip_override"] = saved
        return r.get(e.get("shift"), {}).get("rows", {}).get(e["id"], {}).get("total", 0.0)

    def reset_row(self, e):
        for k in ("hours_manual", "tip_hours_manual", "points_manual", "tip_override"):
            e[k] = None
        self.save()
        if self.step == "Tips":
            self.render_payout()
        self.recalc()
        self.app.notice.show("Back to automatic values")

    def delete_entry(self, e):
        emp = self.s.emp(e.get("emp_id"))
        if messagebox.askyesno("Remove entry", f"Remove {emp['name'] if emp else 'this entry'} "
                                               f"({e.get('shift')}) from this day?", parent=self.app):
            self.dd["entries"].remove(e)
            if self.drawer_entry == e["id"]:
                self.drawer_entry = None
            self.save()
            self.build()

    def add_new(self):
        if self.step != "Hours":
            self.step = self.app._day_step = "Hours"
        self.add_entry(self.shift)

    def add_entry(self, shift):
        dflt = shift or self.shift
        nid = gen_id()
        self.dd["entries"].append({"id": nid, "emp_id": None, "position": "", "shift": dflt,
                                   "time_in": "", "time_out": "", "source": "manual"})
        self.save()
        self.build(focus_entry=nid)
        self.app.notice.show("New row added \u2014 type a name to pick the employee")

    # ── schedule → entries ──────────────────────────────────────────────────
    def fill_from_schedule(self):
        sched = self.s.schedule_day(self.mon, self.day)
        if not sched:
            self.app.notice.warn(f"Nothing scheduled on {self.day}")
            return
        have = {(e.get("emp_id"), e.get("shift")) for e in self.dd["entries"]}
        n = 0
        for sl in sched:
            if (sl["emp_id"], sl["shift"]) in have:
                continue
            self.dd["entries"].append({"id": gen_id(), "emp_id": sl["emp_id"], "position": sl.get("position", ""),
                                       "shift": sl["shift"], "time_in": sl.get("start", ""),
                                       "time_out": sl.get("end", ""), "source": "schedule"})
            n += 1
        self.save()
        self.build()
        self.app.notice.show(f"Added {n} people from the schedule" if n else "Everyone scheduled is already here")

    # ── Toast ───────────────────────────────────────────────────────────────
    def import_csv(self):
        p = filedialog.askopenfilename(parent=self.app, title="Toast TimeEntries CSV",
                                       filetypes=[("CSV", "*.csv"), ("All files", "*.*")])
        if not p:
            return
        try:
            rows = toast.parse_csv_file(p)
        except Exception as ex:
            messagebox.showerror("Can't read CSV", str(ex), parent=self.app)
            return
        self.preview(rows)

    def download_toast(self):
        try:
            import paramiko  # noqa: F401
        except ImportError:
            messagebox.showerror("Missing package", "Toast download needs 'paramiko'.\n\n"
                                 "Install it with:  pip3 install paramiko\n\nOr use Import Toast CSV.",
                                 parent=self.app)
            return
        key = toast.find_key(self.s.settings)
        if not key:
            if not messagebox.askokcancel(
                    "Toast isn't set up on this computer",
                    "Pick your Toast setup file (from another computer) or your private key file.\n\n"
                    "You can also do this in Settings \u2192 Toast.", parent=self.app):
                return
            p = filedialog.askopenfilename(parent=self.app, title="Toast setup file or private key")
            if not p:
                return
            try:
                key = toast.load_key_or_setup(p, self.s.settings)
            except Exception as ex:
                messagebox.showerror("Can't use that file", str(ex), parent=self.app)
                return
            self.s.save_settings()
        prog = Dialog(self.app, "Toast", width=380, height=120)
        tk.Label(prog.body, text=f"Downloading time entries for {self.date.strftime('%a %b %d')}…",
                 bg=BG_PAGE, font=(FONT, 12)).pack(pady=16)
        prog.show()
        ymd = self.date.strftime("%Y%m%d")

        def work():
            try:
                text = toast.sftp_download(self.s.settings, key, ymd)
                self.app.after(0, lambda: done(text, None))
            except Exception as ex:
                self.app.after(0, lambda ex=ex: done(None, ex))

        def done(text, err):
            try:
                prog.destroy()
            except tk.TclError:
                pass
            if err:
                messagebox.showerror("Toast download failed", str(err), parent=self.app)
                return
            self.preview(toast.parse_csv_text(text))

        threading.Thread(target=work, daemon=True).start()

    def preview(self, rows):
        if not rows:
            messagebox.showinfo("Toast", "No time entries in that file.", parent=self.app)
            return
        s = self.s
        entries = toast.rows_to_entries(rows, s.employees, self.day, s.settings, s.positions)
        entries.sort(key=lambda e: (e["shift"] == "Dinner", core_parse(e["time_in"]) or 0))
        dlg = Dialog(self.app, f"Toast entries \u2014 {self.date.strftime('%A %b %d')}", width=1180,
                     height=min(int(self.app.winfo_height() * 0.92), 260 + 38 * len(entries)))

        banner = tk.Frame(dlg.body, bg=BG_PAGE)
        banner.pack(fill="x", pady=(0, 8))
        ban_lbl = tk.Label(banner, text="", bg=BG_PAGE, font=(FONT, 11, "bold"), anchor="w", justify="left")
        ban_lbl.pack(side="left")
        add_all_btn = Btn(banner, "+ Add all new people", lambda: add_all(), "primary", small=True,
                          tip="Create each unknown Toast name as a new employee, one after another")

        sf = ScrollFrame(dlg.body, bg=BG_CARD)
        sf.pack(fill="both", expand=True)
        g = tk.Frame(sf, bg=BG_CARD, padx=8, pady=6)
        g.pack(fill="x")
        heads = ["", "Toast name", "", "Employee", "Position", "Shift", "In", "Out", "Hrs", ""]
        for c, t in enumerate(heads):
            tk.Label(g, text=t, bg=BG_CARD, fg=FG_SEC, font=(FONT, 9, "bold")).grid(row=0, column=c, sticky="w", padx=3)

        rows_ui = []          # dicts per row

        def by_name(n):
            return next((x for x in s.employees if x["name"] == n), None)

        def update_banner():
            unknown = sorted({r["e"]["toast_raw_name"] for r in rows_ui
                              if r["inc"].get() and not by_name(r["ec"].get())})
            if unknown:
                ban_lbl.config(text=f"\u26A0 {len(unknown)} name{'s' if len(unknown) > 1 else ''} not recognised: "
                                    f"{', '.join(unknown)}.   Click + Add to create them, or pick an existing employee.",
                               fg=DANGER, wraplength=880)
                if not add_all_btn.winfo_ismapped():
                    add_all_btn.pack(side="right")
            else:
                ban_lbl.config(text="\u2713 Everyone is matched. Check shifts and times, then press Enter to import.",
                               fg=SUCCESS_FG, wraplength=880)
                add_all_btn.pack_forget()

        def set_emp(r, emp, spread=True):
            """Assign emp to row r (and every other unmatched row with the same Toast name)."""
            targets = [r]
            if spread:
                targets += [x for x in rows_ui if x is not r and x["e"]["toast_raw_name"] == r["e"]["toast_raw_name"]
                            and not by_name(x["ec"].get())]
            for x in targets:
                x["ec"].set(emp["name"])
                x["pc"].config(values=pos_values(s, emp))
                x["pc"].set(toast.pick_position(emp, x["e"].get("toast_job", ""), x["shc"].get(),
                                                s.settings, s.positions))
                x["name_lbl"].config(fg=FG, font=(FONT, 10))
                x["add_btn"].grid_remove()
            names = emp_names(s)
            for x in rows_ui:
                x["ec"].config(values=names)
            update_banner()

        def quick_add(r):
            quick_add_employee(self.app, dlg, r["e"]["toast_raw_name"], r["e"].get("toast_job", ""),
                               on_done=lambda emp, r=r: set_emp(r, emp))

        def add_all():
            todo = []
            for r in rows_ui:
                if r["inc"].get() and not by_name(r["ec"].get()) and \
                        r["e"]["toast_raw_name"] not in [t["e"]["toast_raw_name"] for t in todo]:
                    todo.append(r)

            def nxt(_emp=None, i=0):
                while i < len(todo) and by_name(todo[i]["ec"].get()):
                    i += 1
                if i < len(todo):
                    r = todo[i]
                    quick_add_employee(self.app, dlg, r["e"]["toast_raw_name"], r["e"].get("toast_job", ""),
                                       on_done=lambda emp, r=r, i=i: (set_emp(r, emp), nxt(emp, i + 1)))
            nxt()

        names = emp_names(s)
        for i, e in enumerate(entries, start=1):
            emp = s.emp(e["emp_id"])
            r = {"e": e}
            r["inc"] = tk.BooleanVar(value=True)
            tk.Checkbutton(g, variable=r["inc"], bg=BG_CARD, command=update_banner).grid(row=i, column=0)
            r["name_lbl"] = tk.Label(g, text=e["toast_raw_name"][:24], bg=BG_CARD, fg=FG if emp else DANGER,
                                     font=(FONT, 10, "normal" if emp else "bold"))
            r["name_lbl"].grid(row=i, column=1, sticky="w", padx=3)
            r["add_btn"] = Btn(g, "+ Add", lambda r=r: quick_add(r), "primary", small=True,
                               tip="Create this person as a new employee")
            r["add_btn"].grid(row=i, column=2, padx=3)
            if emp:
                r["add_btn"].grid_remove()
            ec = ttk.Combobox(g, values=names, state="readonly", width=19)
            ec.set(emp["name"] if emp else NO_EMP)
            ec.grid(row=i, column=3, padx=3, pady=3)
            r["ec"] = ec
            pc = ttk.Combobox(g, values=pos_values(s, emp), state="readonly", width=13)
            pc.bind("<<ComboboxSelected>>", lambda ev, pc=pc, e=e: pc.set(e["position"]) if pc.get() == SEP else None)
            pc.set(e["position"])
            pc.grid(row=i, column=4, padx=3)
            r["pc"] = pc
            shc = ttk.Combobox(g, values=SHIFTS, state="readonly", width=8)
            shc.set(e["shift"])
            shc.grid(row=i, column=5, padx=3)
            r["shc"] = shc
            r["ti"] = Inp(g, width=8)
            r["ti"].set(e["time_in"])
            r["ti"].grid(row=i, column=6, padx=3, ipady=2)
            r["to"] = Inp(g, width=8)
            r["to"].set(e["time_out"])
            r["to"].grid(row=i, column=7, padx=3, ipady=2)
            tk.Label(g, text=f"{e['toast_hours']:.2f}", bg=BG_CARD, fg=FG_SEC).grid(row=i, column=8, padx=3)
            is_double = bool(double_split_time(e, self.day, s.settings))
            r["split"] = tk.BooleanVar(value=is_double)
            if is_double:
                cb = tk.Checkbutton(g, text="Split double", variable=r["split"], bg=BG_CARD,
                                    fg=ACCENT, font=(FONT, 9, "bold"))
                cb.grid(row=i, column=9, sticky="w")
                Tooltip(cb, f"Worked both shifts: split at {double_split_time(e, self.day, s.settings)} "
                            f"into {day_shift_name(self.day, s.settings)} + Dinner so they get tips for both")

            def on_emp(ev, r=r):
                v = r["ec"].get()
                if v == NEW_EMP:
                    r["ec"].set(NO_EMP)
                    quick_add(r)
                    return
                em = by_name(v)
                if em:
                    set_emp(r, em)
            ec.bind("<<ComboboxSelected>>", on_emp)
            rows_ui.append(r)
        update_banner()

        replace = tk.BooleanVar(value=True)
        tk.Checkbutton(dlg.bar, text="Replace earlier Toast/schedule entries for these people",
                       variable=replace, bg=BG_PAGE, font=(FONT, 10)).pack(side="left")

        def do_import():
            unknown = [r for r in rows_ui if r["inc"].get() and not by_name(r["ec"].get())]
            if unknown and not messagebox.askyesno(
                    "Some people not matched",
                    f"{len(unknown)} row(s) have no employee yet.\n\nImport them anyway? "
                    "(You can pick the employee later on the Day page.)", parent=dlg):
                return
            new = []
            learned = 0
            for r in rows_ui:
                if not r["inc"].get():
                    continue
                e = r["e"]
                em = by_name(r["ec"].get())
                if em and e["emp_id"] != em["id"] and not em.get("toast_name") and \
                        not toast.match_employee(e["toast_raw_name"], [em]):
                    em["toast_name"] = e["toast_raw_name"]     # remember the match next time
                    learned += 1
                e["emp_id"] = em["id"] if em else None
                e["position"] = r["pc"].get()
                ensure_position(s, em, e["position"])
                e["shift"] = r["shc"].get()
                e["time_in"] = norm_time(r["ti"].get())
                e["time_out"] = norm_time(r["to"].get())
                at = double_split_time(e, self.day, s.settings) if r["split"].get() else None
                if at:
                    a, b = split_entry(e, at, self.day, s.settings, gen_id())
                    new += [a, b]
                else:
                    new.append(e)
            if replace.get():
                ids = {e["emp_id"] for e in new if e["emp_id"]}
                self.dd["entries"] = [x for x in self.dd["entries"]
                                      if not (x.get("source") == "toast"
                                              or (x.get("source") == "schedule" and x.get("emp_id") in ids))]
            self.dd["entries"].extend(new)
            if learned:
                s.save_employees()
            self.save()
            dlg.destroy()
            self.build()
            miss = len([e for e in new if not e["emp_id"]])
            msg = f"Imported {len(new)} entries"
            if miss:
                self.app.notice.warn(msg + f" \u2014 {miss} still need an employee")
            else:
                self.app.notice.show(msg)

        dlg.buttons("Import", do_import)
        dlg.show(focus=dlg)

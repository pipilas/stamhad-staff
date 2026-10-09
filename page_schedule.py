"""Schedule page — build the week: pick who works each day and shift."""

from __future__ import annotations

import copy
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import timedelta

from core import DAYS, shifts_for_day, scheduled_hours, norm_time, parse_time, date_of
from store import gen_id
from quick import quick_add_employee, pos_values, ensure_position, SEP
from ui import *  # noqa: F401,F403
from core import SHIFTS
import exports


def short_time(t: str) -> str:
    m = parse_time(t)
    if m is None:
        return ""
    h, mi = divmod(m % 1440, 60)
    ap = "a" if h < 12 else "p"
    h12 = h % 12 or 12
    return f"{h12}{ap}" if mi == 0 else f"{h12}:{mi:02d}{ap}"


def slot_text(slot) -> str:
    a, z = short_time(slot.get("start")), short_time(slot.get("end"))
    t = f"{a}–{z}" if a and z else (a or "")
    return t


class SchedulePage:
    def __init__(self, app, parent):
        self.app = app
        self.s = app.store
        self.mon = app.mon
        self.week = self.s.week(self.mon)
        self.parent = parent
        self.build()

    def save(self):
        self.s.save_week(self.mon)

    # ── layout ──────────────────────────────────────────────────────────────
    def build(self):
        keep = self.sf.position() if getattr(self, "sf", None) else 0.0
        for w in self.parent.winfo_children():
            w.destroy()
        self.view = getattr(self.app, "_sched_view", "Week")
        self.day_sel = getattr(self.app, "_sched_day", None) or DAYS[self.app.sel_date.weekday()]
        total = sum(len(v) for v in self.week["schedule"].values())
        h = PageHeader(self.parent, "Schedule", f"{total} shifts this week" if total else "Nothing scheduled yet")
        MenuBtn(h.actions, "More", [
            ("Copy last week", self.copy_last_week),
            ("Clear this week", self.clear_week),
            None,
            (f"Export PDF   {MOD_SYM}E", self.export_pdf),
            ("Export CSV", self.export_csv),
        ], "ghost").pack(side="right", padx=(10, 0))
        self.app.date_nav(h.actions).pack(side="right")

        bar = tk.Frame(self.parent, bg=BG_PAGE, padx=28)
        bar.pack(fill="x", pady=(0, 10))
        Segmented(bar, ["Week", "Day"], self.view, self.set_view, size=10).pack(side="left")
        if self.view == "Day":
            labels = [f"{d[:3]} {date_of(self.mon, d).day}" for d in DAYS]
            counts = {lab: len(self.week["schedule"].get(d, [])) or "" for lab, d in zip(labels, DAYS)}
            cur = labels[DAYS.index(self.day_sel)]
            Segmented(bar, labels, cur, lambda lab: self.set_day(DAYS[labels.index(lab)]),
                      badges=counts, size=10).pack(side="left", padx=16)
        sbar = tk.Frame(self.parent, bg=BG_PAGE, padx=28)
        sbar.pack(fill="x", pady=(0, 10))
        self.search_box = SearchBox(sbar, self.on_query, "Find an employee or position", width=30,
                                    value=getattr(self.app, "_sched_query", ""))
        self.search_box.pack(side="left")
        tk.Label(sbar, text=("Click a day to pick who works  \u00b7  click a cell to change one person"
                             if self.view == "Week" else "Click someone to change their shift"),
                 bg=BG_PAGE, fg=FG_SEC, font=(FONT, 10)).pack(side="right")

        self.sf = ScrollFrame(self.parent)
        self.sf.pack(fill="both", expand=True, padx=28, pady=(0, 14))
        self.sf.restore(keep)
        if not [e for e in self.s.employees if e.get("active", True)]:
            empty_state(self.sf, "\U0001F465", "Add your employees first", "Go to Employees",
                        lambda: self.app.go("Employees"))
            return
        self.week_holder = tk.Frame(self.sf, bg=BG_PAGE)
        self.week_holder.pack(fill="x")
        self.render_week()

    def on_query(self, q):
        self.app._sched_query = q
        self.render_week()
        self.sf.to_top()

    def render_week(self):
        for w in self.week_holder.winfo_children():
            w.destroy()
        if self.view == "Week":
            self.build_week(self.week_holder)
        else:
            self.build_day(self.week_holder)

    def set_view(self, v):
        self.app._sched_view = v
        self.sf = None
        self.build()

    def set_day(self, d):
        self.app._sched_day = d
        self.build()

    def add_new(self):
        self.day_picker(self.day_sel)

    def _slots_by(self):
        slots_by = {}
        for day, slots in self.week["schedule"].items():
            for sl in slots:
                slots_by.setdefault((sl["emp_id"], day), []).append(sl)
        return slots_by

    def build_week(self, holder):
        g = tk.Frame(holder, bg=BORDER)
        g.pack(fill="x")
        g.columnconfigure(0, weight=0, minsize=180)
        for c in range(1, 8):
            g.columnconfigure(c, weight=1, uniform="day", minsize=92)
        g.columnconfigure(8, weight=0, minsize=52)
        tk.Label(g, text="", bg="#F9FAFB").grid(row=0, column=0, sticky="nsew", padx=(0, 1), pady=(0, 1))
        for i, day in enumerate(DAYS):
            d = date_of(self.mon, day)
            h = tk.Frame(g, bg="#F9FAFB", cursor="hand2")
            h.grid(row=0, column=i + 1, sticky="nsew", padx=(0, 1), pady=(0, 1))
            l1 = tk.Label(h, text=day[:3].upper(), bg="#F9FAFB", fg=FG_SEC, font=(FONT, 9, "bold"), cursor="hand2")
            l1.pack(pady=(6, 0))
            l2 = tk.Label(h, text=str(d.day), bg="#F9FAFB", fg=FG, font=(FONT, 14, "bold"), cursor="hand2")
            l2.pack(pady=(0, 6))
            for w in (h, l1, l2):
                w.bind("<Button-1>", lambda e, day=day: self.day_picker(day))
            hover([h, l1, l2], "#F9FAFB", "#E0E7FF")
            Tooltip(l2, f"Pick who works {day}")
        tk.Label(g, text="hrs", bg="#F9FAFB", fg=FG_SEC, font=(FONT, 9, "bold")).grid(
            row=0, column=8, sticky="nsew", pady=(0, 1))

        slots_by = self._slots_by()
        in_week = {k[0] for k in slots_by}
        emps = [e for e in self.s.all_employees_sorted() if e.get("active", True) or e["id"] in in_week]
        q = getattr(self.app, "_sched_query", "")
        if q:
            emps = [e for e in emps if matches(q, e["name"], *e.get("positions", []))]
            if not emps:
                tk.Label(holder, text=f"Nobody matches \u201c{q}\u201d.", bg=BG_PAGE, fg=FG_SEC,
                         font=(FONT, 12), pady=30).pack()
                return
        row = 1
        cur_dept = None
        for idx, e in enumerate(emps):
            dept = self.s.emp_dept(e)
            if dept != cur_dept:
                cur_dept = dept
                sec = tk.Frame(g, bg="#FFFFFF")
                sec.grid(row=row, column=0, columnspan=9, sticky="nsew", pady=(0, 1))
                tk.Label(sec, text="FRONT OF HOUSE" if dept == "FOH" else "BACK OF HOUSE", bg="#FFFFFF",
                         fg=FOH_BG if dept == "FOH" else BOH_BG, font=(FONT, 9, "bold"), padx=12, pady=4).pack(anchor="w")
                row += 1
            bg = "#FFFFFF"
            tk.Label(g, text=e["name"], bg=bg, fg=FG, font=(FONT, 11), anchor="w", padx=12).grid(
                row=row, column=0, sticky="nsew", padx=(0, 1), pady=(0, 1))
            total = 0.0
            for i, day in enumerate(DAYS):
                slots = slots_by.get((e["id"], day), [])
                total += sum(scheduled_hours(s) for s in slots)
                self._cell(g, row, i + 1, e, day, slots, bg)
            tk.Label(g, text=f"{total:g}" if total else "", bg=bg, fg=FG_SEC,
                     font=(FONT, 10)).grid(row=row, column=8, sticky="nsew", pady=(0, 1))
            row += 1
        tk.Label(g, text="Total", bg="#F9FAFB", fg=FG_SEC, font=(FONT, 10, "bold"),
                 anchor="w", padx=12, pady=6).grid(row=row, column=0, sticky="nsew", padx=(0, 1))
        for i, day in enumerate(DAYS):
            f = tk.Frame(g, bg="#F9FAFB")
            f.grid(row=row, column=i + 1, sticky="nsew", padx=(0, 1))
            slots = self.week["schedule"].get(day, [])
            inner = tk.Frame(f, bg="#F9FAFB")
            inner.pack(pady=6)
            for sh in shifts_for_day(day, self.s.settings):
                n = len([s for s in slots if s["shift"] == sh])
                if n:
                    pill(inner, f"{sh[0]} {n}", *SHIFT_CLR.get(sh, ("#D1D5DB", FG)), size=8).pack(side="left", padx=1)
        tk.Frame(g, bg="#F9FAFB").grid(row=row, column=8, sticky="nsew")
        legend = tk.Frame(holder, bg=BG_PAGE)
        legend.pack(anchor="w", pady=(8, 0))
        for sh in SHIFT_CLR:
            shift_pill(legend, f"{sh[0]} = {sh}", 8).pack(side="left", padx=(0, 6))
        tk.Label(legend, text="Times show only when they differ from the usual (Settings → Schedule).",
                 bg=BG_PAGE, fg=FG_SEC, font=(FONT, 9)).pack(side="left", padx=6)

    def _cell(self, g, row, col, emp, day, slots, bg):
        """Whole cell painted in the shift colour; two shifts = split diagonally."""
        order = {"Morning": 0, "Brunch": 0, "Dinner": 1}
        dt = self.s.settings.get("default_times", {})
        slots = sorted(slots, key=lambda s: order.get(s["shift"], 2))
        cv = tk.Canvas(g, bg=bg, height=34, width=10, highlightthickness=0, bd=0, cursor="hand2")
        cv.grid(row=row, column=col, sticky="nsew", padx=(0, 1), pady=(0, 1))
        state = {"hover": False}

        def label(sl):
            usual = dt.get(sl["shift"], ["", ""])
            txt = sl["shift"][0]
            if (sl.get("start"), sl.get("end")) != tuple(usual) and slot_text(sl):
                txt += " " + slot_text(sl)
            return txt

        def draw(_=None):
            cv.delete("all")
            w, h = max(cv.winfo_width(), 2), max(cv.winfo_height(), 2)
            if not slots:
                if state["hover"]:
                    cv.create_rectangle(0, 0, w, h, fill="#EEF2FF", outline="")
                    cv.create_text(w / 2, h / 2, text="+", fill=ACCENT, font=(FONT, 12, "bold"))
                return
            if len(slots) == 1:
                sbg, sfg = SHIFT_CLR.get(slots[0]["shift"], ("#E5E7EB", FG))
                cv.create_rectangle(0, 0, w, h, fill=sbg, outline="")
                cv.create_text(w / 2, h / 2, text=label(slots[0]), fill=sfg, font=(FONT, 10, "bold"))
            elif len(slots) == 2:
                (b1, f1), (b2, f2) = (SHIFT_CLR.get(sl["shift"], ("#E5E7EB", FG)) for sl in slots)
                cv.create_polygon(0, 0, w, 0, 0, h, fill=b1, outline="")       # top-left: day shift
                cv.create_polygon(w, 0, w, h, 0, h, fill=b2, outline="")       # bottom-right: dinner
                cv.create_line(w, 0, 0, h, fill="#FFFFFF", width=1)
                cv.create_text(5, 3, text=label(slots[0]), fill=f1, anchor="nw", font=(FONT, 9, "bold"))
                cv.create_text(w - 5, h - 3, text=label(slots[1]), fill=f2, anchor="se", font=(FONT, 9, "bold"))
            else:
                n = len(slots)
                for i, sl in enumerate(slots):
                    sbg, sfg = SHIFT_CLR.get(sl["shift"], ("#E5E7EB", FG))
                    cv.create_rectangle(w * i / n, 0, w * (i + 1) / n, h, fill=sbg, outline="")
                    cv.create_text(w * (i + .5) / n, h / 2, text=sl["shift"][0], fill=sfg, font=(FONT, 9, "bold"))
            if state["hover"]:
                cv.create_rectangle(1, 1, w - 1, h - 1, outline=ACCENT, width=2)

        if slots:
            tips = []
            for sl in slots:
                t = f"{sl['shift']}  {slot_text(sl) or ''}"
                if sl.get("position") and sl["position"] != self.s.emp_main_position(emp):
                    t += f"  as {sl['position']}"
                if sl.get("note"):
                    t += f"\n\u270E {sl['note']}"
                tips.append(t)
            tipw = Tooltip(cv, "\n".join(tips))
        else:
            tipw = None

        def set_hover(on):
            state["hover"] = on
            draw()
        cv.bind("<Configure>", draw)
        def click(_e=None):
            if tipw:
                tipw._hide()
            self.cell_dialog(emp, day)
        cv.bind("<Button-1>", click)
        cv.bind("<Enter>", lambda e: set_hover(True), add="+")
        cv.bind("<Leave>", lambda e: set_hover(False), add="+")

    def build_day(self, holder):
        day = self.day_sel
        q = getattr(self.app, "_sched_query", "")
        slots = self.week["schedule"].get(day, [])
        d = date_of(self.mon, day)
        top = tk.Frame(holder, bg=BG_PAGE)
        top.pack(fill="x", pady=(0, 10))
        tk.Label(top, text=d.strftime("%A, %B %d"), bg=BG_PAGE, fg=FG, font=(FONT, 14, "bold")).pack(side="left")
        Btn(top, "Pick staff for this day", lambda: self.day_picker(day), tip=f"{MOD_SYM}N").pack(side="right")
        cols = tk.Frame(holder, bg=BG_PAGE)
        cols.pack(fill="x")
        shifts = shifts_for_day(day, self.s.settings)
        for c, sh in enumerate(shifts):
            cols.columnconfigure(c, weight=1, uniform="s")
            card = Card(cols, padx=0, pady=0)
            card.grid(row=0, column=c, sticky="nsew", padx=(0 if c == 0 else 10, 0))
            hd = tk.Frame(card, bg=BG_CARD, padx=16, pady=12)
            hd.pack(fill="x")
            shift_pill(hd, sh, 11).pack(side="left")
            mine = [sl for sl in slots if sl["shift"] == sh]
            if q:
                emps_by = {e["id"]: e for e in self.s.employees}
                mine = [sl for sl in mine if matches(q, emps_by.get(sl["emp_id"], {}).get("name", ""),
                                                     sl.get("position", ""))]
            tk.Label(hd, text=f"{len(mine)} people", bg=BG_CARD, fg=FG_SEC, font=(FONT, 11)).pack(side="left", padx=10)
            usual = self.s.settings.get("default_times", {}).get(sh, ["", ""])
            tk.Label(hd, text=f"usually {short_time(usual[0])}\u2013{short_time(usual[1])}", bg=BG_CARD, fg=FG_SEC,
                     font=(FONT, 9)).pack(side="right")
            tk.Frame(card, bg=BORDER, height=1).pack(fill="x")
            if not mine:
                tk.Label(card, text="Nobody matches" if q else "Nobody yet", bg=BG_CARD, fg=FG_SEC, font=(FONT, 11), pady=24).pack()
            emps = {e["id"]: e for e in self.s.employees}
            mine.sort(key=lambda sl: (self.s.emp_dept(emps.get(sl["emp_id"], {})) != "FOH",
                                      emps.get(sl["emp_id"], {}).get("name", "")))
            for sl in mine:
                e = emps.get(sl["emp_id"])
                if not e:
                    continue
                r = tk.Frame(card, bg=BG_CARD, cursor="hand2", padx=16, pady=7)
                r.pack(fill="x")
                n = tk.Label(r, text=e["name"], bg=BG_CARD, fg=FG, font=(FONT, 11, "bold"), cursor="hand2")
                n.pack(side="left")
                info = sl.get("position", "")
                if sl.get("start") or sl.get("end"):
                    info += f"   {slot_text(sl)}"
                i = tk.Label(r, text=info, bg=BG_CARD, fg=FG_SEC, font=(FONT, 10), cursor="hand2")
                i.pack(side="right")
                for w in (r, n, i):
                    w.bind("<Button-1>", lambda ev, e=e: self.cell_dialog(e, day))
                hover([r, n, i], BG_CARD, "#F5F7FF")

    # ── dialogs ─────────────────────────────────────────────────────────────
    def cell_dialog(self, emp, day):
        s = self.s
        sched = s.schedule_day(self.mon, day)
        mine = {sl["shift"]: sl for sl in sched if sl["emp_id"] == emp["id"]}
        d = date_of(self.mon, day)
        dlg = Dialog(self.app, f"{emp['name']} — {day} {d.month}/{d.day}", width=620)
        b = dlg.body
        shifts = shifts_for_day(day, s.settings)
        for sh in mine:
            if sh not in shifts:
                shifts.append(sh)
        for c, t in enumerate(["Shift", "Position", "Start", "End", "Note"]):
            dlg.label(b, t).grid(row=0, column=c, sticky="w", padx=4, pady=(0, 4))
        rows = {}
        for r, sh in enumerate(shifts, start=1):
            sl = mine.get(sh)
            v = tk.BooleanVar(value=sl is not None)
            f = tk.Frame(b, bg=BG_PAGE)
            f.grid(row=r, column=0, sticky="w", padx=4, pady=4)
            tk.Checkbutton(f, variable=v, bg=BG_PAGE).pack(side="left")
            shift_pill(f, sh).pack(side="left")
            pc = ttk.Combobox(b, values=pos_values(s, emp), state="readonly", width=16)
            pc.set((sl or {}).get("position") or s.emp_main_position(emp))
            pc.grid(row=r, column=1, padx=4)
            dflt = s.settings["default_times"].get(sh, ["", ""])
            a = Inp(b, width=9)
            a.set((sl or {}).get("start", dflt[0]))
            a.grid(row=r, column=2, padx=4, ipady=3)
            z = Inp(b, width=9)
            z.set((sl or {}).get("end", dflt[1]))
            z.grid(row=r, column=3, padx=4, ipady=3)
            smart_time_field(a, lambda d=dflt: {"near": d[0] or None, "start": True})
            smart_time_field(z, lambda a=a, d=dflt: {"after": a.get() or None, "near": d[1] or None})
            n = Inp(b, width=16)
            n.set((sl or {}).get("note", ""))
            n.grid(row=r, column=4, padx=4, ipady=3)
            for w in (a, z, n):
                w.bind("<Key>", lambda e, v=v: v.set(True), add="+")
            pc.bind("<<ComboboxSelected>>", lambda e, v=v: v.set(True))
            rows[sh] = (v, pc, a, z, n)
        tk.Label(b, text="Times are optional. Tick a shift to schedule it.", bg=BG_PAGE, fg=FG_SEC,
                 font=(FONT, 9)).grid(row=len(shifts) + 1, column=0, columnspan=5, sticky="w", pady=(8, 0))

        def save():
            fix_times([w for (v, pc, a, z, n) in rows.values() for w in (a, z)])
            for sh, (v, pc, a, z, n) in rows.items():
                for w, lbl in ((a, "start"), (z, "end")):
                    if w.get().strip() and not norm_time(w.get()):
                        messagebox.showwarning("Check time", f"Can't read {lbl} time “{w.get()}”",
                                               parent=dlg)
                        return
            for sh, (v, pc, a, z, n) in rows.items():
                sl = mine.get(sh)
                if v.get():
                    if not sl:
                        sl = {"id": gen_id(), "emp_id": emp["id"], "shift": sh}
                        sched.append(sl)
                    ensure_position(s, emp, pc.get() if pc.get() != SEP else "")
                    sl.update({"position": pc.get() if pc.get() != SEP else s.emp_main_position(emp),
                               "start": norm_time(a.get()),
                               "end": norm_time(z.get()), "note": n.get().strip()})
                elif sl:
                    sched.remove(sl)
            self.save()
            dlg.destroy()
            self.build()

        def remove_all():
            for sl in list(mine.values()):
                sched.remove(sl)
            self.save()
            dlg.destroy()
            self.build()

        dlg.buttons("Save", save)
        if mine:
            Btn(dlg.bar, "Day off", remove_all, "danger").pack(side="left")
        dlg.show()

    def day_picker(self, day):
        s = self.s
        sched = s.schedule_day(self.mon, day)
        d = date_of(self.mon, day)
        shifts = shifts_for_day(day, s.settings)
        dlg = Dialog(self.app, f"Pick staff — {day} {d.month}/{d.day}", width=720,
                     height=int(self.app.winfo_height() * 0.9))
        head = tk.Frame(dlg.body, bg=BG_PAGE)
        head.pack(fill="x")
        tk.Label(head, text=f"Tick who works each shift on {day}. Default times come from Settings.",
                 bg=BG_PAGE, fg=FG_SEC, font=(FONT, 10)).pack(anchor="w", pady=(0, 6))
        srow = tk.Frame(head, bg=BG_PAGE)
        srow.pack(fill="x", pady=(0, 8))
        tk.Label(srow, text="\U0001F50E", bg=BG_PAGE, fg=FG_SEC).pack(side="left")
        search = Inp(srow, width=28, font=(FONT, 12))
        search.pack(side="left", ipady=4, padx=(4, 10))
        Tooltip(search, "Type a name or position. Enter jumps to the first match, Esc clears.")
        only = tk.BooleanVar(value=False)
        tk.Checkbutton(srow, text="Only who's ticked", variable=only, bg=BG_PAGE, font=(FONT, 10),
                       command=lambda: refilter()).pack(side="left")
        count_lbl = tk.Label(srow, text="", bg=BG_PAGE, fg=ACCENT, font=(FONT, 11, "bold"))
        count_lbl.pack(side="right", padx=(10, 0))
        sf = ScrollFrame(dlg.body, bg=BG_CARD)
        sf.pack(fill="both", expand=True)
        g = tk.Frame(sf, bg=BG_CARD, padx=8, pady=6)
        g.pack(fill="x")
        dlg.label(g, "Employee").grid(row=0, column=0, sticky="w")
        for c, sh in enumerate(shifts):
            f = tk.Frame(g, bg=BG_CARD)
            f.grid(row=0, column=1 + c, padx=8)
            shift_pill(f, sh).pack()
        dlg.label(g, "Position").grid(row=0, column=1 + len(shifts), sticky="w", padx=8)
        existing = {(sl["emp_id"], sl["shift"]): sl for sl in sched}
        rows = {}
        row_widgets = []          # (emp, dept, [widgets]) for filtering
        dept_heads = {}
        r = 1
        cur = None
        for e in s.active_employees():
            dept = s.emp_dept(e)
            if dept != cur:
                cur = dept
                lab = tk.Label(g, text="Front of House" if dept == "FOH" else "Back of House",
                               bg=BG_CARD, fg=FOH_BG if dept == "FOH" else BOH_BG, font=(FONT, 10, "bold"))
                lab.grid(row=r, column=0, sticky="w", pady=(8, 2))
                dept_heads[dept] = lab
                r += 1
            nl = tk.Label(g, text=e["name"], bg=BG_CARD, fg=FG, font=(FONT, 11), anchor="w")
            nl.grid(row=r, column=0, sticky="w", pady=1)
            ws = [nl]
            vs = {}
            pos_now = None
            for c, sh in enumerate(shifts):
                sl = existing.get((e["id"], sh))
                if sl and not pos_now:
                    pos_now = sl.get("position")
                v = tk.BooleanVar(value=sl is not None)
                v.trace_add("write", lambda *a: update_count())
                cb = tk.Checkbutton(g, variable=v, bg=BG_CARD)
                cb.grid(row=r, column=1 + c)
                ws.append(cb)
                vs[sh] = v
            pc = ttk.Combobox(g, values=pos_values(s, e), state="readonly", width=16)
            pc.set(pos_now or s.emp_main_position(e))
            pc.grid(row=r, column=1 + len(shifts), padx=8, sticky="w")
            ws.append(pc)
            rows[e["id"]] = (vs, pc)
            row_widgets.append((e, dept, ws))
            r += 1
        nomatch = tk.Label(g, text="Nobody matches.", bg=BG_CARD, fg=FG_SEC, font=(FONT, 11))

        def update_count():
            n = {sh: sum(1 for vs, _ in rows.values() if vs[sh].get()) for sh in shifts}
            count_lbl.config(text="  ·  ".join(f"{sh}: {k}" for sh, k in n.items()))

        def refilter(_=None):
            q = search.get().strip().lower()
            shown = {"FOH": 0, "BOH": 0}
            visible = []
            for e, dept, ws in row_widgets:
                text = (e["name"] + " " + " ".join(e.get("positions", []))).lower()
                ok = all(part in text for part in q.split()) if q else True
                if only.get():
                    ok = ok and any(v.get() for v in rows[e["id"]][0].values())
                for w in ws:
                    w.grid() if ok else w.grid_remove()
                if ok:
                    shown[dept] = shown.get(dept, 0) + 1
                    visible.append(ws)
            for dept, lab in dept_heads.items():
                lab.grid() if shown.get(dept) else lab.grid_remove()
            if visible:
                nomatch.grid_remove()
            else:
                nomatch.grid(row=r, column=0, columnspan=4, sticky="w", pady=10)
            sf.canvas.yview_moveto(0)
            dlg._visible = visible

        def search_enter(_=None):
            vis = getattr(dlg, "_visible", [])
            if vis:
                vis[0][1].focus_set()          # first shift box of the first match (Space ticks it)
            return "break"

        def search_esc(_=None):
            if search.get():
                search.set("")
                refilter()
                return "break"
        search.bind("<KeyRelease>", lambda e: refilter() if e.keysym not in ("Return", "KP_Enter", "Escape") else None)
        search.bind("<Return>", search_enter)
        search.bind("<KP_Enter>", search_enter)
        search.bind("<Escape>", search_esc)
        update_count()
        refilter()

        def set_all(sh, val):
            for vs, _ in rows.values():
                vs[sh].set(val)

        def save():
            apply()
            self.save()
            dlg.destroy()
            self.build()

        def apply():
            for eid, (vs, pc) in rows.items():
                if pc.get() == SEP:
                    pc.set(s.emp_main_position(s.emp(eid)))
                if any(v.get() for v in vs.values()):
                    ensure_position(s, s.emp(eid), pc.get())
                for sh, v in vs.items():
                    sl = existing.get((eid, sh))
                    if v.get():
                        if not sl:
                            dflt = s.settings["default_times"].get(sh, ["", ""])
                            sched.append({"id": gen_id(), "emp_id": eid, "shift": sh,
                                          "position": pc.get(), "start": dflt[0], "end": dflt[1], "note": ""})
                        else:
                            sl["position"] = pc.get()
                    elif sl:
                        sched.remove(sl)

        dlg.buttons("Save", save)
        for sh in shifts:
            Btn(dlg.bar, f"Clear {sh}", lambda sh=sh: set_all(sh, False), "ghost", small=True).pack(side="left", padx=2)

        def new_emp():
            def done(emp):
                apply()                    # keep what's ticked so far
                self.save()
                dlg.destroy()
                self.build()
                self.day_picker(day)
            quick_add_employee(self.app, dlg, on_done=done)
        Btn(dlg.bar, "+ New employee", new_emp, "outline", small=True,
            tip="Add someone who isn't in the list yet").pack(side="left", padx=(12, 2))
        dlg.show(focus=search)

    # ── week actions ────────────────────────────────────────────────────────
    def copy_last_week(self):
        prev = self.s.week(self.mon - timedelta(days=7))["schedule"]
        if not any(prev.values()):
            self.app.notice.warn("Last week has no schedule to copy")
            return
        if any(self.week["schedule"].values()) and not messagebox.askyesno(
                "Replace schedule", "Replace this week's schedule with last week's?", parent=self.app):
            return
        active = {e["id"] for e in self.s.employees if e.get("active", True)}
        new = {}
        for day, slots in prev.items():
            new[day] = [dict(copy.deepcopy(sl), id=gen_id()) for sl in slots if sl["emp_id"] in active]
        self.week["schedule"] = new
        self.save()
        self.app.notice.show("Copied last week's schedule")
        self.build()

    def clear_week(self):
        if messagebox.askyesno("Clear week", "Remove every shift from this week's schedule?", parent=self.app):
            self.week["schedule"] = {}
            self.save()
            self.build()

    def export_pdf(self):
        p = filedialog.asksaveasfilename(parent=self.app, defaultextension=".pdf",
                                         initialfile=f"schedule_{self.mon.isoformat()}.pdf",
                                         filetypes=[("PDF", "*.pdf")])
        if p:
            try:
                exports.schedule_pdf(p, self.s, self.mon)
                self.app.notice.show("Schedule PDF saved")
            except Exception as ex:
                messagebox.showerror("Export failed", str(ex), parent=self.app)

    def export_csv(self):
        p = filedialog.asksaveasfilename(parent=self.app, defaultextension=".csv",
                                         initialfile=f"schedule_{self.mon.isoformat()}.csv",
                                         filetypes=[("CSV", "*.csv")])
        if p:
            exports.schedule_csv(p, self.s, self.mon)
            self.app.notice.show("Schedule CSV saved")

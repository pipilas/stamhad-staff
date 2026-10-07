"""Week — hours worked and total tips per person. Click someone for the details."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, filedialog

from core import DAYS, week_summary, split_day_tips, to_float, date_of
from ui import *  # noqa: F401,F403
import exports


class WeekPage:
    def __init__(self, app, parent):
        self.app = app
        self.s = app.store
        self.mon = app.mon
        self.week = self.s.week(self.mon)
        self.parent = parent
        self.view = getattr(app, "_week_view", "Totals")
        self.drawer_emp = None
        self.build()

    def rows(self):
        return week_summary(self.week, self.s.employees, self.s.pos_map(), self.s.settings)

    def build(self):
        for w in self.parent.winfo_children():
            w.destroy()
        rows = self.rows()
        th = sum(r["total_hours"] for r in rows)
        tt = sum(r["total_tips"] for r in rows)
        h = PageHeader(self.parent, "Week", f"{th:.1f} hours  ·  {money(tt)} tips  ·  {len(rows)} people"
                       if rows else "No hours this week yet")
        MenuBtn(h.actions, "Export", [(f"PDF   {MOD_SYM}E", self.export_pdf), ("CSV", self.export_csv)],
                "ghost").pack(side="right", padx=(10, 0))
        self.app.date_nav(h.actions).pack(side="right")

        bar = tk.Frame(self.parent, bg=BG_PAGE, padx=28)
        bar.pack(fill="x", pady=(0, 10))
        Segmented(bar, ["Totals", "By day"], self.view, self.set_view, size=10).pack(side="left")
        warn = self._pool_warnings()
        if warn:
            l = tk.Label(bar, text=f"  ⚠ {len(warn)} thing{'s' if len(warn) > 1 else ''} to check  ",
                         bg=WARN_BG, fg=WARN_FG, font=(FONT, 10, "bold"), pady=4, cursor="hand2")
            l.pack(side="left", padx=16)
            Tooltip(l, "\n".join(t for t, _ in warn))
            l.bind("<Button-1>", lambda e: warn[0][1]())

        body = tk.Frame(self.parent, bg=BG_PAGE)
        body.pack(fill="both", expand=True)
        self.drawer = Drawer(body, width=380)
        self.sf = ScrollFrame(body)
        self.sf.pack(side="left", fill="both", expand=True, padx=(28, 12), pady=(0, 14))
        if not rows:
            empty_state(self.sf, "\U0001F4CA", "No hours this week yet", "Go to Hours & Tips",
                        lambda: self.app.open_day(self.mon),
                        sub="Download each day's hours from Toast on Hours & Tips and they add up here.")
            return
        (self.build_totals if self.view == "Totals" else self.build_days)(rows)
        if self.drawer_emp:
            r = next((x for x in rows if x["emp_id"] == self.drawer_emp), None)
            if r:
                self.open_person(r)

    def set_view(self, v):
        self.app._week_view = v
        self.view = v
        self.build()

    def build_totals(self, rows):
        cur = None
        card = None
        for r in rows:
            if r["department"] != cur:
                cur = r["department"]
                hd = tk.Frame(self.sf, bg=BG_PAGE)
                hd.pack(fill="x", pady=(10, 4))
                tk.Label(hd, text="Front of House" if cur == "FOH" else "Back of House", bg=BG_PAGE,
                         fg=FOH_BG if cur == "FOH" else BOH_BG, font=(FONT, 10, "bold")).pack(side="left")
                tk.Label(hd, text="TIPS", bg=BG_PAGE, fg=FG_SEC, font=(FONT, 9, "bold"), width=14,
                         anchor="e").pack(side="right", padx=(0, 16))
                tk.Label(hd, text="HOURS", bg=BG_PAGE, fg=FG_SEC, font=(FONT, 9, "bold"), width=10,
                         anchor="e").pack(side="right")
                card = Card(self.sf, padx=0, pady=0)
                card.pack(fill="x")
            row = tk.Frame(card, bg=BG_CARD, cursor="hand2")
            row.pack(fill="x")
            tk.Frame(card, bg="#F1F3F6", height=1).pack(fill="x")
            n = tk.Label(row, text=r["name"], bg=BG_CARD, fg=FG, font=(FONT, 12, "bold"), anchor="w", padx=16, pady=10,
                         cursor="hand2")
            n.pack(side="left")
            days = len([d for d in DAYS if r["hours"][d]])
            dl = tk.Label(row, text=f"{days} day{'s' if days != 1 else ''}", bg=BG_CARD, fg=FG_SEC, font=(FONT, 10),
                          cursor="hand2")
            dl.pack(side="left")
            adj = r["adj_hours"] or r["adj_tips"]
            tl = tk.Label(row, text=money(r["total_tips"]) + (" *" if adj else "  "), bg=BG_CARD,
                          fg=SUCCESS_FG if r["total_tips"] else FG_SEC, font=(FONT, 12, "bold"), width=14, anchor="e",
                          cursor="hand2")
            tl.pack(side="right", padx=(0, 16))
            hl = tk.Label(row, text=f"{r['total_hours']:.2f}", bg=BG_CARD, fg=FG, font=(FONT, 12), width=10,
                          anchor="e", cursor="hand2")
            hl.pack(side="right")
            parts = [row, n, dl, tl, hl]
            for w in parts:
                w.bind("<Button-1>", lambda e, r=r: self.open_person(r))
            hover(parts, BG_CARD, "#F5F7FF")
            if adj:
                Tooltip(tl, "Includes an adjustment — click to see")
        tk.Label(self.sf, text="Click someone to see each day and add an adjustment.", bg=BG_PAGE, fg=FG_SEC,
                 font=(FONT, 9)).pack(anchor="w", pady=(8, 0))

    def build_days(self, rows):
        g = tk.Frame(self.sf, bg=BORDER)
        g.pack(fill="x")
        g.columnconfigure(0, minsize=170)
        for c in range(1, 8):
            g.columnconfigure(c, weight=1, uniform="d", minsize=70)
        heads = [""] + [f"{d[:3]} {date_of(self.mon, d).day}" for d in DAYS] + ["Hours", "Tips"]
        for c, t in enumerate(heads):
            l = tk.Label(g, text=t, bg="#F9FAFB", fg=FG_SEC, font=(FONT, 9, "bold"), pady=7, padx=8,
                         cursor="hand2" if 1 <= c <= 7 else "")
            l.grid(row=0, column=c, sticky="nsew", padx=(0, 1), pady=(0, 1))
            if 1 <= c <= 7:
                l.bind("<Button-1>", lambda e, d=DAYS[c - 1]: self.app.open_day(date_of(self.mon, d)))
                hover([l], "#F9FAFB", "#E0E7FF")
                Tooltip(l, "Open this day")
        for i, r in enumerate(rows, start=1):
            bg = "#FFFFFF"
            n = tk.Label(g, text=r["name"], bg=bg, fg=FG, font=(FONT, 11), anchor="w", padx=10, cursor="hand2")
            n.grid(row=i, column=0, sticky="nsew", padx=(0, 1), pady=(0, 1))
            n.bind("<Button-1>", lambda e, r=r: self.open_person(r))
            for c, d in enumerate(DAYS, start=1):
                h, t = r["hours"][d], r["tips"][d]
                txt = f"{h:.1f}h\n{money(t)}" if t else (f"{h:.1f}h" if h else "")
                l = tk.Label(g, text=txt, bg=bg, fg=FG if h else FG_SEC, font=(FONT, 9), cursor="hand2", pady=3)
                l.grid(row=i, column=c, sticky="nsew", padx=(0, 1), pady=(0, 1))
                l.bind("<Button-1>", lambda e, d=d: self.app.open_day(date_of(self.mon, d)))
                hover([l], bg, "#EEF2FF")
            tk.Label(g, text=f"{r['total_hours']:.2f}", bg=bg, fg=FG, font=(FONT, 11, "bold"), padx=8).grid(
                row=i, column=8, sticky="nsew", padx=(0, 1), pady=(0, 1))
            tk.Label(g, text=money(r["total_tips"]), bg=bg, fg=SUCCESS_FG, font=(FONT, 11, "bold"), padx=8).grid(
                row=i, column=9, sticky="nsew", pady=(0, 1))

    # ── person panel ────────────────────────────────────────────────────────
    def open_person(self, r):
        self.drawer_emp = r["emp_id"]
        self.drawer.open(r["name"], lambda b: self._person_body(b, r),
                         sub=f"{r['total_hours']:.2f} hours  ·  {money(r['total_tips'])} tips",
                         on_close=lambda: setattr(self, "drawer_emp", None))

    def _person_body(self, b, r):
        for d in DAYS:
            h, t = r["hours"][d], r["tips"][d]
            row = tk.Frame(b, bg=BG_CARD, cursor="hand2")
            row.pack(fill="x", pady=1)
            dd = date_of(self.mon, d)
            a = tk.Label(row, text=f"{d[:3]} {dd.month}/{dd.day}", bg=BG_CARD, fg=FG if h else FG_SEC,
                         font=(FONT, 11, "bold" if h else "normal"), width=9, anchor="w", cursor="hand2")
            a.pack(side="left", pady=4)
            x = tk.Label(row, text=f"{h:.2f} h" if h else "—", bg=BG_CARD, fg=FG if h else "#D1D5DB",
                         font=(FONT, 11), width=8, anchor="e", cursor="hand2")
            x.pack(side="left")
            y = tk.Label(row, text=money(t) if t else "", bg=BG_CARD, fg=SUCCESS_FG, font=(FONT, 11, "bold"),
                         anchor="e", cursor="hand2")
            y.pack(side="right")
            for w in (row, a, x, y):
                w.bind("<Button-1>", lambda e, dd=dd: self.app.open_day(dd))
            hover([row, a, x, y], BG_CARD, "#F5F7FF")
        tk.Frame(b, bg=BORDER, height=1).pack(fill="x", pady=12)
        tk.Label(b, text="Adjustment for this week", bg=BG_CARD, fg=FG, font=(FONT, 11, "bold")).pack(anchor="w")
        tk.Label(b, text="Added to the totals. Use a minus sign to take away.", bg=BG_CARD, fg=FG_SEC,
                 font=(FONT, 9)).pack(anchor="w", pady=(0, 6))
        f = tk.Frame(b, bg=BG_CARD)
        f.pack(fill="x")
        tk.Label(f, text="Hours", bg=BG_CARD, fg=FG_HDR, font=(FONT, 10, "bold"), width=7, anchor="w").grid(row=0, column=0)
        ah = Inp(f, width=8, justify="right")
        ah.set(f"{r['adj_hours']:g}" if r["adj_hours"] else "")
        ah.grid(row=0, column=1, ipady=3, pady=3, sticky="w")
        tk.Label(f, text="Tips $", bg=BG_CARD, fg=FG_HDR, font=(FONT, 10, "bold"), width=7, anchor="w").grid(row=1, column=0)
        at = Inp(f, width=8, justify="right")
        at.set(f"{r['adj_tips']:.2f}" if r["adj_tips"] else "")
        at.grid(row=1, column=1, ipady=3, pady=3, sticky="w")
        tk.Label(f, text="Note", bg=BG_CARD, fg=FG_HDR, font=(FONT, 10, "bold"), width=7, anchor="w").grid(row=2, column=0)
        nt = Inp(f, width=26)
        nt.set(r.get("note", ""))
        nt.grid(row=2, column=1, ipady=3, pady=3, sticky="w")

        def commit(_=None):
            self.commit_adj(r["emp_id"], ah, at, nt)
            return "break"
        for w in (ah, at, nt):
            w.bind("<FocusOut>", commit)
            w.bind("<Return>", lambda e, w=w: (commit(), w.tk_focusNext().focus_set(), "break")[2])

    def commit_adj(self, eid, ah, at, nt):
        h = to_float(ah.get())
        t = to_float(at.get())
        if (ah.get().strip() and h is None) or (at.get().strip() and t is None):
            self.app.notice.warn("Adjustments must be numbers (use - to subtract)")
            return
        adj = self.week["adjustments"]
        new = {"hours": h or 0.0, "tips": round(t or 0.0, 2), "note": nt.get().strip()}
        changed = False
        if not new["hours"] and not new["tips"] and not new["note"]:
            if eid in adj:
                del adj[eid]
                changed = True
        elif adj.get(eid) != new:
            adj[eid] = new
            changed = True
        if changed:
            self.s.save_week(self.mon)
            self.app.notice.show("Adjustment saved")
            self.app.after(10, self.build)

    def _pool_warnings(self):
        out = []
        pm, st = self.s.pos_map(), self.s.settings
        for d in DAYS:
            dd = self.week["days"].get(d)
            if not dd:
                continue
            dt = date_of(self.mon, d)
            for sh, r in split_day_tips(dd, pm, st).items():
                left = r["floor_unassigned"] + r["bar_unassigned"]
                if left:
                    out.append((f"{d} {sh}: {money(left)} of tips not given to anyone",
                                lambda dt=dt, sh=sh: self._open(dt, "Tips", sh)))
                if r["overflow"]:
                    out.append((f"{d} {sh}: fixed tips exceed the pool by {money(r['overflow'])}",
                                lambda dt=dt, sh=sh: self._open(dt, "Tips", sh)))
            miss = [e for e in dd.get("entries", []) if not e.get("emp_id")]
            if miss:
                out.append((f"{d}: {len(miss)} without an employee", lambda dt=dt: self._open(dt, "Hours", None)))
        return out

    def _open(self, d, step, shift):
        self.app._day_step = step
        if shift:
            self.app._day_shift = shift
        self.app.open_day(d)

    def export_csv(self):
        p = filedialog.asksaveasfilename(parent=self.app, defaultextension=".csv",
                                         initialfile=f"hours_tips_{self.mon.isoformat()}.csv",
                                         filetypes=[("CSV", "*.csv")])
        if p:
            exports.summary_csv(p, self.rows())
            self.app.notice.show("CSV saved")

    def export_pdf(self):
        p = filedialog.asksaveasfilename(parent=self.app, defaultextension=".pdf",
                                         initialfile=f"hours_tips_{self.mon.isoformat()}.pdf",
                                         filetypes=[("PDF", "*.pdf")])
        if p:
            try:
                exports.summary_pdf(p, self.rows(), self.mon)
                self.app.notice.show("PDF saved")
            except Exception as ex:
                messagebox.showerror("Export failed", str(ex), parent=self.app)

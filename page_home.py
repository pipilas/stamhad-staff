"""Home — today at a glance, one click to each job."""

from __future__ import annotations

import tkinter as tk
from datetime import date, datetime, timedelta

from core import DAYS, monday_of, day_name, shifts_for_day, split_day_tips, eff_hours, to_float, week_summary
import inventory as invm
from ui import *  # noqa: F401,F403


class HomePage:
    def __init__(self, app, parent):
        self.app, self.s, self.parent = app, app.store, parent
        self.build()

    def build(self):
        s = self.s
        today = date.today()
        mon = monday_of(today)
        day = day_name(today)
        hr = datetime.now().hour
        hello = "Good morning" if hr < 12 else ("Good afternoon" if hr < 17 else "Good evening")
        PageHeader(self.parent, hello, today.strftime("%A, %B %d"))

        self.sf = ScrollFrame(self.parent)
        self.sf.pack(fill="both", expand=True, padx=28, pady=(0, 16))
        grid = tk.Frame(self.sf, bg=BG_PAGE)
        grid.pack(fill="x")
        for c in range(3):
            grid.columnconfigure(c, weight=1, uniform="c")

        # 1 — schedule today
        sched = s.schedule_day(mon, day)
        per = {sh: len([x for x in sched if x["shift"] == sh]) for sh in shifts_for_day(day, s.settings)}
        c1 = stat_card(grid, "Working today", f"{len(sched)} people" if sched else "Nobody yet",
                       "  ·  ".join(f"{k} {v}" for k, v in per.items()) if sched else "Nothing scheduled for today",
                       on_click=lambda: self.open("Schedule", today),
                       action=("Pick staff for today", self.pick_today))

        # 2 — hours today
        dd = s.week(mon)["days"].get(day, {})
        entries = dd.get("entries", [])
        people = len({e.get("emp_id") for e in entries if e.get("emp_id")})
        hrs = sum(eff_hours(e) for e in entries)
        c2 = stat_card(grid, "Hours today", f"{hrs:.1f} h" if entries else "Not in yet",
                       f"{people} people clocked" if entries else "Download them from Toast after closing",
                       on_click=lambda: self.open("Hours & Tips", today),
                       action=("Download from Toast", self.download_today))

        # 3 — tips today
        tips = dd.get("tips", {})
        pools = {sh: (to_float(v.get("floor"), 0) or 0) + (to_float(v.get("bar"), 0) or 0) for sh, v in tips.items()}
        tot = sum(pools.values())
        c3 = stat_card(grid, "Tips today", money(tot) if tot else "Not entered",
                       "  ·  ".join(f"{k} {money(v)}" for k, v in pools.items() if v) or "Enter them on Hours & Tips → Tips",
                       color=SUCCESS_FG if tot else FG,
                       on_click=lambda: self.open("Hours & Tips", today, step="Tips"))

        # 4 — this week
        rows = week_summary(s.week(mon), s.employees, s.pos_map(), s.settings)
        wh = sum(r["total_hours"] for r in rows)
        wt = sum(r["total_tips"] for r in rows)
        c4 = stat_card(grid, "This week", f"{wh:.0f} h", f"{money(wt)} tips  ·  {len(rows)} people",
                       on_click=lambda: self.open("Week", today))

        # 5 — order
        inv = invm.load(s)
        due = [it for it in inv["items"] if it.get("active", True)
               and (r := invm.recommend(inv, it)) and r["due"]]
        in_order = len([k for k, v in inv["draft"]["qty"].items() if v])
        if not inv["items"]:
            big, sub = "No items", "Add the things you order"
        else:
            big = f"{len(due)} due" if due else "All stocked"
            sub = (f"✨ suggested from past orders" if due else "Nothing due by past orders") + \
                  (f"  ·  {in_order} in current order" if in_order else "")
        c5 = stat_card(grid, "Supplies", big, sub, color=ACCENT if due else FG,
                       on_click=lambda: self.app.go("Order" if inv["items"] else "Items"))

        # 6 — needs attention
        issues = self.issues(mon, today)
        c6 = stat_card(grid, "Needs attention", f"{len(issues)}" if issues else "All good ✓",
                       "\n".join(t for t, _ in issues[:4]) if issues else "Nothing to fix this week",
                       color=DANGER if issues else SUCCESS_FG,
                       on_click=(issues[0][1] if issues else None))

        for i, c in enumerate((c1, c2, c3, c4, c5, c6)):
            c.grid(row=i // 3, column=i % 3, sticky="nsew", padx=(0 if i % 3 == 0 else 8, 0), pady=(0, 10))

    def issues(self, mon, today):
        out = []
        s = self.s
        w = s.week(mon)
        pm = s.pos_map()
        for d in DAYS:
            dd = w["days"].get(d)
            dt = mon + timedelta(days=DAYS.index(d))
            if not dd:
                continue
            miss = [e for e in dd.get("entries", []) if not e.get("emp_id")]
            if miss:
                out.append((f"{d[:3]}: {len(miss)} without an employee", lambda dt=dt: self.open("Hours & Tips", dt)))
            for sh, r in split_day_tips(dd, pm, s.settings).items():
                left = r["floor_unassigned"] + r["bar_unassigned"]
                if left:
                    out.append((f"{d[:3]} {sh}: {money(left)} tips not given out",
                                lambda dt=dt: self.open("Hours & Tips", dt, step="Tips", shift=sh)))
        # yesterday: scheduled but no hours at all
        y = today - timedelta(days=1)
        ym = monday_of(y)
        yd = day_name(y)
        if s.schedule_day(ym, yd) and not s.week(ym)["days"].get(yd, {}).get("entries"):
            out.append((f"Yesterday's hours aren't in yet", lambda: self.open("Hours & Tips", y)))
        return out

    def open(self, page, d, step=None, shift=None):
        if step:
            self.app._day_step = step
        if shift:
            self.app._day_shift = shift
        self.app.sel_date = d
        self.app.go(page, keep_scroll=False)

    def pick_today(self):
        today = date.today()
        self.open("Schedule", today)
        po = self.app.page_obj
        if po:
            po.day_picker(day_name(today))

    def download_today(self):
        self.open("Hours & Tips", date.today(), step="Hours")
        po = self.app.page_obj
        if po:
            po.download_toast()

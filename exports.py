"""CSV / PDF exports for the schedule and the weekly hours & tips summary."""

from __future__ import annotations

import csv
from datetime import timedelta

from core import DAYS, date_of


def _short(t):
    from page_schedule import short_time
    return short_time(t)


# ── schedule ────────────────────────────────────────────────────────────────
DEPTS = (("FOH", "Front of House"), ("BOH", "Back of House"))
SHIFT_COLORS = {"Morning": ("#FCD34D", "#78350F"), "Brunch": ("#34D399", "#064E3B"),
                "Dinner": ("#818CF8", "#312E81")}
_ORDER = {"Morning": 0, "Brunch": 0, "Dinner": 1}


def _slot_label(store, e, sl):
    a, z = _short(sl.get("start")), _short(sl.get("end"))
    t = f"{sl['shift']} {a}-{z}" if a and z else sl["shift"]
    extra = []
    if sl.get("position") and sl["position"] != store.emp_main_position(e):
        extra.append(sl["position"])
    if sl.get("note"):
        extra.append(sl["note"])
    return t, " · ".join(extra)


def _schedule_matrix(store, mon):
    """[(dept, [(emp, [[slot, ...] per day]), ...]), ...] — FOH first, then BOH. No hours."""
    week = store.week(mon)
    by = {}
    for day, slots in week["schedule"].items():
        for sl in slots:
            by.setdefault(sl["emp_id"], {}).setdefault(day, []).append(sl)
    groups = {k: [] for k, _ in DEPTS}
    for e in store.all_employees_sorted():
        if e["id"] not in by:
            continue
        cells = [sorted(by[e["id"]].get(d, []), key=lambda x: _ORDER.get(x["shift"], 2)) for d in DAYS]
        groups.setdefault(store.emp_dept(e), []).append((e, cells))
    return [(k, groups[k]) for k in groups if groups[k]]


def schedule_csv(path, store, mon):
    names = dict(DEPTS)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        first = True
        for dept, rows in _schedule_matrix(store, mon):
            if not first:
                w.writerow([])
            first = False
            w.writerow([names.get(dept, dept).upper()])
            w.writerow(["Employee"] + [f"{d} {date_of(mon, d):%m/%d}" for d in DAYS])
            for e, cells in rows:
                out = []
                for c in cells:
                    parts = []
                    for sl in c:
                        t, x = _slot_label(store, e, sl)
                        parts.append(f"{t} ({x})" if x else t)
                    out.append(" / ".join(parts))
                w.writerow([e["name"]] + out)


def _rl():
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import letter, landscape
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    except ImportError:
        raise RuntimeError("PDF export needs 'reportlab'.\nInstall it with:  pip3 install reportlab\n\n"
                           "CSV export works without it.")
    return colors, letter, landscape, ParagraphStyle, SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer


def _shift_cell_class():
    from reportlab.platypus import Flowable
    from reportlab.lib import colors

    class ShiftCell(Flowable):
        """Fills the whole table cell with the shift colour; two shifts split diagonally."""
        def __init__(self, items, h=24):
            super().__init__()
            self.items = items          # [(shift, label, extra), ...]
            self.H = h

        def wrap(self, aw, ah):
            self.w = aw
            return aw, self.H

        def _text(self, c, x, y, s, size, color, anchor):
            c.setFillColor(colors.HexColor(color))
            c.setFont("Helvetica-Bold" if size > 6.5 else "Helvetica", size)
            {"l": c.drawString, "r": c.drawRightString, "c": c.drawCentredString}[anchor](x, y, s)

        def draw(self):
            c, w, h = self.canv, self.w, self.H
            it = self.items
            if not it:
                return
            if len(it) == 1:
                sh, lab, ex = it[0]
                bg, fg = SHIFT_COLORS.get(sh, ("#E5E7EB", "#111827"))
                c.setFillColor(colors.HexColor(bg))
                c.rect(0, 0, w, h, stroke=0, fill=1)
                self._text(c, w / 2, h / 2 + (1 if ex else -3), lab, 8, fg, "c")
                if ex:
                    self._text(c, w / 2, h / 2 - 9, ex[:34], 6.0, fg, "c")
                return
            (s1, l1, x1), (s2, l2, x2) = it[0], it[1]
            b1, f1 = SHIFT_COLORS.get(s1, ("#E5E7EB", "#111827"))
            b2, f2 = SHIFT_COLORS.get(s2, ("#E5E7EB", "#111827"))
            p = c.beginPath(); p.moveTo(0, h); p.lineTo(w, h); p.lineTo(0, 0); p.close()
            c.setFillColor(colors.HexColor(b1)); c.drawPath(p, stroke=0, fill=1)
            p = c.beginPath(); p.moveTo(w, h); p.lineTo(w, 0); p.lineTo(0, 0); p.close()
            c.setFillColor(colors.HexColor(b2)); c.drawPath(p, stroke=0, fill=1)
            c.setStrokeColor(colors.white); c.setLineWidth(0.8); c.line(w, h, 0, 0)
            self._text(c, 3, h - 9, l1, 6.8, f1, "l")
            if x1:
                self._text(c, 3, h - 16, x1[:16], 5.8, f1, "l")
            self._text(c, w - 3, 3, l2, 6.8, f2, "r")
            if x2:
                self._text(c, w - 3, 10, x2[:16], 5.8, f2, "r")
    return ShiftCell


def schedule_pdf(path, store, mon):
    colors, letter, landscape, PS, Doc, Table, TS, P, Spacer = _rl()
    from reportlab.platypus import PageBreak
    ShiftCell = _shift_cell_class()
    name = PS("n", fontName="Helvetica-Bold", fontSize=9, leading=11)
    title = PS("t", fontName="Helvetica-Bold", fontSize=15, leading=18)
    sub = PS("s", fontName="Helvetica", fontSize=9, leading=11, textColor=colors.HexColor("#6B7280"))
    sun = mon + timedelta(days=6)
    doc = Doc(path, pagesize=landscape(letter), leftMargin=24, rightMargin=24, topMargin=24, bottomMargin=24)
    names = dict(DEPTS)
    story = []
    for n, (dept, rows) in enumerate(_schedule_matrix(store, mon)):
        if n:
            story.append(PageBreak())
        accent = "#3B82F6" if dept == "FOH" else "#F97316"
        story += [P(f"{names.get(dept, dept)} — Schedule", title),
                  P(f"{mon:%b %d} to {sun:%b %d, %Y}", sub), Spacer(1, 8)]
        data = [["Employee"] + [f"{d[:3]} {date_of(mon, d):%m/%d}" for d in DAYS]]
        style = [("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(accent)),
                 ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                 ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("FONTSIZE", (0, 0), (-1, 0), 9),
                 ("ALIGN", (1, 0), (-1, 0), "CENTER"),
                 ("GRID", (0, 0), (-1, -1), 0.6, colors.white),
                 ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#D1D5DB")),
                 ("VALIGN", (0, 1), (-1, -1), "MIDDLE"),
                 ("LEFTPADDING", (1, 1), (-1, -1), 0), ("RIGHTPADDING", (1, 1), (-1, -1), 0),
                 ("TOPPADDING", (1, 1), (-1, -1), 0), ("BOTTOMPADDING", (1, 1), (-1, -1), 0)]
        for e, cells in rows:
            items = [[(sl["shift"], *_slot_label(store, e, sl)) for sl in c] for c in cells]
            tall = any(x[2] for it in items for x in it)
            data.append([P(e["name"], name)] + [ShiftCell(it, 34 if tall else 24) for it in items])
            r = len(data) - 1
            bgc = "#F5F7FA" if r % 2 == 0 else "#FFFFFF"
            style.append(("BACKGROUND", (0, r), (-1, r), colors.HexColor(bgc)))
        t = Table(data, colWidths=[128] + [87] * 7, repeatRows=1)
        t.setStyle(TS(style))
        story.append(t)
    if not story:
        story = [P(f"Schedule — {mon:%b %d} to {sun:%b %d, %Y}", title), Spacer(1, 8), P("Nothing scheduled.", sub)]
    doc.build(story)


# ── hours & tips ────────────────────────────────────────────────────────────
def summary_csv(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Employee", "Dept"] + [f"{d} hrs" for d in DAYS] + [f"{d} tips" for d in DAYS] +
                   ["Adj hrs", "Adj tips", "Total hours", "Total tips", "Note"])
        for r in rows:
            w.writerow([r["name"], r["department"]] + [f"{r['hours'][d]:.2f}" for d in DAYS] +
                       [f"{r['tips'][d]:.2f}" for d in DAYS] +
                       [f"{r['adj_hours']:.2f}", f"{r['adj_tips']:.2f}",
                        f"{r['total_hours']:.2f}", f"{r['total_tips']:.2f}", r.get("note", "")])
        w.writerow(["TOTAL", ""] + [f"{sum(r['hours'][d] for r in rows):.2f}" for d in DAYS] +
                   [f"{sum(r['tips'][d] for r in rows):.2f}" for d in DAYS] +
                   ["", "", f"{sum(r['total_hours'] for r in rows):.2f}",
                    f"{sum(r['total_tips'] for r in rows):.2f}", ""])


def summary_pdf(path, rows, mon):
    colors, letter, landscape, PS, Doc, Table, TS, P, Spacer = _rl()
    title = PS("t", fontName="Helvetica-Bold", fontSize=15, leading=18)
    sun = mon + timedelta(days=6)
    doc = Doc(path, pagesize=landscape(letter), leftMargin=24, rightMargin=24, topMargin=24, bottomMargin=24)
    data = [["Employee"] + [f"{d[:3]} {date_of(mon, d):%m/%d}" for d in DAYS] + ["Total hrs", "Total tips"]]
    style = [("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1B2A4A")),
             ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
             ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
             ("FONTSIZE", (0, 0), (-1, -1), 8.5),
             ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#D1D5DB")),
             ("ALIGN", (1, 0), (-1, -1), "CENTER"), ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]
    cur = None
    for r in rows:
        if r["department"] != cur:
            cur = r["department"]
            data.append(["Front of House" if cur == "FOH" else "Back of House"] + [""] * 9)
            i = len(data) - 1
            style += [("SPAN", (0, i), (-1, i)), ("ALIGN", (0, i), (-1, i), "LEFT"),
                      ("BACKGROUND", (0, i), (-1, i), colors.HexColor("#3B82F6" if cur == "FOH" else "#F97316")),
                      ("TEXTCOLOR", (0, i), (-1, i), colors.white), ("FONTNAME", (0, i), (-1, i), "Helvetica-Bold")]
        cells = []
        for d in DAYS:
            h, t = r["hours"][d], r["tips"][d]
            cells.append(f"{h:.2f}h\n${t:,.2f}" if (h or t) else "")
        tot_t = f"${r['total_tips']:,.2f}"
        if r["adj_hours"] or r["adj_tips"]:
            tot_t += "*"
        data.append([r["name"]] + cells + [f"{r['total_hours']:.2f}", tot_t])
        i = len(data) - 1
        style.append(("FONTNAME", (-2, i), (-1, i), "Helvetica-Bold"))
        if i % 2 == 0:
            style.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor("#F5F7FA")))
    data.append(["TOTAL"] + [f"{sum(r['hours'][d] for r in rows):.2f}h\n${sum(r['tips'][d] for r in rows):,.2f}"
                             for d in DAYS] +
                [f"{sum(r['total_hours'] for r in rows):.2f}", f"${sum(r['total_tips'] for r in rows):,.2f}"])
    i = len(data) - 1
    style += [("BACKGROUND", (0, i), (-1, i), colors.HexColor("#E0E7FF")), ("FONTNAME", (0, i), (-1, i), "Helvetica-Bold")]
    t = Table(data, colWidths=[130] + [66] * 7 + [62, 76], repeatRows=1)
    t.setStyle(TS(style))
    story = [P(f"Hours &amp; Tips — {mon:%b %d} to {sun:%b %d, %Y}", title), Spacer(1, 8), t]
    if any(r["adj_hours"] or r["adj_tips"] for r in rows):
        story += [Spacer(1, 6), P("* includes a manual adjustment", PS("f", fontName="Helvetica", fontSize=8))]
    doc.build(story)

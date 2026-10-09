"""
Stamhad Staff — core logic (no UI).

Time handling, shift detection, hours, and the tip split.

TIP RULE (per day, per shift):
  * Floor pool  -> every FOH entry with points > 0.
        weight = tip_hours x points
        tip_hours = hours from clock-in until clock-out, but for shifts that
        have a "full share" time (Dinner = 11:00 PM by default) the clock stops
        at that time: leaving at 11:40 PM counts the same as leaving at 11:00 PM.
        So anyone who stays past 11 gets the maximum for their arrival time.
  * Bar pool    -> barbacks take their fixed % first, the rest goes to
        bartenders weighted by tip_hours.
  * Overrides   -> an entry with a manual Tip $ is paid exactly that amount; it
        is taken out of the floor pool first (then the bar pool) and the rest is
        split between everyone else, so the pools always balance.
"""

from __future__ import annotations

import re
from datetime import date, timedelta

DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
SHIFTS = ["Morning", "Brunch", "Dinner"]

DEFAULT_SETTINGS = {
    # clock-ins before this time count as the day shift (Morning / Brunch)
    "day_shift_cutoff": "2:00 PM",
    # days where the day shift is called Brunch instead of Morning
    "brunch_days": ["Saturday", "Sunday"],
    # how floor tips are split: "points" = by position points only (everyone on the shift gets
    # their full points), "time" = tip hours x points (who came earlier / stayed longer gets more)
    "tip_method": "points",
    # per-shift "full share" time. None = no cap (split by full hours worked)
    "full_share_time": {"Morning": None, "Brunch": None, "Dinner": "11:00 PM"},
    # per-shift tip-clock start: clocking in before this counts from this time.
    # None = count from the real clock-in.
    "tip_start_time": {"Morning": None, "Brunch": None, "Dinner": "4:05 PM"},
    # default times used by the schedule
    "default_times": {
        "Morning": ["7:00 AM", "3:00 PM"],
        "Brunch": ["9:30 AM", "4:00 PM"],
        "Dinner": ["4:00 PM", "11:00 PM"],
    },
    "toast": {
        "host": "s-9b0f88558b264dfda.server.transfer.us-east-1.amazonaws.com",
        "port": 22,
        "username": "",
        "export_id": "",
        "key_path": "",
    },
}


# ─────────────────────────────────────────────────────────────────────────────
#  Dates
# ─────────────────────────────────────────────────────────────────────────────
def monday_of(d: date) -> date:
    return d - timedelta(days=d.weekday())


def day_name(d: date) -> str:
    return DAYS[d.weekday()]


def date_of(mon: date, day: str) -> date:
    return mon + timedelta(days=DAYS.index(day))


# ─────────────────────────────────────────────────────────────────────────────
#  Times  (stored as text like "4:05 PM"; computed as minutes after midnight)
# ─────────────────────────────────────────────────────────────────────────────
_TIME_RE = re.compile(r"^\s*(\d{1,2})(?::?(\d{2}))?\s*([ap])?\.?\s*m?\.?\s*$", re.I)


def parse_time(s) -> int | None:
    """'4:05 PM', '04:05PM', '16:05', '4p', '1605', '03/22/2026 06:57 AM' -> minutes."""
    if s is None:
        return None
    s = str(s).strip()
    if not s:
        return None
    # strip a leading date part
    if " " in s:
        first, rest = s.split(" ", 1)
        if "/" in first or "-" in first:
            s = rest.strip()
    s = s.replace(".", "")
    m = _TIME_RE.match(s)
    if not m:
        return None
    h = int(m.group(1))
    mi = int(m.group(2) or 0)
    ap = (m.group(3) or "").lower()
    if len(m.group(1)) > 2 or mi > 59:
        return None
    if ap:
        if not 1 <= h <= 12:
            return None
        if ap == "a":
            h = 0 if h == 12 else h
        else:
            h = 12 if h == 12 else h + 12
    elif h > 23:
        return None
    return h * 60 + mi


def fmt_time(mins: int | None) -> str:
    if mins is None:
        return ""
    mins %= 1440
    h, m = divmod(mins, 60)
    ap = "AM" if h < 12 else "PM"
    h12 = h % 12 or 12
    return f"{h12}:{m:02d} {ap}"


def _ambiguous(s) -> int | None:
    """'4', '4:30', '430', '12' (no AM/PM, 1-12, no leading zero) -> the hour; else None."""
    s = str(s or "").strip().replace(".", "")
    m = _TIME_RE.match(s)
    if not m or m.group(3) or m.group(1).startswith("0"):
        return None
    h = int(m.group(1))
    return h if 1 <= h <= 12 else None


def smart_time(s, after=None, near=None, start=False) -> str:
    """Like norm_time, but a time typed without AM/PM gets the sensible half of the day.
    after: the shift's start (minutes or text) -> pick the end that comes soonest after it
           (start 4 PM, end '11' -> 11 PM;  start 5 PM, end '2' -> 2 AM).
    near:  the usual time for this field (e.g. the shift's usual start) -> pick the closer one.
    start: it's a clock-in / shift start -> never guess 12:00-4:59 AM (type '4a' if you mean it).
    Neither: 6-11 -> AM, 12-5 -> PM (nobody starts a shift at 4 AM).
    '4a' / '4 pm' / '16:00' / '04:00' are always taken as typed."""
    m = parse_time(s)
    if m is None:
        return ""
    h = _ambiguous(s)
    if h is None:
        return fmt_time(m)
    mi = m % 60
    am = (0 if h == 12 else h) * 60 + mi
    pm = (12 if h == 12 else h + 12) * 60 + mi
    if isinstance(after, str):
        after = parse_time(after)
    if isinstance(near, str):
        near = parse_time(near)
    if after is not None:
        def gap(c):
            d = (c - after) % 1440
            return d or 1440
        return fmt_time(min((am, pm), key=gap))
    cands = (am, pm)
    if start:
        cands = tuple(c for c in cands if c >= 5 * 60) or cands
        if len(cands) == 1:
            return fmt_time(cands[0])
    if near is not None:
        def dist(c):
            d = abs(c - near) % 1440
            return min(d, 1440 - d)
        return fmt_time(min(cands, key=dist))
    return fmt_time(am if 6 <= h <= 11 else pm)


def norm_time(s) -> str:
    """Normalise user text to '4:05 PM' (or '' if blank/invalid)."""
    return fmt_time(parse_time(s))


def span_minutes(t_in: int, t_out: int) -> int:
    """Minutes from in to out; out earlier than in means it crossed midnight."""
    if t_out < t_in:
        t_out += 1440
    return t_out - t_in


def hours_between(time_in, time_out) -> float | None:
    a, b = parse_time(time_in), parse_time(time_out)
    if a is None or b is None:
        return None
    return round(span_minutes(a, b) / 60, 2)


def tip_hours_between(time_in, time_out, full_share_time, start_time=None) -> float | None:
    """Hours counted for tips: clock starts no earlier than start_time and
    stops at full_share_time (each only if set)."""
    a, b = parse_time(time_in), parse_time(time_out)
    if a is None or b is None:
        return None
    end = a + span_minutes(a, b)
    st = parse_time(start_time) if start_time else None
    if st is not None and st - 8 * 60 <= a < st:   # came in early (same evening) -> count from start
        a = st
        if end < a:
            return 0.0
    cap = parse_time(full_share_time) if full_share_time else None
    if cap is not None:
        # put the cap on the same "timeline" as the clock-in (handles after-midnight)
        if cap < a - 6 * 60:          # e.g. clock-in 11:30 PM, cap 11 PM -> nothing to cap
            cap += 1440
        end = min(end, cap)
    return round(max(0, end - a) / 60, 2)


# ─────────────────────────────────────────────────────────────────────────────
#  Shifts
# ─────────────────────────────────────────────────────────────────────────────
def day_shift_name(day: str, settings: dict) -> str:
    return "Brunch" if day in settings.get("brunch_days", []) else "Morning"


def shifts_for_day(day: str, settings: dict) -> list[str]:
    return [day_shift_name(day, settings), "Dinner"]


def detect_shift(time_in, day: str, settings: dict, time_out=None) -> str:
    """Pick the shift this clock-in belongs to.
    With both times: the shift whose usual hours (Settings > default times) overlap
    the most with the time worked. E.g. 1:46 PM-11:31 PM on a brunch day = Dinner,
    9:30 AM-4:10 PM = Brunch. Without a clock-out: clock-in before the cutoff = day shift."""
    day_sh = day_shift_name(day, settings)
    a, b = parse_time(time_in), parse_time(time_out)
    dt = settings.get("default_times", {})
    if a is not None and b is not None and dt.get(day_sh) and dt.get("Dinner"):
        end = a + span_minutes(a, b)

        def overlap(sh):
            s0, s1 = parse_time(dt[sh][0]), parse_time(dt[sh][1])
            if s0 is None or s1 is None:
                return 0
            s1 = s0 + span_minutes(s0, s1)
            return max(0, min(end, s1) - max(a, s0))
        od, on = overlap(day_sh), overlap("Dinner")
        if od != on:
            return day_sh if od > on else "Dinner"
    t = a
    cutoff = parse_time(settings.get("day_shift_cutoff", "2:00 PM"))
    if t is not None and cutoff is not None and t < cutoff and t >= 4 * 60:
        return day_sh
    return "Dinner"


# ─────────────────────────────────────────────────────────────────────────────
#  Entries — auto values + manual overrides
# ─────────────────────────────────────────────────────────────────────────────
def to_float(v, default=None):
    if v is None:
        return default
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().replace("$", "").replace(",", "")
    if not s:
        return default
    try:
        return float(s)
    except ValueError:
        return default


def _toast_unchanged(e: dict) -> bool:
    return (e.get("toast_hours") is not None and e.get("toast_in") is not None
            and e.get("time_in") == e.get("toast_in") and e.get("time_out") == e.get("toast_out"))


def auto_hours(e: dict) -> float:
    # Toast's own hours are exact to the second -> use them while the times are untouched
    if _toast_unchanged(e) and e.get("toast_hours"):
        return float(e["toast_hours"])
    h = hours_between(e.get("time_in"), e.get("time_out"))
    if h is not None:
        return h
    return to_float(e.get("toast_hours"), 0.0) or 0.0


def eff_hours(e: dict) -> float:
    m = to_float(e.get("hours_manual"))
    return m if m is not None else auto_hours(e)


def auto_tip_hours(e: dict, settings: dict) -> float:
    """Worked hours minus whatever falls before the tip-clock start or after the full-share time."""
    fst = (settings.get("full_share_time") or {}).get(e.get("shift"))
    sst = (settings.get("tip_start_time") or {}).get(e.get("shift"))
    capped = tip_hours_between(e.get("time_in"), e.get("time_out"), fst, sst)
    full = hours_between(e.get("time_in"), e.get("time_out"))
    if capped is None or full is None:
        return eff_hours(e)
    if capped < full and to_float(e.get("hours_manual")) is None:
        # the tip window cut this shift -> tip time is exactly that window
        # (don't carry over Toast's leftover seconds, e.g. 7.74 vs 7.73)
        return capped
    cut = max(0.0, full - capped)          # time before 4:05 / after 11 PM that doesn't count
    return round(max(0.0, eff_hours(e) - cut), 2)


def eff_tip_hours(e: dict, settings: dict) -> float:
    m = to_float(e.get("tip_hours_manual"))
    return m if m is not None else auto_tip_hours(e, settings)


def auto_points(e: dict, positions_by_name: dict) -> float:
    p = positions_by_name.get(e.get("position"), {})
    return to_float(p.get("tip_points"), 0.0) or 0.0


def eff_points(e: dict, positions_by_name: dict) -> float:
    m = to_float(e.get("points_manual"))
    return m if m is not None else auto_points(e, positions_by_name)


# ─────────────────────────────────────────────────────────────────────────────
#  Tip split
# ─────────────────────────────────────────────────────────────────────────────
def _round_split(total: float, weights: dict) -> dict:
    """Split total by weights into cents that add up exactly."""
    out = {k: 0.0 for k in weights}
    tw = sum(weights.values())
    if tw <= 0 or total <= 0:
        return out
    cents = round(total * 100)
    raw = {k: cents * w / tw for k, w in weights.items()}
    floor = {k: int(v) for k, v in raw.items()}
    left = cents - sum(floor.values())
    for k in sorted(raw, key=lambda k: raw[k] - floor[k], reverse=True)[:left]:
        floor[k] += 1
    return {k: v / 100 for k, v in floor.items()}


def by_time(settings: dict) -> bool:
    """True when tips are split by time worked (tip hours x points)."""
    return (settings or {}).get("tip_method", "points") == "time"


def split_shift_tips(entries: list[dict], floor_pool: float, bar_pool: float,
                     positions_by_name: dict, settings: dict) -> dict:
    """
    entries: the day's entries for ONE shift.
    Returns {"rows": {entry_id: {...}}, "floor_unassigned": x, "bar_unassigned": y,
             "value_per_point_hour": v}
    """
    rows = {}
    floor_pool = max(0.0, to_float(floor_pool, 0.0))
    bar_pool = max(0.0, to_float(bar_pool, 0.0))

    # 1) overrides come off the top
    overridden = {e["id"]: to_float(e.get("tip_override")) for e in entries
                  if to_float(e.get("tip_override")) is not None}
    need = sum(overridden.values())
    from_floor = min(need, floor_pool)
    floor_left = round(floor_pool - from_floor, 2)
    bar_left = round(max(0.0, bar_pool - (need - from_floor)), 2)

    free = [e for e in entries if e["id"] not in overridden]

    # 2) floor pool: tip_hours x points (FOH only)
    fweights = {}
    for e in free:
        pos = positions_by_name.get(e.get("position"), {})
        if pos.get("department", "FOH") != "FOH":
            continue
        pts = eff_points(e, positions_by_name)
        th = eff_tip_hours(e, settings) if by_time(settings) else 1.0
        w = pts * th
        if w > 0:
            fweights[e["id"]] = w
    fshare = _round_split(floor_left, fweights)
    floor_unassigned = floor_left if not fweights else 0.0

    # 3) bar pool: barback % first, rest to bartenders by tip hours
    bshare = {}
    barbacks = []
    bartenders = {}
    for e in free:
        pos = positions_by_name.get(e.get("position"), {})
        pct = to_float(pos.get("bar_tip_share_pct"), 0.0) or 0.0
        if pct > 0:
            barbacks.append((e["id"], pct))
        elif pos.get("receives_bar_tips"):
            bartenders[e["id"]] = eff_tip_hours(e, settings) if by_time(settings) else 1.0
    rem = bar_left
    for eid, pct in barbacks:
        amt = round(bar_left * pct / 100, 2)
        amt = min(amt, rem)
        bshare[eid] = bshare.get(eid, 0.0) + amt
        rem = round(rem - amt, 2)
    if bartenders:
        if sum(bartenders.values()) <= 0:
            bartenders = {k: 1.0 for k in bartenders}
        for k, v in _round_split(rem, bartenders).items():
            bshare[k] = bshare.get(k, 0.0) + v
        bar_unassigned = 0.0
    else:
        bar_unassigned = rem

    tot_w = sum(fweights.values())
    for e in entries:
        eid = e["id"]
        if eid in overridden:
            rows[eid] = {"floor": None, "bar": None, "total": round(overridden[eid], 2),
                         "weight": 0.0, "override": True}
        else:
            f = fshare.get(eid, 0.0)
            b = round(bshare.get(eid, 0.0), 2)
            rows[eid] = {"floor": f, "bar": b, "total": round(f + b, 2),
                         "weight": fweights.get(eid, 0.0), "override": False}
    return {
        "rows": rows,
        "floor_unassigned": round(floor_unassigned, 2),
        "bar_unassigned": round(bar_unassigned, 2),
        "overflow": round(max(0.0, need - floor_pool - bar_pool), 2),
        "value_per_point_hour": round(floor_left / tot_w, 4) if tot_w else 0.0,
    }


def split_day_tips(day_data: dict, positions_by_name: dict, settings: dict) -> dict:
    """Returns {shift: split_result} for every shift that has tips or entries."""
    entries = day_data.get("entries", [])
    tips = day_data.get("tips", {})
    out = {}
    shifts = {e.get("shift") for e in entries} | set(tips.keys())
    for sh in shifts:
        if not sh:
            continue
        es = [e for e in entries if e.get("shift") == sh]
        t = tips.get(sh, {})
        out[sh] = split_shift_tips(es, t.get("floor", 0), t.get("bar", 0),
                                   positions_by_name, settings)
    return out


def double_split_time(e: dict, day: str, settings: dict):
    """If an entry clearly covers both the day shift and dinner (a double), return the
    time to split at (Dinner's usual start), else None."""
    a, b = parse_time(e.get("time_in")), parse_time(e.get("time_out"))
    dt = settings.get("default_times", {})
    day_sh = day_shift_name(day, settings)
    if a is None or b is None or not dt.get("Dinner") or not dt.get(day_sh):
        return None
    split = parse_time(dt["Dinner"][0])
    if split is None:
        return None
    d0, d1 = parse_time(dt[day_sh][0]), parse_time(dt[day_sh][1])
    if d0 is None or d1 is None:
        return None
    d1 = d0 + span_minutes(d0, d1)
    end = a + span_minutes(a, b)
    # worked at least 3 hours of the day shift's usual hours (before dinner starts)
    # AND at least 2 hours of dinner -> it's a double
    day_part = max(0, min(end, d1, split) - max(a, d0))
    if day_part >= 180 and end - split >= 120:
        return fmt_time(split)
    return None


def split_entry(e: dict, at: str, day: str, settings: dict, new_id: str) -> tuple[dict, dict]:
    """Split one clock-in into day shift (in -> at) and Dinner (at -> out)."""
    first = dict(e)
    second = dict(e)
    for x in (first, second):
        for k in ("hours_manual", "tip_hours_manual", "tip_override", "toast_hours", "toast_in", "toast_out"):
            x.pop(k, None)
    first["time_out"] = at
    first["shift"] = day_shift_name(day, settings)
    second["id"] = new_id
    second["time_in"] = at
    second["shift"] = "Dinner"
    return first, second


# ─────────────────────────────────────────────────────────────────────────────
#  Week summary
# ─────────────────────────────────────────────────────────────────────────────
def week_summary(week: dict, employees: list[dict], positions_by_name: dict,
                 settings: dict) -> list[dict]:
    """One row per employee who worked (or has an adjustment) this week."""
    by_emp = {}
    days = week.get("days", {})
    for day in DAYS:
        dd = days.get(day)
        if not dd:
            continue
        split = split_day_tips(dd, positions_by_name, settings)
        for e in dd.get("entries", []):
            r = by_emp.setdefault(e.get("emp_id"), {
                "hours": {d: 0.0 for d in DAYS}, "tips": {d: 0.0 for d in DAYS}})
            r["hours"][day] += eff_hours(e)
            sr = split.get(e.get("shift"), {}).get("rows", {}).get(e["id"])
            if sr:
                r["tips"][day] += sr["total"]
    adj = week.get("adjustments", {})
    for eid in adj:
        by_emp.setdefault(eid, {"hours": {d: 0.0 for d in DAYS},
                                "tips": {d: 0.0 for d in DAYS}})

    emp_map = {e["id"]: e for e in employees}
    rows = []
    for eid, r in by_emp.items():
        emp = emp_map.get(eid, {"id": eid, "name": f"(deleted {eid})", "sort_order": 9999})
        a = adj.get(eid, {})
        ah = to_float(a.get("hours"), 0.0) or 0.0
        at = to_float(a.get("tips"), 0.0) or 0.0
        hrs = {d: round(v, 2) for d, v in r["hours"].items()}
        tps = {d: round(v, 2) for d, v in r["tips"].items()}
        rows.append({
            "emp_id": eid, "name": emp["name"],
            "department": emp_department(emp, positions_by_name),
            "sort_order": emp.get("sort_order", 0),
            "hours": hrs, "tips": tps,
            "adj_hours": ah, "adj_tips": at, "note": a.get("note", ""),
            "total_hours": round(sum(hrs.values()) + ah, 2),
            "total_tips": round(sum(tps.values()) + at, 2),
        })
    rows.sort(key=lambda r: (r["department"] != "FOH", r["sort_order"], r["name"]))
    return rows


def emp_department(emp: dict, positions_by_name: dict) -> str:
    main = emp.get("main_position") or (emp.get("positions") or [""])[0]
    return positions_by_name.get(main, {}).get("department", "FOH")


# ─────────────────────────────────────────────────────────────────────────────
#  Schedule helpers
# ─────────────────────────────────────────────────────────────────────────────
def scheduled_hours(slot: dict) -> float:
    h = hours_between(slot.get("start"), slot.get("end"))
    return h or 0.0

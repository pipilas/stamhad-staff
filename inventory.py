"""
Stamhad Staff — inventory data + a small order recommender.

Data (inventory.json in the data folder):
  {"items":  [{id, name, unit, category, website, link, notes, active}],
   "draft":  {"qty": {item_id: n}, "done": [item_id, ...]},
   "orders": [{id, date, lines: [{item_id, name, unit, website, qty}]}]}

RECOMMENDER (light, runs instantly, no libraries):
  For each item we look at its past orders. Between two orders the item was
  "used up" at  rate = qty / days-until-next-order.  We smooth those rates with
  an exponentially-weighted average whose weight (alpha) is fitted per item by
  checking which alpha would have predicted its own history best. Then:
      stock left now  ~ last qty - rate x days since last order
      suggested qty   = rate x days-until-next-order - stock left
  rounded to the way you usually order it. Items with fewer than 2 orders get
  no suggestion (not enough history).
"""

from __future__ import annotations

import math
import re
import statistics
from datetime import date, timedelta
from urllib.parse import urlparse, quote_plus

from store import gen_id

KNOWN_SITES = {
    "amazon.": "Amazon",
    "webstaurantstore.": "WebstaurantStore",
    "restaurantdepot.": "Restaurant Depot",
    "jetrord.": "Restaurant Depot",
    "costco.": "Costco",
    "samsclub.": "Sam's Club",
    "sysco.": "Sysco",
    "usfoods.": "US Foods",
    "walmart.": "Walmart",
    "target.": "Target",
    "katom.": "KaTom",
    "instacart.": "Instacart",
}

SEARCH_URLS = {
    "Amazon": "https://www.amazon.com/s?k={q}",
    "WebstaurantStore": "https://www.webstaurantstore.com/search/{q}.html",
    "Costco": "https://www.costco.com/CatalogSearch?keyword={q}",
    "Sam's Club": "https://www.samsclub.com/s/{q}",
    "Walmart": "https://www.walmart.com/search?q={q}",
    "Target": "https://www.target.com/s?searchTerm={q}",
    "KaTom": "https://www.katom.com/search?w={q}",
}


# ── links ───────────────────────────────────────────────────────────────────
def clean_link(url: str) -> str:
    url = (url or "").strip()
    if url and not re.match(r"^https?://", url, re.I) and "." in url.split("/")[0]:
        url = "https://" + url
    return url


def site_from_link(url: str) -> str:
    url = clean_link(url)
    if not url:
        return ""
    host = urlparse(url).netloc.lower()
    host = host[4:] if host.startswith("www.") else host
    for key, name in KNOWN_SITES.items():
        if key in host:
            return name
    base = host.split(":")[0].split(".")
    core = base[-2] if len(base) >= 2 else base[0]
    return core.capitalize() if core else ""


def name_from_link(url: str) -> str:
    """Best guess of a product name from the URL words (no internet needed)."""
    url = clean_link(url)
    if not url:
        return ""
    path = urlparse(url).path
    parts = [p for p in path.split("/") if p]
    best = ""
    for p in parts:
        p = re.sub(r"\.(html?|aspx?|php)$", "", p, flags=re.I)
        if p.lower() in ("dp", "gp", "product", "p", "ip", "item", "products", "shop"):
            continue
        words = re.split(r"[-_+]+", p)
        words = [w for w in words if w and not re.fullmatch(r"[0-9a-z]{0,3}\d{4,}[0-9a-z]*", w.lower())]
        if len(words) >= 2 and len(" ".join(words)) > len(best):
            best = " ".join(words)
    best = re.sub(r"\s+", " ", best).strip()
    if not best:
        return ""
    return " ".join(w if w.isupper() or any(ch.isdigit() for ch in w) else w.capitalize()
                    for w in best.split())[:80]


def amazon_asin(url: str) -> str:
    m = re.search(r"/(?:dp|gp/product|gp/aw/d)/([A-Z0-9]{10})", url or "", re.I)
    return m.group(1).upper() if m else ""


def amazon_cart_url(lines: list[tuple[str, float]]) -> str:
    """One link that adds every ASIN with its quantity to the Amazon cart."""
    parts = []
    for i, (asin, qty) in enumerate(lines, start=1):
        parts.append(f"ASIN.{i}={asin}&Quantity.{i}={max(1, int(math.ceil(qty)))}")
    return "https://www.amazon.com/gp/aws/cart/add.html?" + "&".join(parts)


def search_url(site: str, name: str) -> str:
    q = quote_plus(name)
    if site in SEARCH_URLS:
        return SEARCH_URLS[site].format(q=q)
    if site:
        return f"https://www.google.com/search?q={quote_plus(site + ' ' + name)}"
    return f"https://www.google.com/search?q={q}"


def fetch_title(url: str, timeout=6) -> str:
    """Try to read the page <title> (many shops block this; that's fine)."""
    import urllib.request
    req = urllib.request.Request(clean_link(url), headers={
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/605.1.15 "
                      "(KHTML, like Gecko) Version/17.0 Safari/605.1.15",
        "Accept-Language": "en-US,en;q=0.9"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        html = r.read(400_000).decode("utf-8", "ignore")
    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
    if not m:
        return ""
    import html as _h
    t = _h.unescape(re.sub(r"\s+", " ", m.group(1))).strip()
    t = re.sub(r"^(Amazon\.com\s*:\s*)", "", t, flags=re.I)
    t = re.split(r"\s+[|\-–:]\s+(?:Amazon|Webstaurant|WebstaurantStore|Costco|Walmart|Target)\b", t)[0]
    if t.lower() in ("robot check", "access denied", "", "amazon.com"):
        return ""
    return t[:90]


# ── store helpers ───────────────────────────────────────────────────────────
def load(store) -> dict:
    inv = store._load("inventory.json", None) or {}
    inv.setdefault("items", [])
    inv.setdefault("draft", {})
    inv["draft"].setdefault("qty", {})
    inv["draft"].setdefault("done", [])
    inv.setdefault("orders", [])
    inv.setdefault("settings", {"order_every_days": 7})
    return inv


def save(store, inv):
    store._save("inventory.json", inv)


def new_item(name="", link="", unit="", category="", website="") -> dict:
    link = clean_link(link)
    return {"id": gen_id(), "name": name or name_from_link(link), "unit": unit, "category": category,
            "website": website or site_from_link(link), "link": link, "notes": "", "active": True}


def item_history(inv, item_id) -> list[tuple[date, float]]:
    out = []
    for o in inv["orders"]:
        for ln in o["lines"]:
            if ln["item_id"] == item_id and ln.get("qty", 0) > 0:
                out.append((date.fromisoformat(o["date"]), float(ln["qty"])))
    # same-day duplicates add up
    agg = {}
    for d, q in out:
        agg[d] = agg.get(d, 0) + q
    return sorted(agg.items())


# ── recommender ─────────────────────────────────────────────────────────────
def _ewma(xs, alpha):
    s = xs[0]
    for x in xs[1:]:
        s = alpha * x + (1 - alpha) * s
    return s


def _fit_alpha(rates):
    """Pick the smoothing weight that best predicts each next rate from the ones before it."""
    if len(rates) < 3:
        return 0.5
    best, best_err = 0.5, float("inf")
    for a in (0.15, 0.3, 0.45, 0.6, 0.75, 0.9):
        err = 0.0
        for i in range(1, len(rates)):
            err += (rates[i] - _ewma(rates[:i], a)) ** 2
        if err < best_err:
            best, best_err = a, err
    return best


def recommend(inv, item, today: date | None = None) -> dict | None:
    """-> {"qty", "due", "rate_per_week", "days_since", "confidence", "why"} or None."""
    today = today or date.today()
    hist = item_history(inv, item["id"])
    if len(hist) < 2:
        return None
    horizon = float(inv.get("settings", {}).get("order_every_days", 7) or 7)
    rates, gaps = [], []
    for (d0, q0), (d1, _) in zip(hist, hist[1:]):
        gap = max(1, (d1 - d0).days)
        gaps.append(gap)
        rates.append(q0 / gap)
    alpha = _fit_alpha(rates)
    rate = max(0.0, _ewma(rates, alpha))
    last_d, last_q = hist[-1]
    since = max(0, (today - last_d).days)
    left = last_q - rate * since
    raw = rate * horizon - max(0.0, left)          # cover the next cycle with what's left
    qtys = [q for _, q in hist]
    step = 1.0
    if all(abs(q - round(q)) < 1e-9 for q in qtys):
        # items you always order in multiples (e.g. 2, 4, 6) keep that multiple
        g = 0
        for q in qtys:
            g = math.gcd(g, int(round(q)))
        step = float(max(1, g))
    qty = round(raw / step) * step if raw > 0 else 0.0        # nearest usual pack size
    qty = min(qty, 3 * max(qtys))
    due = left <= rate * horizon * 0.5 or qty > 0
    # confidence: more orders + steadier gaps = higher
    cv = (statistics.pstdev(gaps) / statistics.mean(gaps)) if len(gaps) > 1 else 1.0
    conf = max(0.0, min(1.0, (1 - math.exp(-(len(hist) - 1) / 3)) * (1 - min(cv, 1) * 0.6)))
    med_gap = statistics.median(gaps)
    why = (f"Usually {statistics.median(qtys):g} {item.get('unit') or ''} every ~{med_gap:g} days "
           f"(≈{rate * 7:.1f}/week). Last ordered {since} day{'s' if since != 1 else ''} ago "
           f"({last_q:g}); about {max(0.0, left):.1f} left.").replace("  ", " ")
    return {"qty": qty, "due": bool(due and qty > 0), "rate_per_week": rate * 7, "days_since": since,
            "confidence": conf, "why": why, "left": max(0.0, left)}


# ── import a list of items (CSV) ────────────────────────────────────────────
def _clean_size(v: str) -> str:
    v = (v or "").strip()
    low = v.lower()
    if low in ("", "unspecified", "n/a", "na", "-", "none"):
        return ""
    if low == "draught" or low == "draft":
        return "keg"
    return v


def read_items_csv(path) -> list[dict]:
    """Columns (any order, case-insensitive): Item/Name, Category, Size/Unit, Quantity, Notes."""
    import csv as _csv
    rows = []
    with open(path, newline="", encoding="utf-8-sig") as f:
        for r in _csv.DictReader(f):
            r = {(k or "").strip().lower(): (v or "").strip() for k, v in r.items()}
            name = r.get("item") or r.get("name") or r.get("product") or ""
            if not name:
                continue
            q = r.get("quantity") or r.get("qty") or ""
            try:
                qty = float(q)
            except ValueError:
                qty = 0.0
            rows.append({"name": " ".join(name.split()), "category": r.get("category", ""),
                         "unit": _clean_size(r.get("size") or r.get("unit") or ""),
                         "notes": r.get("notes", ""), "qty": qty})
    return rows


def import_items(store, path, put_in_cart=False) -> tuple[int, int]:
    """Add items from a CSV. Skips ones already there (same name + category). Returns (added, skipped)."""
    inv = load(store)
    have = {(i["name"].lower(), (i.get("category") or "").lower()) for i in inv["items"]}
    added = skipped = 0
    for r in read_items_csv(path):
        key = (r["name"].lower(), r["category"].lower())
        if key in have:
            skipped += 1
            continue
        it = new_item(name=r["name"], unit=r["unit"], category=r["category"])
        it["notes"] = r["notes"]
        inv["items"].append(it)
        have.add(key)
        if put_in_cart and r["qty"]:
            inv["draft"]["qty"][it["id"]] = r["qty"]
        added += 1
    save(store, inv)
    return added, skipped

#!/usr/bin/env python3
"""Stamhad Admin — manage customer accounts and subscriptions for all Stamhad apps.

Run:  python3 admin/admin.py        (or double-click admin/run_admin.command on the Mac)
Sign in with YOUR admin account (the one under /admins in the database).
Nothing secret is stored in this file: what you may change is decided by the
Firebase database rules, so this tool is safe to keep in the public repo.
"""

from __future__ import annotations

import json
import secrets
import string
import sys
import threading
import time
import tkinter as tk
from datetime import date, datetime, timedelta
from pathlib import Path
from tkinter import ttk, messagebox

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import account as A  # noqa: E402
from ui import *     # noqa: E402,F401,F403
import ui            # noqa: E402

APPS = {"staff": "Stamhad Staff", "payroll": "Stamhad Payroll"}
PLANS = ["Standard", "Pro", "Trial", "Free"]
PREFS = Path.home() / ".stamhad-admin.json"
DOWNLOAD = "https://github.com/pipilas/stamhad-staff/releases/latest"


def add_months(d: date, n: int) -> date:
    m = d.month - 1 + n
    y, m = d.year + m // 12, m % 12 + 1
    import calendar
    return date(y, m, min(d.day, calendar.monthrange(y, m)[1]))


def new_password(n=10) -> str:
    alphabet = string.ascii_letters + string.digits
    while True:
        p = "".join(secrets.choice(alphabet) for _ in range(n))
        if any(c.isdigit() for c in p) and any(c.isupper() for c in p):
            return p


def status_of(sub: dict | None) -> tuple[str, str]:
    """-> (text, colour)"""
    if not sub:
        return "—", FG_SEC
    ok, why = A.evaluate(sub)
    pu = sub.get("paid_until")
    if ok:
        if pu:
            left = (date.fromisoformat(str(pu)[:10]) - date.today()).days
            return (f"Active · {left} days left" if left <= 14 else f"Active until {pu}"), \
                (WARN_FG if left <= 7 else SUCCESS_FG)
        return "Active", SUCCESS_FG
    if not sub.get("active"):
        return "Off", DANGER
    return f"Expired {pu}", DANGER


class Admin(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Stamhad Admin")
        self.configure(bg=BG_PAGE)
        self.geometry("1180x720")
        self.minsize(900, 560)
        ui.install_global_wheel(self)
        ui.install_field_behaviour(self)
        self.tok = None            # {"uid", "id_token", "refresh_token", "at"}
        self.data = {"accounts": {}, "subscriptions": {}, "usage": {}}
        self.query = ""
        self.notice = Notice(self)
        try:
            self.prefs = json.loads(PREFS.read_text())
        except Exception:
            self.prefs = {}
        if not A.configured():
            self.show_message("Firebase isn't configured in account.py yet.")
            return
        self.show_signin()

    # ── tokens ────────────────────────────────────────────────────────────
    def id_token(self) -> str:
        if time.time() - self.tok["at"] > 45 * 60:                    # ID tokens last 60 min
            r = A.refresh(self.tok["refresh_token"])
            self.tok.update(id_token=r["id_token"], refresh_token=r["refresh_token"], at=time.time())
        return self.tok["id_token"]

    def run(self, work, done, busy_text="Working…"):
        """Run a network job in the background, then done(result, error) on the UI thread."""
        self.config(cursor="watch")

        def w():
            try:
                res, err = work(), None
            except Exception as e:
                res, err = None, e
            self.after(0, lambda: (self.config(cursor=""), done(res, err)))
        threading.Thread(target=w, daemon=True).start()

    # ── screens ───────────────────────────────────────────────────────────
    def clear(self):
        for w in self.winfo_children():
            if not isinstance(w, tk.Toplevel):
                w.destroy()
        self.notice = Notice(self)

    def show_message(self, text):
        self.clear()
        tk.Label(self, text=text, bg=BG_PAGE, fg=FG, font=(FONT, 14)).pack(expand=True)

    def show_signin(self, msg=""):
        self.clear()
        card = tk.Frame(self, bg=BG_CARD, padx=34, pady=28)
        card.place(relx=0.5, rely=0.45, anchor="center")
        tk.Label(card, text="Stamhad Admin", bg=BG_CARD, fg=FG, font=(FONT, 20, "bold")).pack(anchor="w")
        tk.Label(card, text="Sign in with your admin account", bg=BG_CARD, fg=FG_SEC, font=(FONT, 10)).pack(
            anchor="w", pady=(2, 14))
        em = tk.Entry(card, width=32, font=(FONT, 13), relief="solid", bd=1)
        em.pack(fill="x", ipady=5)
        em.insert(0, self.prefs.get("email", ""))
        pw = tk.Entry(card, width=32, font=(FONT, 13), relief="solid", bd=1, show="•")
        pw.pack(fill="x", ipady=5, pady=(8, 4))
        err = tk.Label(card, text=msg, bg=BG_CARD, fg=DANGER, font=(FONT, 10), wraplength=320, justify="left")
        err.pack(anchor="w", pady=4)

        def go(_=None):
            e, p = em.get().strip(), pw.get()

            def work():
                s = A.sign_in(e, p)
                if A.db_get(f"admins/{s['uid']}", s["id_token"]) is not True:
                    raise A.AuthError("NOT_ADMIN", "This account isn't an admin. Add its UID under /admins "
                                                   "in the Firebase console.")
                return s

            def done(s, ex):
                if ex:
                    err.config(text=str(ex) if not isinstance(ex, A.Offline) else "No internet.")
                    return
                self.tok = dict(s, at=time.time())
                self.prefs["email"] = e
                try:
                    PREFS.write_text(json.dumps(self.prefs))
                except Exception:
                    pass
                self.show_main()
            self.run(work, done)
            return "break"
        b = Btn(card, "Sign in", go, "primary")
        b.pack(fill="x", pady=(6, 0))
        for w in (em, pw):
            w.bind("<Return>", go)
        (pw if em.get() else em).focus_set()

    def show_main(self):
        self.clear()
        h = PageHeader(self, "Customers", "Accounts and subscriptions for all Stamhad apps")
        Btn(h.actions, "+ New account", self.new_account, "primary").pack(side="right")
        Btn(h.actions, "Refresh", self.load, "ghost").pack(side="right", padx=8)
        bar = tk.Frame(self, bg=BG_PAGE, padx=28)
        bar.pack(fill="x", pady=(0, 10))
        self.search = SearchBox(bar, self.on_query, "Find a business or email", width=30)
        self.search.pack(side="left")
        self.count = tk.Label(bar, text="", bg=BG_PAGE, fg=FG_SEC, font=(FONT, 10))
        self.count.pack(side="right")
        self.sf = ScrollFrame(self)
        self.sf.pack(fill="both", expand=True, padx=28, pady=(0, 16))
        self.load()

    def on_query(self, q):
        self.query = q
        self.render()

    def load(self):
        def work():
            t = self.id_token()
            return {k: (A.db_get(k, t) or {}) for k in ("accounts", "subscriptions", "usage")}

        def done(d, ex):
            if ex:
                messagebox.showerror("Couldn't load", str(ex), parent=self)
                return
            self.data = d
            self.render()
        self.run(work, done)

    def last_seen(self, uid):
        best = ""
        for app in (self.data["usage"].get(uid) or {}).values():
            for dev in (app or {}).values():
                best = max(best, (dev or {}).get("last_seen", ""))
        return best.replace("T", " ")[:16] if best else "never"

    def render(self):
        for w in self.sf.winfo_children():
            w.destroy()
        accs = self.data["accounts"]
        rows = sorted(accs.items(), key=lambda kv: (kv[1].get("business_name") or kv[1].get("email") or "").lower())
        rows = [(u, a) for u, a in rows if matches(self.query, a.get("business_name", ""), a.get("email", ""),
                                                  a.get("owner", ""))]
        self.count.config(text=f"{len(rows)} account(s)")
        card = Card(self.sf, padx=0, pady=0)
        card.pack(fill="x")
        g = tk.Frame(card, bg=BG_CARD, padx=16, pady=10)
        g.pack(fill="x")
        heads = ["Business", "Email"] + [APPS[a] for a in APPS] + ["Last seen"]
        for c, t in enumerate(heads):
            tk.Label(g, text=t, bg=BG_CARD, fg=FG_SEC, font=(FONT, 9, "bold"), anchor="w").grid(
                row=0, column=c, sticky="w", padx=8, pady=(0, 6))
        g.columnconfigure(0, weight=1)
        if not rows:
            tk.Label(g, text="No accounts yet. Click + New account.", bg=BG_CARD, fg=FG_SEC,
                     font=(FONT, 11)).grid(row=1, column=0, columnspan=len(heads), sticky="w", padx=8, pady=10)
        for r, (uid, a) in enumerate(rows, start=1):
            subs = self.data["subscriptions"].get(uid) or {}
            cells = [tk.Label(g, text=a.get("business_name") or "—", bg=BG_CARD, fg=FG,
                              font=(FONT, 11, "bold"), anchor="w"),
                     tk.Label(g, text=a.get("email", ""), bg=BG_CARD, fg=FG_SEC, font=(FONT, 10), anchor="w")]
            for app in APPS:
                t, c = status_of(subs.get(app))
                cells.append(tk.Label(g, text=t, bg=BG_CARD, fg=c, font=(FONT, 10, "bold"), anchor="w"))
            cells.append(tk.Label(g, text=self.last_seen(uid), bg=BG_CARD, fg=FG_SEC, font=(FONT, 10), anchor="w"))
            for c, w in enumerate(cells):
                w.grid(row=r, column=c, sticky="we", padx=8, pady=5)
                w.config(cursor="hand2")
                w.bind("<Button-1>", lambda e, uid=uid: self.edit(uid))
            hover(cells, BG_CARD, "#F5F7FF")

    # ── create / edit ─────────────────────────────────────────────────────
    def new_account(self):
        d = Dialog(self, "New account", width=520)
        f = {}
        for key, label, default in (("business_name", "Business name", ""), ("owner", "Owner", ""),
                                    ("email", "Email (their login)", ""), ("password", "Password", new_password())):
            d.label(d.body, label).pack(anchor="w", pady=(6, 0))
            e = Inp(d.body, width=40)
            e.set(default)
            e.pack(fill="x", ipady=3)
            f[key] = e
        apps = {}
        tk.Label(d.body, text="Subscriptions", bg=BG_PAGE, fg=FG_HDR, font=(FONT, 10, "bold")).pack(anchor="w", pady=(12, 0))
        for app, name in APPS.items():
            v = tk.BooleanVar(value=(app == "staff"))
            tk.Checkbutton(d.body, text=name, variable=v, bg=BG_PAGE, font=(FONT, 11)).pack(anchor="w")
            apps[app] = v
        row = tk.Frame(d.body, bg=BG_PAGE)
        row.pack(anchor="w", pady=(8, 0))
        tk.Label(row, text="Plan", bg=BG_PAGE, fg=FG_HDR, font=(FONT, 10, "bold")).pack(side="left")
        plan = ttk.Combobox(row, values=PLANS, width=10, state="readonly")
        plan.set(PLANS[0])
        plan.pack(side="left", padx=(6, 16))
        tk.Label(row, text="Paid until", bg=BG_PAGE, fg=FG_HDR, font=(FONT, 10, "bold")).pack(side="left")
        until = Inp(row, width=12)
        until.set(str(add_months(date.today(), 1)))
        until.pack(side="left", padx=6, ipady=2)
        tk.Label(d.body, text="YYYY-MM-DD. Leave empty for no end date.", bg=BG_PAGE, fg=FG_SEC,
                 font=(FONT, 9)).pack(anchor="w")

        def create():
            vals = {k: e.get().strip() for k, e in f.items()}
            if "@" not in vals["email"] or len(vals["password"]) < 6:
                messagebox.showwarning("Check", "Email and a password of at least 6 characters are needed.", parent=d)
                return
            pu = until.get().strip()
            if pu:
                try:
                    date.fromisoformat(pu)
                except ValueError:
                    messagebox.showwarning("Check", "Paid until must look like 2026-11-08.", parent=d)
                    return
            chosen = [a for a, v in apps.items() if v.get()]

            def work():
                uid = A.create_user(vals["email"], vals["password"])
                t = self.id_token()
                A.db_put(f"accounts/{uid}", {"business_name": vals["business_name"], "owner": vals["owner"],
                                             "email": vals["email"].lower(), "notes": "",
                                             "created_at": datetime.now().isoformat(timespec="seconds")}, t)
                for app in chosen:
                    A.db_put(f"subscriptions/{uid}/{app}", {"active": True, "plan": plan.get(),
                                                           "paid_until": pu or None,
                                                           "updated_at": datetime.now().isoformat(timespec="seconds")}, t)
                return uid

            def done(uid, ex):
                if ex:
                    messagebox.showerror("Couldn't create", str(ex), parent=d)
                    return
                d.destroy()
                self.load()
                self.show_login_details(vals["business_name"], vals["email"], vals["password"])
            self.run(work, done)
        d.buttons("Create account", create, "primary")
        d.show()

    def show_login_details(self, business, email, password):
        text = (f"Your Stamhad Staff login{(' for ' + business) if business else ''}:\n\n"
                f"Email: {email}\nPassword: {password}\n\n"
                f"Download the app: {DOWNLOAD}\n"
                f"Windows: StamhadStaff-Setup.exe · Mac: the .pkg file\n\n"
                f"You can change your password in the app: Settings → Account.")
        d = Dialog(self, "Account created", width=520)
        tk.Label(d.body, text="✓ Account created", bg=BG_PAGE, fg=SUCCESS_FG, font=(FONT, 14, "bold")).pack(anchor="w")
        t = tk.Text(d.body, height=10, wrap="word", font=(FONT, 11), relief="flat", highlightthickness=1,
                    highlightbackground=BORDER, padx=8, pady=6)
        t.insert("1.0", text)
        t.pack(fill="x", pady=8)

        def copy():
            self.clipboard_clear()
            self.clipboard_append(text)
            self.notice.show("Copied — paste it into an email or message")
        d.buttons("Copy", copy, "primary", cancel_text="Close")
        d.show()

    def edit(self, uid):
        a = dict(self.data["accounts"].get(uid) or {})
        subs = dict(self.data["subscriptions"].get(uid) or {})
        d = Dialog(self, a.get("business_name") or a.get("email", "Account"), width=700)
        f = {}
        for key, label in (("business_name", "Business name"), ("owner", "Owner"), ("notes", "Notes")):
            d.label(d.body, label).pack(anchor="w", pady=(6, 0))
            e = Inp(d.body, width=50)
            e.set(a.get(key, ""))
            e.pack(fill="x", ipady=3)
            f[key] = e
        tk.Label(d.body, text=f"Login: {a.get('email', '')}   ·   last seen {self.last_seen(uid)}",
                 bg=BG_PAGE, fg=FG_SEC, font=(FONT, 9)).pack(anchor="w", pady=(4, 0))
        widgets = {}
        for app, name in APPS.items():
            sub = subs.get(app) or {}
            box = tk.Frame(d.body, bg=BG_CARD, highlightthickness=1, highlightbackground=BORDER, padx=12, pady=8)
            box.pack(fill="x", pady=(12, 0))
            top = tk.Frame(box, bg=BG_CARD)
            top.pack(fill="x")
            on = tk.BooleanVar(value=bool(sub.get("active")))
            has = tk.BooleanVar(value=bool(sub))
            tk.Label(top, text=name, bg=BG_CARD, fg=FG, font=(FONT, 12, "bold")).pack(side="left")
            t, c = status_of(sub or None)
            tk.Label(top, text=t, bg=BG_CARD, fg=c, font=(FONT, 10, "bold")).pack(side="right")
            row = tk.Frame(box, bg=BG_CARD)
            row.pack(fill="x", pady=(6, 0))
            tk.Checkbutton(row, text="Active", variable=on, bg=BG_CARD, font=(FONT, 11),
                           command=lambda h=has: h.set(True)).pack(side="left")
            plan = ttk.Combobox(row, values=PLANS, width=9, state="readonly")
            plan.set(sub.get("plan") or PLANS[0])
            plan.pack(side="left", padx=10)
            tk.Label(row, text="Paid until", bg=BG_CARD, fg=FG_HDR, font=(FONT, 10, "bold")).pack(side="left")
            until = Inp(row, width=12)
            until.set(sub.get("paid_until") or "")
            until.pack(side="left", padx=6, ipady=2)

            def extend(months, until=until, on=on, has=has):
                try:
                    cur = date.fromisoformat(until.get().strip())
                except ValueError:
                    cur = date.today()
                base = max(cur, date.today())
                until.set(str(add_months(base, months)))
                on.set(True)
                has.set(True)
            Btn(row, "+1 month", lambda e=extend: e(1), "ghost", small=True).pack(side="left", padx=2)
            Btn(row, "+1 year", lambda e=extend: e(12), "ghost", small=True).pack(side="left", padx=2)
            if sub.get("stripe_subscription"):
                tk.Label(box, text=f"Stripe: {sub.get('stripe_status', '')}  {sub.get('stripe_subscription')}",
                         bg=BG_CARD, fg=FG_SEC, font=(FONT, 9)).pack(anchor="w", pady=(4, 0))
            widgets[app] = (has, on, plan, until)

        def save():
            acc = {k: e.get().strip() for k, e in f.items()}
            new_subs = {}
            for app, (has, on, plan, until) in widgets.items():
                if not has.get() and not on.get():
                    continue
                pu = until.get().strip()
                if pu:
                    try:
                        date.fromisoformat(pu)
                    except ValueError:
                        messagebox.showwarning("Check", f"{APPS[app]}: paid until must look like 2026-11-08.", parent=d)
                        return
                new = dict(subs.get(app) or {})
                new.update(active=on.get(), plan=plan.get(), paid_until=pu or None,
                           updated_at=datetime.now().isoformat(timespec="seconds"))
                new_subs[app] = new

            def work():
                t = self.id_token()
                A.db_patch(f"accounts/{uid}", acc, t)
                for app, sub in new_subs.items():
                    A.db_put(f"subscriptions/{uid}/{app}", sub, t)

            def done(_, ex):
                if ex:
                    messagebox.showerror("Couldn't save", str(ex), parent=d)
                    return
                d.destroy()
                self.notice.show("Saved — their app picks it up at the next check (or when they reopen it)")
                self.load()
            self.run(work, done)

        def reset():
            def done(_, ex):
                if ex:
                    messagebox.showerror("Couldn't send", str(ex), parent=d)
                else:
                    self.notice.show(f"Password reset email sent to {a.get('email')}")
            self.run(lambda: A.send_password_reset(a.get("email", "")), done)
        Btn(d.bar, "Send password reset", reset, "ghost").pack(side="left")
        d.buttons("Save", save, "primary")
        d.show()


if __name__ == "__main__":
    Admin().mainloop()

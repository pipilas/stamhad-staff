#!/usr/bin/env python3
"""Stamhad Admin - manage customer accounts and subscriptions for all Stamhad apps.

Run:  python3 admin/admin.py        (or double-click admin/run_admin.command on the Mac)
Sign in with YOUR admin account (the one under /admins in the database).
The same Customers screen is inside Stamhad Staff when you sign in there as admin.
"""

from __future__ import annotations

import json
import sys
import time
import tkinter as tk
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import account as A  # noqa: E402
import ui            # noqa: E402
from ui import *     # noqa: E402,F401,F403
from admin_ui import CustomersMixin  # noqa: E402

PREFS = Path.home() / ".stamhad-admin.json"


class Admin(tk.Tk, CustomersMixin):
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


if __name__ == "__main__":
    Admin().mainloop()

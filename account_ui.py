"""Sign-in / subscription screens that cover the app window until the account checks out."""

from __future__ import annotations

import threading
import tkinter as tk
from datetime import date

import account as acct
from applog import log
from ui import *  # noqa: F401,F403


class Gate:
    """Owns the account session for the app window.
    States: checking -> (open | signin | locked | offline)."""

    def __init__(self, app):
        self.app = app
        self.session = acct.Session(app.store.root)
        self.overlay = None
        self.state = "open"
        self.status = {}
        self._waiting = []          # things to run once the app is unlocked (e.g. welcome screen)
        self._timer = None

    # ── public ────────────────────────────────────────────────────────────
    @property
    def locked(self) -> bool:
        return self.state != "open"

    def when_open(self, fn):
        if self.locked:
            self._waiting.append(fn)
        else:
            fn()

    def start(self):
        if not self.session.signed_in:
            self.show_signin()
            return
        if self.session.within_grace():
            self._open()                     # recent good check: let them straight in…
            self.recheck(quiet=True)         # …and confirm in the background
        else:
            self.show_checking()
            self.recheck(quiet=False)

    def recheck(self, quiet=True, done=None):
        def work():
            try:
                res = acct.check(self.session, self.app.version)
                err = None
            except acct.Offline as e:
                res, err = None, e
            except acct.AuthError as e:
                res, err = {"state": "locked", "message": str(e)}, None
            except Exception as e:                       # never crash the app over a check
                log.exception("account check failed")
                res, err = None, acct.Offline(str(e))
            self.app.after(0, lambda: self._after_check(res, err, quiet, done))
        threading.Thread(target=work, daemon=True).start()

    def sign_out(self):
        log.info("signed out (%s)", self.session.data.get("email"))
        self.session.sign_out()
        self.show_signin()

    # ── after a check ─────────────────────────────────────────────────────
    def _after_check(self, res, err, quiet, done):
        if done:
            done(res, err)
        if err is not None:                                  # offline
            log.info("account check offline: %s", err)
            if self.session.within_grace():
                if self.locked:
                    self._open()
                if not quiet:
                    self.app.notice.show(f"Offline — works for {self.session.grace_left_days()} more "
                                         f"day(s) without internet", ms=4000)
            else:
                self.show_offline()
            self._schedule()
            return
        self.status = res
        st = res.get("state")
        log.info("account check: %s %s", st, res.get("message", ""))
        if st == "ok":
            if self.locked:
                self._open()
        elif st == "signed_out":
            self.show_signin(res.get("message", ""))
        else:
            self.show_locked(res.get("message", ""))
        self._schedule()

    def _schedule(self):
        if self._timer:
            try:
                self.app.after_cancel(self._timer)
            except Exception:
                pass
        self._timer = self.app.after(acct.RECHECK_HOURS * 3600 * 1000, lambda: self.recheck(quiet=True))

    # ── overlay plumbing ──────────────────────────────────────────────────
    def _cover(self, state):
        self.state = state
        if self.overlay is not None and self.overlay.winfo_exists():
            self.overlay.destroy()
        for w in self.app.winfo_children():          # close any dialog that was open
            if isinstance(w, tk.Toplevel) and not w.overrideredirect():
                try:
                    w.destroy()
                except tk.TclError:
                    pass
        o = tk.Frame(self.app, bg=BG_SIDE)
        o.place(x=0, y=0, relwidth=1, relheight=1)
        o.lift()
        self.overlay = o
        card = tk.Frame(o, bg=BG_CARD, padx=36, pady=30)
        card.place(relx=0.5, rely=0.45, anchor="center")
        tk.Label(card, text="Stamhad", bg=BG_CARD, fg=FG, font=(FONT, 22, "bold")).pack(anchor="w")
        tk.Label(card, text="STAFF", bg=BG_CARD, fg=ACCENT, font=(FONT, 10, "bold")).pack(anchor="w", pady=(0, 18))
        tk.Label(o, text=f"v{self.app.version}", bg=BG_SIDE, fg="#44506A", font=(FONT, 9)).place(
            relx=1.0, rely=1.0, anchor="se", x=-14, y=-10)
        return card

    def _open(self):
        self.state = "open"
        if self.overlay is not None and self.overlay.winfo_exists():
            self.overlay.destroy()
        self.overlay = None
        waiting, self._waiting = self._waiting, []
        for fn in waiting:
            self.app.after(200, fn)

    # ── screens ───────────────────────────────────────────────────────────
    def show_checking(self):
        card = self._cover("checking")
        tk.Label(card, text="Checking your account…", bg=BG_CARD, fg=FG_SEC, font=(FONT, 12)).pack(
            anchor="w", pady=(0, 6))
        tk.Label(card, text=self.session.data.get("email", ""), bg=BG_CARD, fg=FG_SEC, font=(FONT, 10)).pack(anchor="w")

    def show_signin(self, message=""):
        card = self._cover("signin")
        tk.Label(card, text="Sign in", bg=BG_CARD, fg=FG, font=(FONT, 16, "bold")).pack(anchor="w")
        tk.Label(card, text="Use the email and password you got from Stamhad Software.", bg=BG_CARD, fg=FG_SEC,
                 font=(FONT, 10), wraplength=340, justify="left").pack(anchor="w", pady=(2, 14))
        tk.Label(card, text="Email", bg=BG_CARD, fg=FG_HDR, font=(FONT, 10, "bold")).pack(anchor="w")
        em = tk.Entry(card, width=34, font=(FONT, 13), relief="solid", bd=1)
        em.pack(fill="x", ipady=5, pady=(2, 10))
        em.insert(0, self.session.data.get("email", ""))
        tk.Label(card, text="Password", bg=BG_CARD, fg=FG_HDR, font=(FONT, 10, "bold")).pack(anchor="w")
        pw = tk.Entry(card, width=34, font=(FONT, 13), relief="solid", bd=1, show="•")
        pw.pack(fill="x", ipady=5, pady=(2, 4))
        show = tk.BooleanVar(value=False)
        tk.Checkbutton(card, text="Show password", variable=show, bg=BG_CARD, font=(FONT, 10),
                       command=lambda: pw.config(show="" if show.get() else "•")).pack(anchor="w")
        err = tk.Label(card, text=message, bg=BG_CARD, fg=DANGER, font=(FONT, 10), wraplength=340, justify="left")
        err.pack(anchor="w", pady=(8, 4))
        btn = Btn(card, "Sign in", None, "primary")
        btn.pack(fill="x", pady=(4, 10))
        busy = {"on": False}

        def submit(_=None):
            if busy["on"]:
                return "break"
            e, p = em.get().strip(), pw.get()
            if not e or not p:
                err.config(text="Type your email and password.", fg=DANGER)
                return "break"
            busy["on"] = True
            btn._lbl.config(text="Signing in…")
            err.config(text="")

            def work():
                try:
                    res, ex = acct.complete_sign_in(self.session, e, p, self.app.version), None
                except Exception as x:
                    res, ex = None, x
                self.app.after(0, lambda: finish(res, ex))
            threading.Thread(target=work, daemon=True).start()
            return "break"

        def finish(res, ex):
            busy["on"] = False
            if not err.winfo_exists():
                return
            btn._lbl.config(text="Sign in")
            if isinstance(ex, acct.Offline):
                err.config(text="Can't reach the internet. Check the connection and try again.", fg=DANGER)
            elif ex is not None:
                err.config(text=str(ex), fg=DANGER)
                log.info("sign-in failed for %s: %s", e_val(), ex)
            elif res and res.get("state") == "ok":
                log.info("signed in as %s", self.session.data.get("email"))
                self.status = res
                self._open()
                self._schedule()
                self.app.notice.show(f"Signed in — {res.get('account', {}).get('business_name') or self.session.data.get('email')}")
            else:
                self.show_locked((res or {}).get("message", ""))

        def e_val():
            try:
                return em.get()
            except tk.TclError:
                return "?"

        def forgot(_=None):
            e = em.get().strip()
            if not e:
                err.config(text="Type your email first, then click “Forgot password?”.", fg=DANGER)
                return

            def work():
                try:
                    acct.send_password_reset(e)
                    m, c = f"Sent. Check {e} for a link to set a new password.", SUCCESS_FG
                except acct.Offline:
                    m, c = "Can't reach the internet.", DANGER
                except Exception as x:
                    m, c = str(x), DANGER
                self.app.after(0, lambda: err.winfo_exists() and err.config(text=m, fg=c))
            threading.Thread(target=work, daemon=True).start()

        btn._cmd = submit
        for w in (em, pw):
            w.bind("<Return>", submit)
            w.bind("<KP_Enter>", submit)
        lk = tk.Label(card, text="Forgot password?", bg=BG_CARD, fg=ACCENT, font=(FONT, 10, "bold"), cursor="hand2")
        lk.pack(anchor="w")
        lk.bind("<Button-1>", forgot)
        tk.Label(card, text=f"No account yet? Contact {acct.SUPPORT_EMAIL}", bg=BG_CARD, fg=FG_SEC,
                 font=(FONT, 9)).pack(anchor="w", pady=(14, 0))
        (pw if em.get() else em).focus_set()

    def show_locked(self, message=""):
        card = self._cover("locked")
        tk.Label(card, text="Subscription not active", bg=BG_CARD, fg=FG, font=(FONT, 16, "bold")).pack(anchor="w")
        tk.Label(card, text=message or "This account can't use Stamhad Staff right now.", bg=BG_CARD, fg=DANGER,
                 font=(FONT, 11), wraplength=380, justify="left").pack(anchor="w", pady=(6, 4))
        tk.Label(card, text=f"To turn it back on, contact {acct.SUPPORT_EMAIL}.\n"
                            "Your data is safe on this computer.", bg=BG_CARD, fg=FG_SEC, font=(FONT, 10),
                 wraplength=380, justify="left").pack(anchor="w", pady=(0, 14))
        tk.Label(card, text=f"Signed in as {self.session.data.get('email', '')}", bg=BG_CARD, fg=FG_SEC,
                 font=(FONT, 9)).pack(anchor="w", pady=(0, 10))
        self._buttons(card)

    def show_offline(self):
        card = self._cover("offline")
        tk.Label(card, text="Connect to the internet", bg=BG_CARD, fg=FG, font=(FONT, 16, "bold")).pack(anchor="w")
        lo = self.session.last_ok()
        when = f"The last check was on {lo:%B %d}. " if lo else ""
        tk.Label(card, text=f"{when}Stamhad Staff works up to {acct.GRACE_DAYS} days without internet, then it "
                            "needs to check your subscription once.", bg=BG_CARD, fg=FG_SEC, font=(FONT, 11),
                 wraplength=380, justify="left").pack(anchor="w", pady=(6, 14))
        self._buttons(card)

    def _buttons(self, card):
        row = tk.Frame(card, bg=BG_CARD)
        row.pack(fill="x")
        b = Btn(row, "Try again", None, "primary")
        b.pack(side="left")

        def again():
            b._lbl.config(text="Checking…")
            self.recheck(quiet=False, done=lambda r, e: b.winfo_exists() and b._lbl.config(text="Try again"))
        b._cmd = again
        Btn(row, "Save my data…", self.save_data, "ghost").pack(side="left", padx=8)
        lk = tk.Label(card, text="Sign in with another account", bg=BG_CARD, fg=ACCENT, font=(FONT, 10, "bold"),
                      cursor="hand2")
        lk.pack(anchor="w", pady=(14, 0))
        lk.bind("<Button-1>", lambda e: self.sign_out())

    def save_data(self):
        """Even when locked, people can take their data with them."""
        from pathlib import Path
        from tkinter import filedialog, messagebox
        import sharing
        start = Path.home() / "Desktop"
        path = filedialog.asksaveasfilename(parent=self.app, title="Save all my data",
                                            initialdir=str(start if start.exists() else Path.home()),
                                            initialfile=sharing.default_name(), defaultextension=sharing.EXT)
        if not path:
            return
        try:
            sharing.make_package(self.app.store, Path(path), self.app.version)
            messagebox.showinfo("Saved", f"All your data is in:\n{path}", parent=self.app)
        except Exception as ex:
            messagebox.showerror("Couldn't save", str(ex), parent=self.app)

    # ── for the Settings page ─────────────────────────────────────────────
    def summary(self) -> list[tuple[str, str]]:
        d = self.session.data
        sub = d.get("sub") or {}
        rows = [("Signed in as", d.get("email", "—")),
                ("Business", d.get("business") or "—"),
                ("Plan", sub.get("plan") or "—")]
        pu = sub.get("paid_until")
        if pu:
            try:
                until = date.fromisoformat(str(pu)[:10])
                left = (until - date.today()).days
                rows.append(("Paid until", f"{until:%B %d, %Y}" + (f"  ({left} days left)" if left >= 0 else "")))
            except ValueError:
                rows.append(("Paid until", str(pu)))
        state = d.get("last_state")
        rows.append(("Status", "Active" if state == "ok" else (d.get("last_message") or "—")))
        lc = d.get("last_check")
        rows.append(("Last checked", lc.replace("T", " ")[:16] if lc else "never"))
        return rows

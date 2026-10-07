"""Update screens: 'a new version is available' and the download/install progress."""

from __future__ import annotations

import os
import threading
import tkinter as tk
import webbrowser
from tkinter import ttk, messagebox

import updater
from applog import log
from ui import *  # noqa: F401,F403


def startup_check(app):
    """Quietly ask GitHub a few seconds after the app opens. Never blocks or nags on errors."""
    if not app.store.settings.get("update_check", True):
        return

    def work():
        try:
            info = updater.check(app.version)
        except Exception as e:
            log.info("update check skipped: %s", e)
            return
        if info["available"] and info["version"] != app.store.settings.get("skipped_version"):
            log.info("update available: %s", info["version"])
            app.after(0, lambda: ask(app, info))
    threading.Thread(target=work, daemon=True).start()


def manual_check(app, on_done=None):
    def done(info=None, err=None):
        if on_done:
            on_done()
        if err:
            messagebox.showwarning("Couldn't check", f"{err}\n\nCheck the internet connection and try again.",
                                   parent=app)
        elif info["available"]:
            ask(app, info, manual=True)
        else:
            messagebox.showinfo("Up to date", f"You have the latest version ({app.version}).", parent=app)

    def work():
        try:
            info = updater.check(app.version)
            app.after(0, lambda: done(info))
        except Exception as e:
            app.after(0, lambda: done(err=str(e)))
    threading.Thread(target=work, daemon=True).start()


def ask(app, info, manual=False):
    kind, _, problem = updater.install_target()
    d = Dialog(app, "Update available", width=500)
    tk.Label(d.body, text=f"Stamhad Staff {info['version']} is available", bg=BG_PAGE, fg=FG,
             font=(FONT, 15, "bold")).pack(anchor="w")
    tk.Label(d.body, text=f"You have {app.version}. Your data is kept — it's backed up before updating.",
             bg=BG_PAGE, fg=FG_SEC, font=(FONT, 10)).pack(anchor="w", pady=(2, 10))
    notes = (info.get("notes") or "").strip()
    if notes:
        tk.Label(d.body, text="What's new", bg=BG_PAGE, fg=FG_HDR, font=(FONT, 10, "bold")).pack(anchor="w")
        t = tk.Text(d.body, height=min(10, notes.count("\n") + 2), wrap="word", bg="#FFFFFF", fg=FG,
                    relief="flat", highlightthickness=1, highlightbackground=BORDER, font=(FONT, 10),
                    padx=8, pady=6)
        t.insert("1.0", notes)
        t.config(state="disabled")
        t.pack(fill="x", pady=(2, 8))
    if problem:
        tk.Label(d.body, text=problem, bg=WARN_BG, fg=WARN_FG,
                 font=(FONT, 10), wraplength=450, justify="left", padx=10, pady=8).pack(fill="x", pady=(4, 0))

    def later():
        d.destroy()

    def skip():
        app.store.settings["skipped_version"] = info["version"]
        app.store.save_settings()
        d.destroy()

    def go():
        d.destroy()
        run_update(app, info)

    if problem:
        d.buttons("Open download page", lambda: (webbrowser.open(info.get("page") or updater.RELEASES_PAGE),
                                                  d.destroy()), "primary", cancel_text="Later")
    else:
        d.buttons("Update now", go, "primary", cancel_text="Later")
    if not manual:
        Btn(d.bar, "Skip this version", skip, "ghost").pack(side="left")
    d.show()


def run_update(app, info):
    d = Dialog(app, "Updating", width=460)
    d.protocol("WM_DELETE_WINDOW", lambda: None)
    d.unbind("<Escape>")
    head = tk.Label(d.body, text=f"Updating to {info['version']}", bg=BG_PAGE, fg=FG, font=(FONT, 14, "bold"))
    head.pack(anchor="w")
    bar = ttk.Progressbar(d.body, mode="determinate", maximum=100, length=420)
    bar.pack(fill="x", pady=(12, 4))
    msg = tk.Label(d.body, text="Backing up your data…", bg=BG_PAGE, fg=FG_SEC, font=(FONT, 10),
                   wraplength=420, justify="left")
    msg.pack(anchor="w")
    d.show()

    def status(t):
        app.after(0, lambda: msg.config(text=t))

    def prog(got, total):
        def upd():
            if total:
                bar["value"] = got * 100 / total
                msg.config(text=f"Downloading… {got / 1e6:.1f} of {total / 1e6:.1f} MB")
            else:
                msg.config(text=f"Downloading… {got / 1e6:.1f} MB")
        app.after(0, upd)

    def failed(err):
        log.error("update to %s failed: %s", info["version"], err)
        head.config(text="The update didn't finish", fg=DANGER)
        msg.config(text=f"{err}\n\nNothing was changed — you're still on {app.version} and your data is safe.",
                   fg=FG)
        bar["value"] = 0
        for w in d.bar.winfo_children():
            w.destroy()
        d.protocol("WM_DELETE_WINDOW", d.destroy)
        d.bind("<Escape>", lambda e: d.destroy())
        Btn(d.bar, "Try again", lambda: (d.destroy(), run_update(app, info)), "primary").pack(side="right")
        Btn(d.bar, "Download page", lambda: webbrowser.open(info.get("page") or updater.RELEASES_PAGE),
            "ghost").pack(side="right", padx=8)
        Btn(d.bar, "Close", d.destroy, "ghost").pack(side="left")
        d.update_idletasks()
        d.geometry(f"{max(d.winfo_width(), 460)}x{d.winfo_reqheight()}")

    def restart():
        head.config(text="Restarting…")
        msg.config(text="The new version opens in a few seconds.")
        log.info("update to %s ready, quitting so the helper can install it", info["version"])
        app.after(600, lambda: (app.destroy(), os._exit(0)))

    def work():
        try:
            updater.backup_data(app.store.root, "before-update")
            status("Downloading…")
            pkg = updater.download(info, prog)
            status("Getting it ready…")
            updater.prepare_and_launch(pkg, app.store.root, info["version"], status)
            app.after(0, restart)
        except Exception as e:
            app.after(0, lambda e=e: failed(str(e)))
    threading.Thread(target=work, daemon=True).start()


def show_last_result(app, res):
    if not res:
        return
    to = res.get("to", "")
    ok = res.get("status") == "ok" or (res.get("status") == "started" and not updater.is_newer(to, app.version))
    if ok:
        log.info("now running %s after update", app.version)
        app.notice.show(f"Updated to {app.version} ✓", ms=4000)
    else:
        log.warning("last update failed: %s", res)
        messagebox.showwarning(
            "Update didn't install",
            f"The update to {to} didn't finish, so you're still on {app.version}.\n"
            f"{res.get('detail', '')}\n\nYou can try again in Settings → Data → Check for updates.",
            parent=app)

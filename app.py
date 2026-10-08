#!/usr/bin/env python3
"""
Stamhad Staff — employees, weekly schedule, hours and tips.

Run:  python3 app.py
"""

from __future__ import annotations

import os
import sys
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from core import DAYS, SHIFTS, monday_of, norm_time, to_float  # noqa: E402
from store import Store, gen_id  # noqa: E402
from ui import *  # noqa: E402,F401
import ui  # noqa: E402
import applog  # noqa: E402
import updater  # noqa: E402
import update_ui  # noqa: E402
import account  # noqa: E402
import account_ui  # noqa: E402

try:
    VERSION = (Path(__file__).parent / "version.txt").read_text().strip()
except Exception:
    VERSION = "0.1.0"

NAV = [
    (None, [("Home", "\u2302")]),
    ("STAFF", [("Schedule", "\U0001F4C5"), ("Hours & Tips", "\u23F1"), ("Week", "\U0001F4CA")]),
    ("INVENTORY", [("Order", "\U0001F6D2"), ("Items", "\U0001F4E6"), ("Order History", "\U0001F5C2")]),
    ("SETUP", [("Employees", "\U0001F465"), ("Positions", "\U0001F3F7"), ("Settings", "\u2699")]),
]
PAGES = [p for _, items in NAV for p, _ in items]
OLD_NAMES = {"Day": "Hours & Tips", "Week Summary": "Week", "Inventory": "Order"}
DATE_PAGES = {"Schedule": "week", "Hours & Tips": "day", "Week": "week"}

SHORTCUTS = [
    (f"{MOD_SYM}1 \u2026 {MOD_SYM}9", "Go to a page in the sidebar order (Home, Schedule, Hours & Tips, Week, "
                                     "Order, Items, History, Employees, Positions)"),
    (f"{MOD_SYM},", "Settings"),
    (f"{MOD_SYM}\u2190  /  {MOD_SYM}\u2192", "Previous / next day or week"),
    (f"{MOD_SYM}T", "Jump to today"),
    (f"{MOD_SYM}N", "Add \u2014 person, item, employee or position (depends on page)"),
    (f"{MOD_SYM}D", "Download from Toast (Hours & Tips)"),
    (f"{MOD_SYM}I", "Import a Toast CSV (Hours & Tips)"),
    (f"{MOD_SYM}E", "Export (Schedule, Week, Order History)"),
    (f"{MOD_SYM}S", "Save (Settings)"),
    ("Enter", "In a dialog: press the main button.  In a table: save and go to the row below"),
    ("\u2191 / \u2193", "Move up / down a row in tables"),
    (f"{MOD_SYM}F", "Search on this page (Schedule, Order, Items, History, Employees)"),
    ("Esc", "Clear the search / close the side panel or dialog"),
    ("Type letters", "In an open dropdown: narrow the list to matching names (Backspace widens it)"),
    (f"{MOD_SYM}/", "Show this list"),
    ("F1", "Help \u2014 opens on the topic for the page you're on"),
]


class App(tk.Tk):
    def __init__(self, store: Store | None = None):
        super().__init__()
        self.withdraw()
        self.title(f"NUME — powered by StamHad   v{VERSION}")
        self.configure(bg=BG_PAGE)
        self.minsize(1080, 700)
        set_window_icon(self)
        self._style()
        install_global_wheel(self)
        install_field_behaviour(self)

        real_run = store is None
        self.store = store or Store()
        self.version = VERSION
        self.shortcuts = SHORTCUTS
        applog.setup(self.store.root, VERSION)
        applog.install_tk(self)
        self.notice = Notice(self)
        self.sel_date = date.today()
        self.page = None
        self.page_obj = None
        self._scroll_mem = {}

        ui_state = self.store.settings.get("ui", {})
        self.geometry(ui_state.get("geometry") or "1320x860")
        self._build_sidebar()
        self.main = tk.Frame(self, bg=BG_PAGE)
        self.main.pack(side="left", fill="both", expand=True)
        self._bind_shortcuts()

        self.protocol("WM_DELETE_WINDOW", self._close)
        preset_applied = self._apply_preset()
        self.gate = None
        start = OLD_NAMES.get(ui_state.get("page"), ui_state.get("page"))
        self.go(start if start in PAGES else "Home")
        self.deiconify()
        if real_run and account.configured():
            self.gate = account_ui.Gate(self)       # sign-in / subscription check covers the window
            self.gate.start()
        if self.store.first_run and not self.store.employees:
            self.when_unlocked(self._offer_first_import)
        if real_run:
            res = updater.startup_cleanup(self.store.root)
            self.after(900, lambda: update_ui.show_last_result(self, res))
            self.after(4000, lambda: update_ui.startup_check(self))

    def locked(self) -> bool:
        """True while the sign-in / subscription screen covers the app."""
        return bool(self.gate and self.gate.locked)

    def when_unlocked(self, fn):
        if self.gate:
            self.gate.when_open(fn)
        else:
            self.after(300, fn)

    def reload_store(self):
        """Re-read everything from disk (after Receive files)."""
        self.store = Store(self.store.root)
        self.go(self.page or "Home", keep_scroll=False)
        self.refresh_badges() if hasattr(self, "refresh_badges") else None

    # ── look ────────────────────────────────────────────────────────────────
    def _style(self):
        st = ttk.Style(self)
        try:
            if not IS_MAC:
                st.theme_use("clam")
        except tk.TclError:
            pass
        st.configure("TCombobox", padding=3)
        st.configure("TCheckbutton", background=BG_CARD)
        st.configure("Vertical.TScrollbar", arrowsize=12)
        self.option_add("*Checkbutton.highlightThickness", 0)
        self.option_add("*Checkbutton.cursor", "hand2")
        self.option_add("*TCombobox*Listbox.font", (FONT, 11))
        self.option_add("*TCombobox*Listbox.selectBackground", ACCENT)
        self.option_add("*TCombobox*Listbox.selectForeground", "#FFFFFF")

    @property
    def mon(self):
        return monday_of(self.sel_date)

    # ── sidebar ─────────────────────────────────────────────────────────────
    def _build_sidebar(self):
        side = tk.Frame(self, bg=BG_SIDE, width=214)
        side.pack(side="left", fill="y")
        side.pack_propagate(False)
        top = tk.Frame(side, bg=BG_SIDE, padx=20, pady=20)
        top.pack(fill="x")
        logo = logo_image(top, "dark")
        if logo:
            tk.Label(top, image=logo, bg=BG_SIDE, bd=0).pack(anchor="w")
        else:
            tk.Label(top, text="NUME", bg=BG_SIDE, fg="#FFFFFF", font=(FONT, 20, "bold")).pack(anchor="w")
        tk.Label(top, text="powered by StamHad", bg=BG_SIDE, fg="#7EB8FF", font=(FONT, 9, "bold")).pack(
            anchor="w", pady=(6, 0))
        self.nav_btns = {}
        n = 0
        for sec, items in NAV:
            if sec:
                tk.Label(side, text=sec, bg=BG_SIDE, fg="#5F6B85", font=(FONT, 9, "bold"),
                         anchor="w", padx=22).pack(fill="x", pady=(16, 4))
            for page, icon in items:
                n += 1
                row = tk.Frame(side, bg=BG_SIDE, cursor="hand2")
                row.pack(fill="x", padx=10, pady=1)
                ic = tk.Label(row, text=icon, bg=BG_SIDE, fg=FG_SIDE, font=(FONT, 12), width=2, cursor="hand2")
                ic.pack(side="left", padx=(8, 4), pady=7)
                lb = tk.Label(row, text=page, bg=BG_SIDE, fg=FG_SIDE, font=(FONT, 12), anchor="w", cursor="hand2")
                lb.pack(side="left", fill="x", expand=True)
                badge = tk.Label(row, text="", bg=BG_SIDE, fg="#FFFFFF", font=(FONT, 9, "bold"))
                badge.pack(side="right", padx=8)
                parts = (row, ic, lb, badge)
                for w in parts:
                    w.bind("<Button-1>", lambda e, p=page: self.go(p))
                    w.bind("<Enter>", lambda e, p=page: self._paint_nav(p, hover=True))
                    w.bind("<Leave>", lambda e, p=page: self._paint_nav(p))
                key = f"{MOD_SYM}{n}" if n <= 9 else f"{MOD_SYM},"
                Tooltip(lb, key)
                self.nav_btns[page] = parts
        bottom = tk.Frame(side, bg=BG_SIDE, padx=20, pady=14)
        bottom.pack(side="bottom", fill="x")
        self.help_btn = tk.Label(bottom, text="?  Help", bg=BG_SIDE, fg="#C9D3E8", font=(FONT, 12, "bold"),
                                 cursor="hand2", anchor="w")
        self.help_btn.pack(fill="x", pady=(0, 6))
        self.help_btn.bind("<Button-1>", lambda e: self.open_help())
        self.help_btn.bind("<Enter>", lambda e: self.page != "Help" and self.help_btn.config(bg=BG_SIDE_HV, fg="#FFFFFF"))
        self.help_btn.bind("<Leave>", lambda e: self.page != "Help" and self.help_btn.config(bg=BG_SIDE, fg="#C9D3E8"))
        Tooltip(self.help_btn, "F1")
        hl = tk.Label(bottom, text="\u2328  Shortcuts", bg=BG_SIDE, fg="#6B7894", font=(FONT, 10), cursor="hand2")
        hl.pack(anchor="w")
        hl.bind("<Button-1>", lambda e: self.show_shortcuts())
        tk.Label(bottom, text=f"v{VERSION}", bg=BG_SIDE, fg="#44506A", font=(FONT, 9)).pack(anchor="w", pady=(4, 0))

    def _paint_nav(self, page, hover=False):
        parts = self.nav_btns.get(page)
        if not parts:
            return
        active = page == self.page
        bg = ACCENT if active else (BG_SIDE_HV if hover else BG_SIDE)
        fg = "#FFFFFF" if active or hover else FG_SIDE
        for w in parts[:3]:
            try:
                w.config(bg=bg, fg=fg) if w is not parts[0] else w.config(bg=bg)
            except tk.TclError:
                pass
        parts[3].config(bg="#EF4444" if parts[3].cget("text") else bg)
        parts[2].config(font=(FONT, 12, "bold" if active else "normal"))

    def set_badge(self, page, text):
        if page in self.nav_btns:
            self.nav_btns[page][3].config(text=f" {text} " if text else "")
            self._paint_nav(page)

    def refresh_badges(self):
        """Sidebar counter: how many items are in the cart."""
        try:
            import inventory as invm
            inv = invm.load(self.store)
            n = len([k for k, v in inv["draft"]["qty"].items() if v])
            self.set_badge("Order", str(n) if n else "")
        except Exception:
            pass

    # ── keyboard ────────────────────────────────────────────────────────────
    def _bind_shortcuts(self):
        def on(key, fn, need_no_typing=False):
            def h(ev):
                if self._dialog_open() or self.locked():
                    return
                if need_no_typing and isinstance(self.focus_get(), tk.Entry):
                    return
                fn()
                return "break"
            self.bind_all(f"<{MOD}-{key}>", h)

        for i, p in enumerate(PAGES[:9], start=1):
            on(f"Key-{i}", lambda p=p: self.go(p))
        on("comma", lambda: self.go("Settings"))
        on("Left", lambda: self.step(-1), need_no_typing=True)
        on("Right", lambda: self.step(+1), need_no_typing=True)
        on("bracketleft", lambda: self.step(-1))
        on("bracketright", lambda: self.step(+1))
        for ch, action in (("t", "today"), ("n", "new"), ("d", "download"), ("i", "import"),
                           ("e", "export"), ("s", "save")):
            on(ch, lambda a=action: self._action(a))
            on(ch.upper(), lambda a=action: self._action(a))
        on("slash", self.show_shortcuts)
        on("question", self.open_help)
        self.bind_all("<F1>", lambda e: (None if self.locked() else self.open_help(), "break")[1])
        on("f", self.focus_search)
        on("F", self.focus_search)
        self.bind("<Escape>", self._escape)

    def focus_search(self):
        sb = getattr(self.page_obj, "search_box", None)
        if sb is not None and sb.winfo_exists():
            sb.focus()
        else:
            self.notice.show("No search on this page")

    def _escape(self, ev=None):
        dr = getattr(self.page_obj, "drawer", None)
        if dr is not None and dr.winfo_exists() and dr.is_open:
            dr.close()
        else:
            self.focus_set()

    def _dialog_open(self):
        return any(isinstance(w, tk.Toplevel) and w.winfo_viewable() and not w.overrideredirect()
                   for w in self.winfo_children())

    def _action(self, a):
        po = self.page_obj
        if a == "today":
            if self.page in DATE_PAGES:
                self.set_date(date.today())
        elif a == "new":
            if po and hasattr(po, "add_new"):
                po.add_new()
        elif a == "download" and self.page == "Hours & Tips" and po:
            po.download_toast()
        elif a == "import" and self.page == "Hours & Tips" and po:
            po.import_csv()
        elif a == "export" and po and hasattr(po, "export_pdf"):
            po.export_pdf()
        elif a == "save":
            if self.page == "Settings" and po:
                po.save()
            else:
                self.focus_set()
                self.notice.show("Everything is saved automatically \u2713")

    def open_help(self, topic=None):
        """Help page, opened on the topic for the page you were on."""
        if self._dialog_open():
            return
        if self.page != "Help":
            from page_help import PAGE_TOPIC
            self._help_topic = topic or PAGE_TOPIC.get(self.page, getattr(self, "_help_topic", None) or "start")
            self._help_query = ""
        elif topic:
            self._help_topic = topic
        self.go("Help", keep_scroll=False)

    def show_shortcuts(self):
        dlg = Dialog(self, "Keyboard shortcuts", width=820)
        g = tk.Frame(dlg.body, bg=BG_CARD, highlightbackground=BORDER, highlightthickness=1, padx=14, pady=10)
        g.pack(fill="both", expand=True)
        for r, (k, t) in enumerate(SHORTCUTS):
            tk.Label(g, text=k, bg="#EEF2FF", fg=ACCENT, font=(FONT, 11, "bold"), padx=8, pady=2).grid(
                row=r, column=0, sticky="w", pady=3)
            tk.Label(g, text=t, bg=BG_CARD, fg=FG, font=(FONT, 11), anchor="w", justify="left",
                     wraplength=560).grid(row=r, column=1, sticky="w", padx=12)
        dlg.buttons("Got it", dlg.destroy, "primary", cancel_text=None)
        dlg.show()

    # ── navigation ──────────────────────────────────────────────────────────
    def date_nav(self, parent):
        """The ◀ date ▶ Today control for pages that have a date."""
        unit = DATE_PAGES.get(self.page)
        if unit == "day":
            t = self.sel_date.strftime("%a, %b %d %Y")
        else:
            m = self.mon
            s = m + timedelta(days=6)
            end = s.strftime("%d, %Y") if s.month == m.month else s.strftime("%b %d, %Y")
            t = f"{m.strftime('%b %d')} \u2013 {end}"
        return DateNav(parent, t, lambda: self.step(-1), lambda: self.step(+1),
                       lambda: self.set_date(date.today()), tip_unit=unit or "day",
                       pick=(self.sel_date, unit or "day", self.set_date))

    def step(self, n):
        unit = DATE_PAGES.get(self.page)
        if not unit:
            return
        self.sel_date += timedelta(days=n if unit == "day" else 7 * n)
        self.go(self.page, keep_scroll=False)

    def set_date(self, d):
        self.sel_date = d
        self.go(self.page, keep_scroll=False)

    def open_day(self, d):
        self.sel_date = d
        self.go("Hours & Tips", keep_scroll=False)

    def _commit_focus(self):
        self.focus_set()          # commit any field being edited
        try:
            self.update()
        except tk.TclError:
            pass

    def scroll_key(self):
        return (self.page, self.sel_date if DATE_PAGES.get(self.page) == "day" else self.mon)

    def go(self, page, keep_scroll=True):
        page = OLD_NAMES.get(page, page)
        if getattr(self, "_cal_popup", None) is not None:
            self._cal_popup.close()
        self._commit_focus()
        if self.page:
            sf = getattr(self.page_obj, "sf", None)
            if sf:
                try:
                    self._scroll_mem[self.scroll_key()] = sf.position()
                except tk.TclError:
                    pass
        prev = self.page
        self.page = page
        self.page_obj = None
        if prev:
            self._paint_nav(prev)
        self._paint_nav(page)
        for w in self.main.winfo_children():
            w.destroy()
        if page == "Home":
            from page_home import HomePage as P
        elif page == "Schedule":
            from page_schedule import SchedulePage as P
        elif page == "Hours & Tips":
            from page_day import DayPage as P
        elif page == "Week":
            from page_week import WeekPage as P
        elif page == "Order":
            from page_inventory import OrderPage as P
        elif page == "Items":
            from page_inventory import ItemsPage as P
        elif page == "Order History":
            from page_inventory import HistoryPage as P
        elif page == "Employees":
            from page_setup import EmployeesPage as P
        elif page == "Positions":
            from page_setup import PositionsPage as P
        elif page == "Help":
            from page_help import HelpPage as P
        else:
            from page_setup import SettingsPage as P
        self.page_obj = P(self, self.main)
        try:
            self.help_btn.config(fg="#FFFFFF" if page == "Help" else "#C9D3E8",
                                 bg=ACCENT if page == "Help" else BG_SIDE)
        except (AttributeError, tk.TclError):
            pass
        sf = getattr(self.page_obj, "sf", None)
        if sf and keep_scroll:
            sf.restore(self._scroll_mem.get(self.scroll_key(), 0.0))
        self.after(50, self.refresh_badges)

    def refresh(self):
        self.go(self.page)

    def _close(self):
        self._commit_focus()
        try:
            self.store.settings["ui"] = {"geometry": self.geometry(), "page": self.page}
            self.store.save_settings()
        except Exception:
            pass
        self.destroy()

    # ── one-time setup file dropped next to the app (preset.json) ───────────
    def _apply_preset(self) -> bool:
        """preset.json next to app.py can carry Toast settings + an employee export to import once."""
        import json
        base = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
        p = base / "preset.json"
        if not p.exists():
            return False
        try:
            pre = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return False
        done = self.store.settings.setdefault("applied_presets", [])
        if pre.get("id") in done:
            return False
        msgs = []
        try:
            import toast
            t = self.store.settings.setdefault("toast", {})
            for k, v in (pre.get("toast") or {}).items():
                t[k] = v
            key = Path(pre["key"]).expanduser() if pre.get("key") else None
            if key and key.exists():
                t["key_path"] = str(toast.install_key_file(key))
                msgs.append("Toast key set up")
            pos_changes = pre.get("positions") or {}
            if pos_changes:
                changed = []
                for name, fields in pos_changes.items():
                    p = next((x for x in self.store.positions if x["name"].lower() == name.lower()), None)
                    if p:
                        p.update(fields)
                        changed.append(f"{p['name']} {fields.get('tip_points', '')}".strip())
                if changed:
                    self.store.save_positions()
                    msgs.append("Points: " + ", ".join(changed))
            inv_csv = pre.get("inventory_csv")
            if inv_csv:
                ip = (p.parent / inv_csv).resolve()
                if ip.exists():
                    import inventory as invm
                    n, sk = invm.import_items(self.store, ip, put_in_cart=pre.get("inventory_to_cart", False))
                    msgs.append(f"{n} inventory items added" + (f" ({sk} already there)" if sk else ""))
            csv_path = pre.get("employees_csv")
            if csv_path:
                cp = (p.parent / csv_path).resolve()
                if cp.exists():
                    n, npos = self.store.import_toast_employees(cp, replace=pre.get("replace", True))
                    msgs.append(f"{n} employees and {npos} positions imported from Toast")
        except Exception as ex:
            messagebox.showerror("Setup", f"Couldn't finish the setup:\n{ex}", parent=self)
        done.append(pre.get("id"))
        self.store.save_settings()
        if msgs:
            self.after(600, lambda: self.notice.show("  \u2713 " + "  \u00b7  ".join(msgs), ms=6000))
        return True

    # ── first run ───────────────────────────────────────────────────────────
    def _offer_first_import(self):
        """Brand-new install: no employees yet. Ask how tips are split and how to add people."""
        self.store.save_positions()
        self.store.save_employees()
        self.store.save_settings()
        st = self.store.settings
        d = Dialog(self, "Welcome to NUME", width=600)
        tk.Label(d.body, text="Welcome to NUME \U0001F44B", bg=BG_PAGE, fg=FG,
                 font=(FONT, 18, "bold")).pack(anchor="w")
        tk.Label(d.body, text="Two quick choices and you're ready. You can change both later.",
                 bg=BG_PAGE, fg=FG_SEC, font=(FONT, 11)).pack(anchor="w", pady=(2, 14))
        tk.Label(d.body, text="1.  How are tips split?", bg=BG_PAGE, fg=FG, font=(FONT, 13, "bold")).pack(anchor="w")
        meth = tk.StringVar(value=st.get("tip_method", "points"))
        for val, title, sub in (
                ("points", "By points only", "Everyone on the shift gets their position's points, however long they "
                                             "stayed."),
                ("time", "By time worked \u00d7 points", "Who came earlier or stayed longer gets more. The tip clock "
                                                         "times are in Settings \u2192 Tips & shifts.")):
            tk.Radiobutton(d.body, text=title, variable=meth, value=val, bg=BG_PAGE, font=(FONT, 12, "bold"),
                           anchor="w").pack(anchor="w", pady=(4, 0))
            tk.Label(d.body, text=sub, bg=BG_PAGE, fg=FG_SEC, font=(FONT, 10), wraplength=540,
                     justify="left").pack(anchor="w", padx=(26, 0))
        tk.Label(d.body, text="2.  Add your employees", bg=BG_PAGE, fg=FG, font=(FONT, 13, "bold")).pack(
            anchor="w", pady=(16, 2))
        tk.Label(d.body, text="The app starts empty. Positions come with suggested tip points "
                              "(Server 10, Bartender 5, Busser 5\u2026). Check them in Positions.",
                 bg=BG_PAGE, fg=FG_SEC, font=(FONT, 10), wraplength=540, justify="left").pack(anchor="w", pady=(0, 6))
        how = tk.StringVar(value="toast")
        opts = [("toast", "Import a Toast employee export (CSV)",
                 "Toast Web \u2192 Employees \u2192 Export. Brings names and jobs.")]
        opts += [("file", "Receive a file from another computer",
                  "A .stamhad file made with Settings \u2192 Data \u2192 Share files."),
                 ("manual", "I'll add them myself", "Opens Employees \u2192 + Add employee.")]
        for val, title, sub in opts:
            tk.Radiobutton(d.body, text=title, variable=how, value=val, bg=BG_PAGE, font=(FONT, 12),
                           anchor="w").pack(anchor="w", pady=(2, 0))
            tk.Label(d.body, text=sub, bg=BG_PAGE, fg=FG_SEC, font=(FONT, 9), wraplength=540,
                     justify="left").pack(anchor="w", padx=(26, 0))

        def start():
            st["tip_method"] = meth.get()
            self.store.save_settings()
            choice = how.get()
            d.destroy()
            if choice == "toast":
                self.go("Employees")
                self.after(100, self.page_obj.import_toast)
            elif choice == "file":
                self._settings_tab = "Data"
                self.go("Settings")
                self.after(100, self.page_obj.receive_files)
            else:
                self.go("Employees")
                self.after(100, lambda: self.page_obj.edit(None))
        d.buttons("Get started", start, "primary", cancel_text=None)
        d.protocol("WM_DELETE_WINDOW", start)
        d.show(focus=d)


def selftest() -> int:
    """Used by the GitHub build: prove the packaged app can start. Exit code 0 = good."""
    import importlib
    import traceback
    out = Path.home() / "stamhad-staff-selftest.txt"
    try:
        for m in ("core", "store", "ui", "toast", "quick", "inventory", "exports", "applog", "updater",
                  "update_ui", "sharing", "account", "account_ui", "admin_ui", "page_help", "page_home", "page_day", "page_schedule", "page_week",
                  "page_inventory", "page_setup", "paramiko", "reportlab.platypus", "certifi"):
            importlib.import_module(m)
        r = tk.Tk()
        r.withdraw()
        r.update()
        r.destroy()
        assert VERSION and VERSION != "0.1.0", "version.txt missing from the build"
        kind, target, problem = updater.install_target()
        out.write_text(f"OK {VERSION}\nkind={kind}\ntarget={target}\nproblem={problem}\n")
        return 0
    except Exception:
        out.write_text("FAIL\n" + traceback.format_exc())
        return 1


def selftest_update(pkg: str) -> int:
    """Used by the GitHub build: run the REAL in-app update with an installer file, then quit
    like the app does. CI then checks that the new version was installed and reopened."""
    import traceback
    out = Path.home() / "stamhad-staff-selftest.txt"
    try:
        root = Store().root
        applog.setup(root, VERSION)
        updater.prepare_and_launch(Path(pkg), root, VERSION, lambda m: print(m, flush=True))
        out.write_text(f"UPDATE STARTED {VERSION}\n")
        return 0
    except Exception:
        out.write_text("UPDATE FAIL\n" + traceback.format_exc())
        return 1


def main():
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    if "--selftest-update" in sys.argv:
        os._exit(selftest_update(sys.argv[sys.argv.index("--selftest-update") + 1]))
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()

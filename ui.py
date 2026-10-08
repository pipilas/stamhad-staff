"""Stamhad Staff — shared look & widgets (same style as Stamhad Payroll)."""

from __future__ import annotations

import platform
import tkinter as tk
from tkinter import ttk
from pathlib import Path

IS_MAC = platform.system() == "Darwin"
IS_WIN = platform.system() == "Windows"
FONT = "Helvetica Neue" if IS_MAC else ("Segoe UI" if IS_WIN else "DejaVu Sans")

BG_PAGE = "#F0F2F5"
BG_CARD = "#FFFFFF"
BG_NAV = "#1B2A4A"
BORDER = "#E5E7EB"
BORDER_FOCUS = "#4F46E5"
FG = "#1C1C1E"
FG_SEC = "#6B7280"
FG_HDR = "#374151"
ACCENT = "#4F46E5"
ACCENT_HV = "#4338CA"
SUCCESS = "#10B981"
SUCCESS_HV = "#059669"
SUCCESS_BG = "#D1FAE5"
SUCCESS_FG = "#065F46"
WARN_BG = "#FEF3C7"
WARN_FG = "#92400E"
WARN_BORD = "#F59E0B"
WARN_HV = "#D97706"
DANGER = "#EF4444"
DANGER_HV = "#DC2626"
EXPORT_BG = "#0891B2"
EXPORT_HV = "#0E7490"
MANUAL_BG = "#FEF9C3"      # yellow = value typed by hand (overrides automation)
ROW_A = "#FFFFFF"
ROW_B = "#F5F7FA"
FOH_BG, BOH_BG = "#3B82F6", "#F97316"

SHIFT_CLR = {"Morning": ("#FCD34D", "#78350F"),
             "Brunch": ("#34D399", "#064E3B"),
             "Dinner": ("#818CF8", "#312E81")}

ICONS_DIR = Path(__file__).parent / "icons"


def logo_image(master, variant="dark"):
    """The NUME wordmark (icons/wordmark_dark.png on dark backgrounds, _light on white), or None."""
    try:
        p = ICONS_DIR / f"wordmark_{variant}.png"
        if p.exists():
            img = tk.PhotoImage(master=master, file=str(p))
            refs = getattr(master, "_logo_refs", [])
            refs.append(img)
            master._logo_refs = refs
            return img
    except Exception:
        pass
    return None


def set_window_icon(win):
    try:
        ico = ICONS_DIR / "icon.ico"
        if IS_WIN and ico.exists():
            win.iconbitmap(str(ico))
            return
        png = ICONS_DIR / "icon_64.png"
        if png.exists():
            img = tk.PhotoImage(master=win, file=str(png))
            win.iconphoto(True, img)
            win._icon_ref = img
    except Exception:
        pass


def money(v) -> str:
    return f"${v:,.2f}"


def hrs(v) -> str:
    return f"{v:.2f}"


MOD = "Command" if IS_MAC else "Control"          # shortcut modifier key
MOD_SYM = "\u2318" if IS_MAC else "Ctrl+"


# ═════════════════════════════════════════════════════════════════════════════
#  SMOOTH SCROLLING
# ═════════════════════════════════════════════════════════════════════════════
class _Smooth:
    """Pixel-based, eased scrolling for one canvas."""

    def __init__(self, canvas):
        self.c = canvas
        self.target = None
        self.job = None

    def _total(self):
        try:
            sr = [float(x) for x in str(self.c.cget("scrollregion")).split()]
            return sr[3] - sr[1] if len(sr) == 4 else 0.0
        except (ValueError, tk.TclError):
            return 0.0

    def by(self, px, animate=True):
        total = self._total()
        view = self.c.winfo_height()
        if total <= view + 1:
            return
        cur = self.c.yview()[0] * total
        base = self.target if (self.job and self.target is not None) else cur
        tgt = max(0.0, min(total - view, base + px))
        if not animate:
            self._stop()
            self.c.yview_moveto(tgt / total)
            return
        self.target = tgt
        if not self.job:
            self._tick()

    def _stop(self):
        if self.job:
            try:
                self.c.after_cancel(self.job)
            except tk.TclError:
                pass
        self.job = None
        self.target = None

    def _tick(self):
        try:
            total = self._total()
            cur = self.c.yview()[0] * total
            d = self.target - cur
            if abs(d) < 1.0 or total <= 0:
                self.c.yview_moveto(self.target / total if total else 0)
                self.job = None
                self.target = None
                return
            self.c.yview_moveto((cur + d * 0.28) / total)
            self.job = self.c.after(8, self._tick)
        except (tk.TclError, TypeError):
            self.job = None


def smooth(canvas) -> _Smooth:
    if not hasattr(canvas, "_smooth"):
        canvas._smooth = _Smooth(canvas)
    return canvas._smooth


class ScrollFrame(tk.Frame):
    """Vertical (and optional horizontal) scrolling frame with smooth scrolling."""

    def __init__(self, parent, bg=BG_PAGE, horizontal=False):
        self._outer = tk.Frame(parent, bg=bg)
        self.canvas = tk.Canvas(self._outer, bg=bg, highlightthickness=0, bd=0,
                                yscrollincrement=1, xscrollincrement=1)
        self.vsb = ttk.Scrollbar(self._outer, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self._vset)
        self._horizontal = horizontal
        if horizontal:
            self.hsb = ttk.Scrollbar(self._outer, orient="horizontal", command=self.canvas.xview)
            self.canvas.configure(xscrollcommand=self.hsb.set)
            self.hsb.pack(side="bottom", fill="x")
        self.vsb.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        super().__init__(self.canvas, bg=bg)
        self._win = self.canvas.create_window((0, 0), window=self, anchor="nw")
        self.bind("<Configure>", self._content_changed)
        self.canvas.bind("<Configure>", self._cfg)
        self.after(300, self._watch)

    def _watch(self):
        """Cheap check a few times a second: if the content height changed, fix the scroll."""
        try:
            bb = self.canvas.bbox("all")
            h = (bb[3] - bb[1]) if bb else 0
            if h != getattr(self, "_last_h", None):
                self._last_h = h
                self._content_changed()
            self._watch_job = self.after(250, self._watch)
        except tk.TclError:
            pass

    def _content_changed(self, _=None):
        """Content got taller/shorter: update the scroll area and never leave the view
        pointing past the end (that shows an empty page)."""
        try:
            bb = self.canvas.bbox("all")
            self.canvas.configure(scrollregion=bb)
            total = (bb[3] - bb[1]) if bb else 0
            view = self.canvas.winfo_height()
            if total <= view + 1:
                self.canvas.yview_moveto(0)
            else:
                top = self.canvas.yview()[0] * total
                if top + view > total:
                    self.canvas.yview_moveto(max(0.0, (total - view) / total))
        except tk.TclError:
            pass

    def to_top(self):
        try:
            sm = getattr(self.canvas, "_smooth", None)
            if sm:
                sm._stop()
            self._content_changed()
            self.canvas.yview_moveto(0)
        except tk.TclError:
            pass

    def _vset(self, lo, hi):
        # hide the scrollbar when everything fits
        self.vsb.set(lo, hi)
        try:
            if float(lo) <= 0.0 and float(hi) >= 1.0:
                self.vsb.pack_forget()
            elif not self.vsb.winfo_ismapped():
                self.vsb.pack(side="right", fill="y", before=self.canvas)
        except tk.TclError:
            pass

    def _cfg(self, e):
        if self._horizontal:
            self.canvas.itemconfig(self._win, width=max(e.width, self.winfo_reqwidth()))
        else:
            self.canvas.itemconfig(self._win, width=e.width)
        self.after_idle(self._content_changed)

    # remember / restore position across page rebuilds
    def position(self) -> float:
        try:
            return self.canvas.yview()[0]
        except tk.TclError:
            return 0.0

    def restore(self, frac: float):
        if frac:
            def go():
                try:
                    self.canvas.update_idletasks()
                    self.canvas.configure(scrollregion=self.canvas.bbox("all"))
                    self.canvas.yview_moveto(frac)
                except tk.TclError:
                    pass
            self.canvas.after_idle(go)

    def scroll_into_view(self, widget, margin=40):
        """Scroll so that widget (inside this frame) is visible."""
        try:
            self.canvas.update_idletasks()
            y = widget.winfo_rooty() - self.winfo_rooty()
            h = widget.winfo_height()
            total = self.winfo_height()
            view = self.canvas.winfo_height()
            top = self.canvas.yview()[0] * total
            if y - margin < top:
                smooth(self.canvas).by(y - margin - top)
            elif y + h + margin > top + view:
                smooth(self.canvas).by(y + h + margin - top - view)
        except tk.TclError:
            pass

    def pack(self, **kw):
        self._outer.pack(**kw)

    def grid(self, **kw):
        self._outer.grid(**kw)

    def destroy(self):
        if getattr(self, "_dying", False):
            return
        self._dying = True
        job = getattr(self, "_watch_job", None)
        if job:
            try:
                self.after_cancel(job)
            except tk.TclError:
                pass
        self._outer.destroy()


def _find_canvas(w):
    while w is not None:
        if isinstance(w, tk.Canvas):
            try:
                if w.cget("scrollregion"):
                    return w
            except tk.TclError:
                pass
        w = getattr(w, "master", None)
    return None


def install_global_wheel(root):
    """Smooth wheel/trackpad scrolling everywhere. Wheel over a dropdown scrolls
    the page instead of silently changing the dropdown's value."""

    def widget_of(ev):
        w = ev.widget
        if isinstance(w, str):
            try:
                w = root.nametowidget(w)
            except (KeyError, tk.TclError):
                return None
        return w

    def wheel(ev):
        w = widget_of(ev)
        c = _find_canvas(w)
        if not c:
            return
        if ev.state & 0x0001 and getattr(c, "xview", None):      # Shift = sideways
            c.xview_scroll(int(-ev.delta * (4 if IS_MAC else 0.5)), "units")
            return "break"
        if IS_MAC:
            # trackpad sends many small deltas (already smooth); mouse wheel bigger ones
            if abs(ev.delta) < 4:
                smooth(c).by(-ev.delta * 7, animate=False)
            else:
                smooth(c).by(-ev.delta * 14)
        else:
            smooth(c).by(-ev.delta / 120 * 90)
        return "break"

    def wheel_x11(ev):
        c = _find_canvas(widget_of(ev))
        if c:
            smooth(c).by(-90 if ev.num == 4 else 90)
        return "break"

    root.bind_all("<MouseWheel>", wheel)
    root.bind_all("<Shift-MouseWheel>", wheel)
    # dropdowns: scroll the page, never change the value
    root.bind_class("TCombobox", "<MouseWheel>", wheel)
    if not IS_MAC:
        root.bind_all("<Button-4>", wheel_x11)
        root.bind_all("<Button-5>", wheel_x11)
        root.bind_class("TCombobox", "<Button-4>", wheel_x11)
        root.bind_class("TCombobox", "<Button-5>", wheel_x11)


# ═════════════════════════════════════════════════════════════════════════════
#  FRIENDLIER FIELDS
# ═════════════════════════════════════════════════════════════════════════════
def install_field_behaviour(root):
    """Select-all when a field gets focus (so typing replaces), and type-ahead
    for dropdowns (press letters to jump to a name)."""

    def focus_in(ev):
        w = ev.widget
        try:
            if str(w.cget("state")) == "normal":
                w.after_idle(lambda: _select_all(w))
        except tk.TclError:
            pass

    root.bind_class("Entry", "<FocusIn>", focus_in, add="+")

    def type_ahead(ev):
        w = ev.widget
        ch = ev.char
        if not ch or not ch.isprintable() or ev.state & 0x000C:      # ignore Ctrl/Cmd combos
            return
        try:
            if str(w.cget("state")) != "readonly":
                return
        except tk.TclError:
            return
        now = ev.time or 0
        buf = getattr(w, "_ta_buf", "")
        if now - getattr(w, "_ta_time", 0) > 900:
            buf = ""
        buf += ch.lower()
        w._ta_buf, w._ta_time = buf, now
        vals = [str(v) for v in w.cget("values")]
        hit = next((v for v in vals if v.lower().startswith(buf)), None) or \
            next((v for v in vals if any(p.startswith(buf) for p in v.lower().split())), None) or \
            next((v for v in vals if buf in v.lower()), None)
        if hit and hit != w.get():
            w.set(hit)
            w._ta_pending = True
        return "break"

    def commit_type_ahead(ev):
        w = ev.widget
        if getattr(w, "_ta_pending", False):
            w._ta_pending = False
            w.event_generate("<<ComboboxSelected>>")

    root.bind_class("TCombobox", "<KeyPress>", type_ahead, add="+")
    root.bind_class("TCombobox", "<FocusOut>", commit_type_ahead, add="+")
    root.bind_class("TCombobox", "<Return>", commit_type_ahead, add="+")

    # ── open list: typing letters narrows it down ─────────────────────────────
    def _cb_of(lb_path):
        try:
            return root.nametowidget(root.tk.call("ttk::combobox::LBMaster", lb_path))
        except (KeyError, tk.TclError):
            return None

    def list_filter(ev):
        lb_path = str(ev.widget)
        cb = _cb_of(lb_path)
        if cb is None:
            return
        ch = ev.char
        if ev.keysym == "BackSpace":
            buf = getattr(cb, "_lf_buf", "")[:-1]
        elif ch and ch.isprintable() and not ev.state & 0x000C:
            buf = getattr(cb, "_lf_buf", "") + ch.lower()
        else:
            return
        if not hasattr(cb, "_lf_full"):
            cb._lf_full = list(cb.cget("values"))
        full = [str(v) for v in cb._lf_full]
        fixed = [v for v in full if v.startswith("+")]            # "+ New employee…" stays on top

        def ok(v):
            lv = v.lower()
            return lv.startswith(buf) or any(p.startswith(buf) for p in lv.split())
        pool = [v for v in full if not v.startswith("+") and v.strip(" -—─")]
        hits = ([v for v in pool if v.lower().startswith(buf)] +
                [v for v in pool if ok(v) and not v.lower().startswith(buf)]) if buf else full
        if buf and not hits:
            root.bell()
            return "break"
        cb._lf_buf = buf
        vals = fixed + hits if buf else full
        cb.configure(values=vals)
        cb._lf_set = [str(v) for v in vals]
        try:
            root.tk.call("ttk::combobox::ConfigureListbox", str(cb))
            first = len(fixed) if buf else 0
            for op in (("selection", "clear", 0, "end"), ("selection", "set", first),
                       ("activate", first), ("see", first)):
                root.tk.call(lb_path, *op)
            root.update_idletasks()
            root.tk.call("ttk::combobox::PlacePopdown", str(cb), str(cb) + ".popdown")
        except tk.TclError:
            pass
        return "break"

    def _restore(cb):
        full = getattr(cb, "_lf_full", None)
        cb._lf_buf = ""
        if full is None:
            return
        del cb._lf_full
        if [str(v) for v in cb.cget("values")] != getattr(cb, "_lf_set", None):
            return                      # something else changed the list since - leave it
        cur = cb.get()
        cb.configure(values=full)
        cb.set(cur)

    def list_restore(ev):
        path = str(ev.widget)
        if path.endswith(".popdown"):
            try:
                _restore(root.nametowidget(path[: -len(".popdown")]))
            except KeyError:
                pass

    def list_done(ev):
        cb = _cb_of(str(ev.widget))
        if cb is not None:
            _restore(cb)

    for seq in ("<ButtonRelease-1>", "<Return>", "<Escape>"):
        root.bind_class("ComboboxListbox", seq, list_done, add="+")
    root.bind_class("ComboboxListbox", "<KeyPress>", list_filter, add="+")
    root.bind_class("ComboboxPopdown", "<Unmap>", list_restore, add="+")


def _select_all(w):
    try:
        if w.focus_get() is w:
            w.select_range(0, "end")
            w.icursor("end")
    except (tk.TclError, KeyError):
        pass


class Tooltip:
    def __init__(self, widget, text, delay=550):
        self.w, self.text, self.delay = widget, text, delay
        self.tip = None
        self.job = None
        widget.bind("<Enter>", self._sched, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<ButtonPress>", self._hide, add="+")

    def _sched(self, _=None):
        self._hide()
        self.job = self.w.after(self.delay, self._show)

    def _show(self):
        try:
            x = self.w.winfo_rootx() + 8
            y = self.w.winfo_rooty() + self.w.winfo_height() + 6
            self.tip = tk.Toplevel(self.w)
            self.tip.wm_overrideredirect(True)
            self.tip.wm_geometry(f"+{x}+{y}")
            tk.Label(self.tip, text=self.text, bg="#111827", fg="#F9FAFB", font=(FONT, 10),
                     padx=8, pady=4, justify="left").pack()
        except tk.TclError:
            self.tip = None

    def _hide(self, _=None):
        if self.job:
            try:
                self.w.after_cancel(self.job)
            except tk.TclError:
                pass
            self.job = None
        if self.tip:
            try:
                self.tip.destroy()
            except tk.TclError:
                pass
            self.tip = None


def hover(widgets, normal_bg, hover_bg, extra=None):
    """Highlight a group of widgets together when the mouse is over any of them."""
    def paint(c):
        for w in widgets:
            try:
                w.config(bg=c)
            except tk.TclError:
                pass
        if extra:
            extra(c == hover_bg)
    for w in widgets:
        w.bind("<Enter>", lambda e: paint(hover_bg), add="+")
        w.bind("<Leave>", lambda e: paint(normal_bg), add="+")


class Btn(tk.Frame):
    """Label-based button — colours render correctly on macOS.
    tip="..." shows a tooltip (use it for the keyboard shortcut)."""
    STYLES = {
        "primary": (ACCENT, "#FFFFFF", ACCENT_HV),
        "success": (SUCCESS, "#FFFFFF", SUCCESS_HV),
        "danger": (DANGER, "#FFFFFF", DANGER_HV),
        "export": (EXPORT_BG, "#FFFFFF", EXPORT_HV),
        "warning": (WARN_BORD, "#FFFFFF", WARN_HV),
        "ghost": ("#FFFFFF", "#374151", "#E5E7EB"),
        "outline": ("#FFFFFF", ACCENT, "#EEF2FF"),
    }

    def __init__(self, parent, text="", command=None, style="primary", small=False, tip=None, **kw):
        bg, fg, hv = self.STYLES.get(style, self.STYLES["primary"])
        bd = BORDER if style in ("ghost", "outline") else bg
        super().__init__(parent, bg=bg, highlightbackground=bd, highlightthickness=1,
                         cursor="hand2", **kw)
        self._bg, self._hv, self._bd = bg, hv, bd
        self._cmd = command
        self._pady = 3 if small else 7
        self._lbl = tk.Label(self, text=text, bg=bg, fg=fg, cursor="hand2",
                             font=(FONT, 10 if small else 11, "bold"),
                             padx=8 if small else 14, pady=self._pady)
        self._lbl.pack(pady=(0, 1))
        for w in (self, self._lbl):
            w.bind("<Enter>", lambda e: self._paint(self._hv))
            w.bind("<Leave>", lambda e: self._paint(self._bg))
            w.bind("<ButtonPress-1>", lambda e: self._press(True))
            w.bind("<ButtonRelease-1>", self._release)
        if tip:
            Tooltip(self._lbl, tip)

    def _press(self, down):
        # nudge the text 1px down while pressed (pack padding: works the same on Windows, Mac, Linux)
        try:
            self._lbl.pack_configure(pady=(1, 0) if down else (0, 1))
        except tk.TclError:
            pass

    def _release(self, e):
        try:
            self._press(False)
        except tk.TclError:
            return
        # only fire if released over the button (lets you cancel by dragging away)
        x, y = e.x_root, e.y_root
        if self.winfo_rootx() <= x <= self.winfo_rootx() + self.winfo_width() and \
                self.winfo_rooty() <= y <= self.winfo_rooty() + self.winfo_height():
            self.invoke()

    def invoke(self):
        if self._cmd:
            self._cmd()

    def mark_default(self):
        """Thicker ring = the button Enter presses."""
        tk.Frame.config(self, highlightthickness=2, highlightbackground="#1E1B4B")
        return self

    def _paint(self, c):
        try:
            tk.Frame.config(self, bg=c)
            self._lbl.config(bg=c)
        except tk.TclError:
            pass


class Inp(tk.Entry):
    def __init__(self, parent, width=10, **kw):
        kw.setdefault("font", (FONT, 11))
        super().__init__(parent, bg="#FFFFFF", fg=FG, insertbackground=FG, relief="flat",
                         bd=0, highlightthickness=1, highlightbackground=BORDER,
                         highlightcolor=BORDER_FOCUS, width=width, **kw)

    def set(self, v):
        self.delete(0, "end")
        self.insert(0, "" if v is None else str(v))


class Card(tk.Frame):
    def __init__(self, parent, bg=BG_CARD, **kw):
        kw.setdefault("padx", 14)
        kw.setdefault("pady", 10)
        super().__init__(parent, bg=bg, highlightbackground=BORDER, highlightthickness=1, **kw)


def pill(parent, text, bg, fg="#FFFFFF", size=9):
    return tk.Label(parent, text=f" {text} ", bg=bg, fg=fg, font=(FONT, size, "bold"), padx=4, pady=1)


def dept_pill(parent, dept):
    return pill(parent, dept, FOH_BG if dept == "FOH" else BOH_BG)


def shift_pill(parent, shift, size=9):
    bg, fg = SHIFT_CLR.get(shift, ("#D1D5DB", "#374151"))
    return pill(parent, shift, bg, fg, size)


def section(parent, text, color=ACCENT, bg=BG_PAGE, sub=None):
    f = tk.Frame(parent, bg=bg)
    tk.Frame(f, bg=color, width=4).pack(side="left", fill="y", padx=(0, 10))
    tk.Label(f, text=text, bg=bg, fg=FG, font=(FONT, 15, "bold")).pack(side="left")
    if sub:
        tk.Label(f, text=sub, bg=bg, fg=FG_SEC, font=(FONT, 11)).pack(side="left", padx=10)
    return f


class Notice:
    def __init__(self, root):
        self.root = root
        self._lbl = None
        self._job = None

    def show(self, msg, ms=2600, bg=SUCCESS_BG, fg=SUCCESS_FG):
        if self._lbl:
            self._lbl.destroy()
        if self._job:
            self.root.after_cancel(self._job)
        self._lbl = tk.Label(self.root, text=f"  {msg}  ", bg=bg, fg=fg,
                             font=(FONT, 12, "bold"), padx=18, pady=8)
        self._lbl.place(relx=0.5, rely=0.0, anchor="n", y=58)
        self._lbl.lift()
        self._job = self.root.after(ms, self._hide)

    def warn(self, msg, ms=4000):
        self.show(msg, ms, WARN_BG, WARN_FG)

    def _hide(self):
        if self._lbl:
            self._lbl.destroy()
            self._lbl = None
        self._job = None


class Dialog(tk.Toplevel):
    """Modal dialog with a body frame and a button bar.
    Enter = the main button, Esc = cancel."""

    def __init__(self, parent, title, width=460, height=None):
        super().__init__(parent)
        self.withdraw()
        self.title(title)
        self.configure(bg=BG_PAGE)
        self.transient(parent)
        self.resizable(True, True)
        self.bar = tk.Frame(self, bg=BG_PAGE, padx=18, pady=12)
        self.bar.pack(fill="x", side="bottom")
        tk.Frame(self, bg=BORDER, height=1).pack(fill="x", side="bottom")
        self.body = tk.Frame(self, bg=BG_PAGE, padx=18, pady=14)
        self.body.pack(fill="both", expand=True)
        self._dw, self._dh = width, height
        self._primary = None
        try:
            self._prev_grab = parent.grab_current()
        except (tk.TclError, KeyError):
            self._prev_grab = None
        self.bind("<Escape>", lambda e: self.destroy())
        for k in ("<Return>", "<KP_Enter>"):
            self.bind(k, self._enter)
        self.bind(f"<{MOD}-Return>", self._enter)

    def destroy(self):
        prev = getattr(self, "_prev_grab", None)
        super().destroy()
        # give the grab back to the dialog underneath (dialog-on-dialog)
        if prev is not None:
            try:
                if prev.winfo_exists():
                    prev.grab_set()
                    prev.focus_set()
            except tk.TclError:
                pass

    def _enter(self, ev=None):
        if self._primary is None:
            return
        w = self.focus_get()
        if isinstance(w, tk.Text):
            return
        # let a field finish committing its value first
        self.after(1, self._primary.invoke)
        return "break"

    def buttons(self, primary_text, primary_cmd, style="success", cancel_text="Cancel"):
        """Standard right-aligned [Cancel] [Primary] — Primary is what Enter presses."""
        self._primary = Btn(self.bar, primary_text, primary_cmd, style,
                            tip="Enter").mark_default()
        self._primary.pack(side="right")
        if cancel_text:
            Btn(self.bar, cancel_text, self.destroy, "ghost", tip="Esc").pack(side="right", padx=8)
        return self._primary

    def show(self, focus=None):
        self.update_idletasks()
        w = self._dw
        h = self._dh or min(self.winfo_reqheight(), int(self.winfo_screenheight() * 0.85))
        px = self.master.winfo_rootx() + (self.master.winfo_width() - w) // 2
        py = self.master.winfo_rooty() + 40
        self.geometry(f"{w}x{h}+{max(px, 0)}+{max(py, 0)}")
        self.deiconify()
        try:
            self.grab_set()
        except tk.TclError:
            pass
        target = focus or self._first_field(self.body)
        (target or self).focus_set()

    def _first_field(self, w):
        for c in w.winfo_children():
            if isinstance(c, (tk.Entry, ttk.Combobox)):
                return c
            f = self._first_field(c)
            if f:
                return f
        return None

    def label(self, parent, text, **kw):
        return tk.Label(parent, text=text, bg=parent.cget("bg"), fg=FG_HDR,
                        font=(FONT, 11, "bold"), anchor="w", **kw)


# ═════════════════════════════════════════════════════════════════════════════
#  LAYOUT PIECES (sidebar redesign)
# ═════════════════════════════════════════════════════════════════════════════
BG_SIDE = "#16213A"
BG_SIDE_HV = "#22304F"
FG_SIDE = "#AAB4C8"


class PageHeader(tk.Frame):
    """Big title + subtitle on the left, `.actions` on the right."""

    def __init__(self, parent, title, sub=None):
        super().__init__(parent, bg=BG_PAGE, padx=28, pady=18)
        self.pack(fill="x")
        left = tk.Frame(self, bg=BG_PAGE)
        left.pack(side="left")
        tk.Label(left, text=title, bg=BG_PAGE, fg=FG, font=(FONT, 20, "bold")).pack(anchor="w")
        self.sub = tk.Label(left, text=sub or "", bg=BG_PAGE, fg=FG_SEC, font=(FONT, 11))
        if sub:
            self.sub.pack(anchor="w")
        self.actions = tk.Frame(self, bg=BG_PAGE)
        self.actions.pack(side="right")


class DateNav(tk.Frame):
    """◀  Sat, Sep 26  ▶  Today — used in page headers."""

    def __init__(self, parent, text, on_prev, on_next, on_today, tip_unit="day", pick=None):
        super().__init__(parent, bg="#FFFFFF", highlightbackground=BORDER, highlightthickness=1)
        for sym, cmd, tip in (("‹", on_prev, f"Previous {tip_unit}  ({MOD_SYM}←)"),):
            b = tk.Label(self, text=sym, bg="#FFFFFF", fg=FG_HDR, font=(FONT, 18), padx=10, cursor="hand2")
            b.pack(side="left")
            b.bind("<Button-1>", lambda e, c=cmd: c())
            Tooltip(b, tip)
            hover([b], "#FFFFFF", "#EEF2FF")
        lab = tk.Label(self, text=text + "  \u25BE" if pick else text, bg="#FFFFFF", fg=FG,
                       font=(FONT, 12, "bold"), padx=6, width=22 if pick else 20,
                       cursor="hand2" if pick else "")
        lab.pack(side="left", fill="y")
        if pick:
            cur, unit, cb = pick
            lab.bind("<Button-1>", lambda e: open_calendar(self, cur, unit, cb))
            Tooltip(lab, "Pick a week" if unit == "week" else "Pick a day")
            hover([lab], "#FFFFFF", "#EEF2FF")
        b = tk.Label(self, text="›", bg="#FFFFFF", fg=FG_HDR, font=(FONT, 18), padx=10, cursor="hand2")
        b.pack(side="left")
        b.bind("<Button-1>", lambda e: on_next())
        Tooltip(b, f"Next {tip_unit}  ({MOD_SYM}→)")
        hover([b], "#FFFFFF", "#EEF2FF")
        tk.Frame(self, bg=BORDER, width=1).pack(side="left", fill="y")
        t = tk.Label(self, text="Today", bg="#FFFFFF", fg=ACCENT, font=(FONT, 10, "bold"), padx=10, cursor="hand2")
        t.pack(side="left", fill="y")
        t.bind("<Button-1>", lambda e: on_today())
        Tooltip(t, f"{MOD_SYM}T")
        hover([t], "#FFFFFF", "#EEF2FF")


def open_calendar(anchor, current, unit, on_pick):
    """Open the calendar under anchor; if one is already open, just close it."""
    top = anchor.winfo_toplevel()
    old = getattr(top, "_cal_popup", None)
    if old is not None:
        old.close()
        return None
    return CalendarPopup(anchor, current, unit, on_pick)


class CalendarPopup(tk.Frame):
    """Month calendar drawn INSIDE the app window under a widget (no separate
    window / no grab - those freeze on macOS). unit="day": click a day.
    unit="week": rows highlight as whole weeks (Mon-Sun); a click picks that week."""

    def __init__(self, anchor, current, unit, on_pick):
        import calendar
        import time
        from datetime import date
        top = anchor.winfo_toplevel()
        super().__init__(top, bg=BORDER)
        self._cal, self._date, self._t0 = calendar, date, time.time()
        self.top = top
        self.cur, self.unit, self.on_pick = current, unit, on_pick
        self.y, self.m = current.year, current.month
        self.body = tk.Frame(self, bg="#FFFFFF", padx=10, pady=8)
        self.body.pack(padx=1, pady=1)
        self.render()
        self.update_idletasks()
        x = anchor.winfo_rootx() - top.winfo_rootx() + anchor.winfo_width() // 2 - self.winfo_reqwidth() // 2
        y = anchor.winfo_rooty() - top.winfo_rooty() + anchor.winfo_height() + 4
        x = max(4, min(x, top.winfo_width() - self.winfo_reqwidth() - 4))
        self.place(x=x, y=y)
        self.lift()
        top._cal_popup = self
        if not getattr(top, "_cal_hooked", False):      # one dispatcher per window, never unbound
            top._cal_hooked = True
            top.bind("<Button-1>", lambda e: CalendarPopup._root_click(top, e), add="+")
            top.bind("<Escape>", lambda e: CalendarPopup._root_close(top), add="+")

    @staticmethod
    def _root_click(top, e):
        p = getattr(top, "_cal_popup", None)
        if p is None or not p.winfo_exists():
            top._cal_popup = None
            return
        import time
        if time.time() - p._t0 < 0.25:
            return
        x, y = e.x_root, e.y_root
        if not (p.winfo_rootx() <= x < p.winfo_rootx() + p.winfo_width()
                and p.winfo_rooty() <= y < p.winfo_rooty() + p.winfo_height()):
            p.close()

    @staticmethod
    def _root_close(top):
        p = getattr(top, "_cal_popup", None)
        if p is not None:
            p.close()

    def close(self):
        if getattr(self.top, "_cal_popup", None) is self:
            self.top._cal_popup = None
        try:
            self.destroy()
        except tk.TclError:
            pass

    def _wheel(self, w):
        w.bind("<MouseWheel>", lambda e: (self.shift(-1 if e.delta > 0 else 1), "break")[1])
        w.bind("<Button-4>", lambda e: (self.shift(-1), "break")[1])
        w.bind("<Button-5>", lambda e: (self.shift(1), "break")[1])
        for c in w.winfo_children():
            self._wheel(c)

    def shift(self, n):
        m = self.m + n
        self.y, self.m = self.y + (m - 1) // 12, (m - 1) % 12 + 1
        self.render()

    def pick(self, d):
        self.close()
        self.on_pick(d)

    def render(self):
        from datetime import timedelta
        for w in self.body.winfo_children():
            w.destroy()
        date = self._date
        today = date.today()
        top = tk.Frame(self.body, bg="#FFFFFF")
        top.pack(fill="x", pady=(0, 6))
        for sym, n, side in (("\u2039", -1, "left"), ("\u203A", 1, "right")):
            b = tk.Label(top, text=sym, bg="#FFFFFF", fg=FG_HDR, font=(FONT, 18), padx=8, cursor="hand2")
            b.pack(side=side)
            b.bind("<Button-1>", lambda e, n=n: self.shift(n))
            hover([b], "#FFFFFF", "#EEF2FF")
        tk.Label(top, text=date(self.y, self.m, 1).strftime("%B %Y"), bg="#FFFFFF", fg=FG,
                 font=(FONT, 13, "bold")).pack(side="left", expand=True)
        g = tk.Frame(self.body, bg="#FFFFFF")
        g.pack()
        for i, d in enumerate(("Mo", "Tu", "We", "Th", "Fr", "Sa", "Su")):
            tk.Label(g, text=d, bg="#FFFFFF", fg=FG_SEC, font=(FONT, 9, "bold"), width=4).grid(row=0, column=i, pady=(0, 2))
        cur_mon = self.cur - timedelta(days=self.cur.weekday())
        weeks = self._cal.Calendar(firstweekday=0).monthdatescalendar(self.y, self.m)
        for r, wk in enumerate(weeks, start=1):
            in_week = self.unit == "week" and wk[0] == cur_mon
            cells = []
            for c, d in enumerate(wk):
                sel = (d == self.cur) if self.unit == "day" else in_week
                base = ACCENT if sel else ("#EEF2FF" if (self.unit == "day" and wk[0] == cur_mon) else "#FFFFFF")
                fg = "#FFFFFF" if sel else (FG if d.month == self.m else "#C0C4CC")
                l = tk.Label(g, text=str(d.day), bg=base, fg=fg, width=4, pady=5, cursor="hand2",
                             font=(FONT, 11, "bold" if d == today else "normal"))
                if d == today and not sel:
                    l.config(fg=ACCENT)
                l.grid(row=r, column=c, padx=0, pady=1, sticky="nsew")
                l._base, l._fg = base, l.cget("fg")
                l.bind("<Button-1>", lambda e, d=d: self.pick(d))
                cells.append(l)
            for l in cells:
                if self.unit == "week":
                    l.bind("<Enter>", lambda e, cs=cells: [x.config(bg=ACCENT if x._base == ACCENT else "#E0E7FF") for x in cs])
                    l.bind("<Leave>", lambda e, cs=cells: [x.config(bg=x._base) for x in cs])
                else:
                    l.bind("<Enter>", lambda e, x=l: x.config(bg=x._base if x._base == ACCENT else "#E0E7FF"))
                    l.bind("<Leave>", lambda e, x=l: x.config(bg=x._base))
        foot = tk.Frame(self.body, bg="#FFFFFF")
        foot.pack(fill="x", pady=(6, 0))
        t = tk.Label(foot, text="This week" if self.unit == "week" else "Today", bg="#FFFFFF", fg=ACCENT,
                     font=(FONT, 10, "bold"), cursor="hand2", pady=2)
        t.pack(side="left")
        t.bind("<Button-1>", lambda e: self.pick(today))
        tk.Label(foot, text="Esc to close", bg="#FFFFFF", fg=FG_SEC, font=(FONT, 9)).pack(side="right")
        self._wheel(self)


class Segmented(tk.Frame):
    """A row of tabs; one is active. badges: {option: text}."""

    def __init__(self, parent, options, current, on_change, badges=None, bg=BG_PAGE, colors=None, size=11):
        super().__init__(parent, bg=BORDER, padx=1, pady=1)
        badges = badges or {}
        colors = colors or {}
        for i, o in enumerate(options):
            on = o == current
            abg = colors.get(o, (ACCENT, "#FFFFFF"))[0] if on else "#FFFFFF"
            afg = colors.get(o, (ACCENT, "#FFFFFF"))[1] if on else FG_HDR
            f = tk.Frame(self, bg=abg, cursor="hand2")
            f.pack(side="left", padx=(0 if i == 0 else 1, 0))
            l = tk.Label(f, text=o, bg=abg, fg=afg, font=(FONT, size, "bold"), padx=14, pady=6, cursor="hand2")
            l.pack(side="left")
            parts = [f, l]
            if badges.get(o) not in (None, ""):
                bl = tk.Label(f, text=str(badges[o]), bg=abg, fg=afg if on else FG_SEC, font=(FONT, 9, "bold"),
                              padx=0, cursor="hand2")
                bl.pack(side="left", padx=(0, 10))
                parts.append(bl)
            for w in parts:
                w.bind("<Button-1>", lambda e, o=o: on_change(o))
            if not on:
                hover(parts, "#FFFFFF", "#EEF2FF")


class Drawer(tk.Frame):
    """Right-hand side panel for editing one thing without leaving the page."""

    def __init__(self, parent, width=340):
        super().__init__(parent, bg=BG_CARD, width=width, highlightbackground=BORDER, highlightthickness=1)
        self.pack_propagate(False)
        self._on_close = None

    @property
    def is_open(self):
        try:
            return bool(self.winfo_manager())
        except tk.TclError:
            return False

    def open(self, title, builder, sub=None, on_close=None):
        for w in self.winfo_children():
            w.destroy()
        self._on_close = on_close
        head = tk.Frame(self, bg=BG_CARD, padx=18, pady=14)
        head.pack(fill="x")
        x = tk.Label(head, text="✕", bg=BG_CARD, fg=FG_SEC, font=(FONT, 13), cursor="hand2")
        x.pack(side="right", anchor="n")
        x.bind("<Button-1>", lambda e: self.close())
        Tooltip(x, "Close  (Esc)")
        tk.Label(head, text=title, bg=BG_CARD, fg=FG, font=(FONT, 15, "bold"), anchor="w",
                 wraplength=280, justify="left").pack(anchor="w")
        if sub:
            tk.Label(head, text=sub, bg=BG_CARD, fg=FG_SEC, font=(FONT, 10), anchor="w",
                     wraplength=300, justify="left").pack(anchor="w", pady=(2, 0))
        tk.Frame(self, bg=BORDER, height=1).pack(fill="x")
        body = ScrollFrame(self, bg=BG_CARD)
        body.pack(fill="both", expand=True)
        inner = tk.Frame(body, bg=BG_CARD, padx=18, pady=12)
        inner.pack(fill="both", expand=True)
        builder(inner)
        if not self.winfo_manager():
            self.pack(side="right", fill="y", padx=(0, 20), pady=(0, 16))

    def close(self):
        if self.winfo_exists() and self.winfo_manager():
            self.focus_set()
            try:
                self.update()
            except tk.TclError:
                pass
            self.pack_forget()
            if self._on_close:
                self._on_close()


def field_label(parent, text, hint=None):
    f = tk.Frame(parent, bg=parent.cget("bg"))
    tk.Label(f, text=text, bg=parent.cget("bg"), fg=FG_HDR, font=(FONT, 10, "bold")).pack(side="left")
    if hint:
        tk.Label(f, text=hint, bg=parent.cget("bg"), fg=FG_SEC, font=(FONT, 9)).pack(side="left", padx=6)
    return f


def empty_state(parent, icon, text, btn_text=None, cmd=None, sub=None):
    f = tk.Frame(parent, bg=parent.cget("bg"), pady=50)
    f.pack(fill="x")
    tk.Label(f, text=icon, bg=f.cget("bg"), font=(FONT, 34)).pack()
    tk.Label(f, text=text, bg=f.cget("bg"), fg=FG, font=(FONT, 14, "bold")).pack(pady=(6, 2))
    if sub:
        tk.Label(f, text=sub, bg=f.cget("bg"), fg=FG_SEC, font=(FONT, 11), wraplength=520).pack()
    if btn_text:
        Btn(f, btn_text, cmd).pack(pady=14)
    return f


class MenuBtn(Btn):
    """A button that opens a small menu of (label, command) choices."""

    def __init__(self, parent, text, items, style="primary", **kw):
        super().__init__(parent, text + "  ▾", self._popup, style, **kw)
        self._items = items

    def _popup(self):
        m = tk.Menu(self, tearoff=0, font=(FONT, 12))
        for it in self._items:
            if it is None:
                m.add_separator()
            else:
                lbl, cmd = it
                m.add_command(label=lbl, command=cmd)
        try:
            m.tk_popup(self.winfo_rootx(), self.winfo_rooty() + self.winfo_height() + 2)
        finally:
            m.grab_release()


def stat_card(parent, title, big, sub="", color=FG, on_click=None, action=None):
    """Home page card: small title, big number/text, a line of detail, optional button."""
    c = tk.Frame(parent, bg=BG_CARD, highlightbackground=BORDER, highlightthickness=1, padx=18, pady=14,
                 cursor="hand2" if on_click else "")
    t = tk.Label(c, text=title.upper(), bg=BG_CARD, fg=FG_SEC, font=(FONT, 9, "bold"), anchor="w")
    t.pack(anchor="w")
    b = tk.Label(c, text=big, bg=BG_CARD, fg=color, font=(FONT, 22, "bold"), anchor="w", justify="left")
    b.pack(anchor="w", pady=(4, 0))
    s = tk.Label(c, text=sub, bg=BG_CARD, fg=FG_SEC, font=(FONT, 10), anchor="w", justify="left", wraplength=260)
    s.pack(anchor="w", pady=(2, 0))
    if action:
        Btn(c, action[0], action[1], "outline", small=True).pack(anchor="w", pady=(10, 0))
    if on_click:
        parts = [c, t, b, s]
        for w in parts:
            w.bind("<Button-1>", lambda e: on_click())
        hover(parts, BG_CARD, "#F5F7FF")
    return c


class SearchBox(tk.Frame):
    """🔎 [ type to search… ✕ ]  — calls on_change(text) as you type.
    Esc clears it. The page's App.focus_search() (⌘F) jumps here."""

    def __init__(self, parent, on_change, placeholder="Search", width=26, value=""):
        super().__init__(parent, bg="#FFFFFF", highlightbackground=BORDER, highlightthickness=1)
        tk.Label(self, text="\U0001F50E", bg="#FFFFFF", fg=FG_SEC, font=(FONT, 11)).pack(side="left", padx=(8, 2))
        self.entry = tk.Entry(self, width=width, font=(FONT, 12), relief="flat", bd=0, bg="#FFFFFF", fg=FG,
                              insertbackground=FG, highlightthickness=0)
        self.entry.pack(side="left", ipady=5, padx=(2, 4))
        self.clear_btn = tk.Label(self, text="✕", bg="#FFFFFF", fg=FG_SEC, font=(FONT, 10), cursor="hand2")
        self.clear_btn.bind("<Button-1>", lambda e: self.clear())
        self._ph = placeholder
        self._cb = on_change
        self._showing_ph = False
        if value:
            self.entry.insert(0, value)
            self.clear_btn.pack(side="right", padx=(0, 8))
        else:
            self._show_ph()
        self.entry.bind("<FocusIn>", self._focus_in, add="+")
        self.entry.bind("<FocusOut>", lambda e: self._show_ph() if not self.get() else None, add="+")
        self.entry.bind("<KeyRelease>", self._changed)
        self.entry.bind("<Escape>", lambda e: (self.clear(), "break")[1] if self.get() else None)
        self.bind("<Button-1>", lambda e: self.entry.focus_set())
        Tooltip(self.entry, f"{placeholder}  ({MOD_SYM}F)")

    def _show_ph(self):
        if not self.entry.get():
            self._showing_ph = True
            self.entry.insert(0, self._ph)
            self.entry.config(fg="#9CA3AF")

    def _focus_in(self, _=None):
        if self._showing_ph:
            self.entry.delete(0, "end")
            self.entry.config(fg=FG)
            self._showing_ph = False

    def get(self):
        return "" if self._showing_ph else self.entry.get().strip()

    def _changed(self, ev=None):
        if ev is not None and ev.keysym in ("Escape", "Return", "KP_Enter", "Tab"):
            return
        if self.get():
            if not self.clear_btn.winfo_manager():
                self.clear_btn.pack(side="right", padx=(0, 8))
        else:
            self.clear_btn.pack_forget()
        self._cb(self.get().lower())

    def clear(self):
        self._focus_in()
        self.entry.delete(0, "end")
        self.clear_btn.pack_forget()
        self._cb("")

    def focus(self):
        self.entry.focus_set()
        self._focus_in()
        self.entry.select_range(0, "end")


def matches(query: str, *texts) -> bool:
    """Every word of the query appears somewhere in the texts (case-insensitive)."""
    if not query:
        return True
    hay = " ".join(t for t in texts if t).lower()
    return all(w in hay for w in query.lower().split())

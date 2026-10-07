"""Inventory — Order (pick items + how many), My cart, Items, Order History. No links."""

from __future__ import annotations

import csv
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import date

import inventory as invm
from core import to_float
from ui import *  # noqa: F401,F403

UNITS = ["each", "case", "box", "pack", "bag", "bottle", "gallon", "lb", "roll", "sleeve", "dozen"]
OTHER = "Other"
ALL = "All items"


def fmt_qty(q):
    return f"{q:g}" if q else ""


class _InvBase:
    """Shared bits: data and the item dialogs."""

    def __init__(self, app, parent):
        self.app = app
        self.s = app.store
        self.parent = parent
        self.inv = invm.load(self.s)
        self.query = ""
        self.build()

    def save(self):
        invm.save(self.s, self.inv)

    def _items(self):
        return [i for i in self.inv["items"] if i.get("active", True)]

    def cat(self, it):
        return (it.get("category") or "").strip() or OTHER

    def _match(self, it):
        return matches(self.query, it.get("name", ""), it.get("category", ""), it.get("unit", ""),
                       it.get("notes", ""))

    def _groups(self, items):
        g = {}
        for it in items:
            g.setdefault(self.cat(it), []).append(it)
        for v in g.values():
            v.sort(key=lambda i: i["name"].lower())
        return g

    def _cat_order(self, names):
        return sorted(names, key=lambda k: (k == OTHER, k.lower()))

    def _categories(self):
        return sorted({i.get("category") for i in self.inv["items"] if i.get("category")}, key=str.lower)

    def _search(self, parent, on_change, width=26, placeholder="Search items"):
        def changed(q):
            self.query = q
            on_change()
        self.search_box = SearchBox(parent, changed, placeholder, width=width, value=self.query)
        return self.search_box

    def cart(self):
        return {k: v for k, v in self.inv["draft"]["qty"].items() if v}

    def add_new(self):
        self.item_dialog()

    # ── delete / right-click menu ───────────────────────────────────────────
    def delete_items(self, items):
        if not items:
            return False
        names = ", ".join(i["name"] for i in items[:5]) + (f" and {len(items) - 5} more" if len(items) > 5 else "")
        if not messagebox.askyesno("Delete", f"Delete {len(items)} item{'s' if len(items) > 1 else ''}?\n\n{names}"
                                   "\n\nPast orders keep their record.", parent=self.app):
            return False
        ids = {i["id"] for i in items}
        self.inv["items"] = [i for i in self.inv["items"] if i["id"] not in ids]
        for k in ids:
            self.inv["draft"]["qty"].pop(k, None)
        self.save()
        self.app.notice.show(f"Deleted {len(items)} item{'s' if len(items) > 1 else ''}")
        self.app.refresh_badges()
        return True

    def bind_menu(self, widgets, it):
        """Right-click (or Ctrl-click on a Mac) any of these widgets for Edit / Delete."""
        def popup(ev):
            m = tk.Menu(self.app, tearoff=0, font=(FONT, 12))
            m.add_command(label=f"Edit \u201c{it['name']}\u201d\u2026", command=lambda: self.item_dialog(it))
            m.add_command(label="Delete", command=lambda: self.delete_items([it]) and self.build())
            try:
                m.tk_popup(ev.x_root, ev.y_root)
            finally:
                m.grab_release()
            return "break"
        for w in widgets:
            for seq in ("<Button-3>", "<Button-2>" if IS_MAC else "<Button-3>", "<Control-Button-1>"):
                w.bind(seq, popup)

    # ── add / edit one item ─────────────────────────────────────────────────
    def item_dialog(self, it=None, keep=None):
        new = it is None
        it = it or invm.new_item(**(keep or {}))
        dlg = Dialog(self.app, "Add item" if new else it["name"], width=520)
        b = dlg.body
        b.columnconfigure(0, weight=1)
        field_label(b, "Name").grid(row=0, column=0, sticky="w")
        name = Inp(b, width=44, font=(FONT, 12))
        name.set(it.get("name", ""))
        name.grid(row=1, column=0, sticky="we", ipady=4, pady=(2, 12))
        row = tk.Frame(b, bg=BG_PAGE)
        row.grid(row=2, column=0, sticky="we")
        field_label(row, "Unit").grid(row=0, column=0, sticky="w", padx=(0, 16))
        unit = ttk.Combobox(row, values=UNITS, width=12)
        unit.set(it.get("unit", ""))
        unit.grid(row=1, column=0, sticky="w", padx=(0, 16), pady=(2, 12))
        field_label(row, "Category", "e.g. Bar, Kitchen, Cleaning").grid(row=0, column=1, sticky="w")
        cat = ttk.Combobox(row, values=self._categories(), width=22)
        cat.set(it.get("category", ""))
        cat.grid(row=1, column=1, sticky="w", pady=(2, 12))
        field_label(b, "Notes", "optional — brand, size, where you buy it").grid(row=3, column=0, sticky="w")
        notes = Inp(b, width=44)
        notes.set(it.get("notes", ""))
        notes.grid(row=4, column=0, sticky="we", ipady=4, pady=(2, 8))
        active = tk.BooleanVar(value=it.get("active", True))
        tk.Checkbutton(b, text="Show in the order list", variable=active, bg=BG_PAGE,
                       font=(FONT, 10)).grid(row=5, column=0, sticky="w")

        def collect():
            nm = " ".join(name.get().split())
            if not nm:
                messagebox.showwarning("Name", "Give the item a name.", parent=dlg)
                return False
            if new and any(i["name"].lower() == nm.lower() for i in self.inv["items"]):
                if not messagebox.askyesno("Already there", f"“{nm}” is already an item. Add it again?",
                                           parent=dlg):
                    return False
            it.update({"name": nm, "unit": unit.get().strip(), "category": cat.get().strip(),
                       "notes": notes.get().strip(), "active": active.get()})
            if new:
                self.inv["items"].append(it)
            self.save()
            return True

        def save():
            if collect():
                dlg.destroy()
                self.app.notice.show(f"Saved {it['name']}")
                self.build()

        def save_another():
            if collect():
                k = {"unit": it["unit"], "category": it["category"]}
                dlg.destroy()
                self.build()
                self.item_dialog(keep=k)
                self.app.notice.show(f"Saved {it['name']} — next one")

        def delete():
            if messagebox.askyesno("Delete item", f"Delete {it['name']}?\n\nPast orders keep their record.",
                                   parent=dlg):
                self.inv["items"].remove(it)
                self.inv["draft"]["qty"].pop(it["id"], None)
                self.save()
                dlg.destroy()
                self.build()

        dlg.buttons("Save", save)
        if new:
            Btn(dlg.bar, "Save & add another", save_another, "outline",
                tip="Saves and opens a fresh form (keeps unit and category)").pack(side="left")
        else:
            Btn(dlg.bar, "Delete", delete, "ghost", small=True).pack(side="left")
        dlg.show(focus=name)

    def bulk_dialog(self):
        dlg = Dialog(self.app, "Add many items", width=620, height=520)
        tk.Label(dlg.body, text="One item per line. Add the unit after a comma if you like:  Paper towels, case",
                 bg=BG_PAGE, fg=FG_SEC, font=(FONT, 10)).pack(anchor="w", pady=(0, 6))
        txt = tk.Text(dlg.body, height=14, font=(FONT, 12), relief="flat", highlightthickness=1,
                      highlightbackground=BORDER, highlightcolor=BORDER_FOCUS, wrap="none")
        txt.pack(fill="both", expand=True)
        opts = tk.Frame(dlg.body, bg=BG_PAGE)
        opts.pack(fill="x", pady=(8, 0))
        tk.Label(opts, text="Category for all (optional)", bg=BG_PAGE, fg=FG_HDR).pack(side="left")
        cat = ttk.Combobox(opts, values=self._categories(), width=20)
        cat.pack(side="left", padx=8)
        prev = tk.Label(dlg.body, text="", bg=BG_PAGE, fg=FG_SEC, font=(FONT, 10), anchor="w")
        prev.pack(fill="x", pady=(6, 0))

        def parse():
            out = []
            for line in txt.get("1.0", "end").splitlines():
                line = line.strip(" -•\t")
                if not line:
                    continue
                nm, _, un = line.partition(",")
                out.append(invm.new_item(name=" ".join(nm.split()), unit=un.strip(), category=cat.get().strip()))
            return out
        txt.bind("<KeyRelease>", lambda e: prev.config(text=f"{len(parse())} items" if parse() else ""))

        def add():
            items = [i for i in parse() if i["name"]]
            if not items:
                return
            self.inv["items"].extend(items)
            self.save()
            dlg.destroy()
            self.build()
            self.app.notice.show(f"Added {len(items)} items")

        dlg.buttons("Add items", add)
        dlg.show(focus=txt)


# ═════════════════════════════════════════════════════════════════════════════
#  ORDER  (pick items + how many)   and   MY CART
# ═════════════════════════════════════════════════════════════════════════════
class OrderPage(_InvBase):
    def build(self):
        for w in self.parent.winfo_children():
            w.destroy()
        self.recs = {i["id"]: invm.recommend(self.inv, i) for i in self._items()}
        self.mode = getattr(self.app, "_order_mode", "shop")
        if self.mode == "cart":
            self.build_cart()
        else:
            self.build_shop()

    def set_mode(self, m):
        self.app._commit_focus()
        self.app._order_mode = m
        self.build()

    # ── shopping: pick a category, type how many ───────────────────────────
    def build_shop(self):
        h = PageHeader(self.parent, "Order", "")
        self.head_sub = h.sub
        h.sub.pack(anchor="w")
        self.cart_btn = Btn(h.actions, "", lambda: self.set_mode("cart"), "success",
                            tip="See everything you've added")
        self.cart_btn.pack(side="right")
        MenuBtn(h.actions, "More", [("✨ Fill in all suggestions", self.use_suggestions),
                                    ("Empty the cart", self.clear_draft), None,
                                    ("+ Add a new item…", self.item_dialog)], "ghost").pack(side="right", padx=8)
        if not self.inv["items"]:
            empty_state(self.parent, "\U0001F6D2", "No items yet", "+ Add your first item", self.item_dialog,
                        sub="Add the things you order (name, unit, category). Then come here, type how many "
                            "you need, and press Show my cart.")
            self._update_summary()
            return
        sbar = tk.Frame(self.parent, bg=BG_PAGE, padx=28)
        sbar.pack(fill="x", pady=(0, 12))
        self._search(sbar, lambda: (self.render_list(), self.sf.to_top()), width=34,
                     placeholder="Search all items").pack(side="left")
        body = tk.Frame(self.parent, bg=BG_PAGE)
        body.pack(fill="both", expand=True, padx=28, pady=(0, 16))
        self.cats_col = tk.Frame(body, bg=BG_PAGE, width=220)
        self.cats_col.pack(side="left", fill="y")
        self.cats_col.pack_propagate(False)
        right = tk.Frame(body, bg=BG_PAGE)
        right.pack(side="left", fill="both", expand=True, padx=(16, 0))
        self.list_head = tk.Frame(right, bg=BG_PAGE)
        self.list_head.pack(fill="x", pady=(0, 8))
        self.sf = ScrollFrame(right)
        self.sf.pack(fill="both", expand=True)
        groups = self._groups(self._items())
        sel = getattr(self.app, "_order_cat", None)
        if sel not in groups and sel != ALL:
            sel = ALL
        self.catsel = sel
        self.render_cats()
        self.render_list()
        self._update_summary()

    def render_cats(self):
        for w in self.cats_col.winfo_children():
            w.destroy()
        groups = self._groups(self._items())
        cart = self.cart()
        tk.Label(self.cats_col, text="CATEGORIES", bg=BG_PAGE, fg=FG_SEC, font=(FONT, 9, "bold")).pack(anchor="w", pady=(0, 6))
        for name in [ALL] + self._cat_order(groups):
            items = self._items() if name == ALL else groups[name]
            n_cart = len([i for i in items if cart.get(i["id"])])
            on = name == self.catsel and not self.query
            bg = "#FFFFFF" if on else BG_PAGE
            r = tk.Frame(self.cats_col, bg=bg, cursor="hand2", highlightbackground=ACCENT if on else BG_PAGE,
                         highlightthickness=1)
            r.pack(fill="x", pady=2)
            n = tk.Label(r, text=name, bg=bg, fg=FG, font=(FONT, 11, "bold" if on else "normal"), anchor="w",
                         padx=12, pady=8, cursor="hand2")
            n.pack(side="left")
            parts = [r, n]
            c = tk.Label(r, text=f" {n_cart} " if n_cart else f"{len(items)}", bg=ACCENT if n_cart else bg,
                         fg="#FFFFFF" if n_cart else FG_SEC, font=(FONT, 9, "bold"), cursor="hand2")
            c.pack(side="right", padx=8)
            Tooltip(c, f"{n_cart} in your cart" if n_cart else f"{len(items)} items")
            if not n_cart:
                parts.append(c)
            for w in (r, n, c):
                w.bind("<Button-1>", lambda e, name=name: self.pick_cat(name))
            if not on:
                hover(parts, BG_PAGE, "#E8ECF4")

    def pick_cat(self, name):
        self.app._commit_focus()
        if self.query:
            self.query = ""
            self.search_box.clear()
        self.catsel = name
        self.app._order_cat = name
        self.render_cats()
        self.render_list()
        self.sf.to_top()

    def render_list(self):
        for w in self.list_head.winfo_children():
            w.destroy()
        for w in self.sf.winfo_children():
            w.destroy()
        if self.query:
            items = [i for i in self._items() if self._match(i)]
            title = f"{len(items)} match{'es' if len(items) != 1 else ''} for “{self.query}”"
        elif self.catsel == ALL:
            items = self._items()
            title = ALL
        else:
            items = self._groups(self._items()).get(self.catsel, [])
            title = self.catsel
        many = self.catsel == ALL or bool(self.query)
        items.sort(key=lambda i: ((self.cat(i).lower() if many else ""), i["name"].lower()))
        tk.Label(self.list_head, text=title, bg=BG_PAGE, fg=FG, font=(FONT, 16, "bold")).pack(side="left")
        sugg = [i for i in items if (self.recs.get(i["id"]) or {}).get("due") and not self.cart().get(i["id"])]
        if sugg:
            Btn(self.list_head, f"✨ Fill {len(sugg)} suggestion{'s' if len(sugg) > 1 else ''}",
                lambda s=sugg: self.fill(s), "outline", small=True,
                tip="Fill in what past orders suggest for these items").pack(side="right")
        card = Card(self.sf, padx=0, pady=0)
        card.pack(fill="x")
        g = tk.Frame(card, bg=BG_CARD, padx=12, pady=8)
        g.pack(fill="x")
        g.columnconfigure(0, weight=1)
        for c, t in enumerate(["Item", "Suggested", "How many"]):
            tk.Label(g, text=t, bg=BG_CARD, fg=FG_SEC, font=(FONT, 9, "bold")).grid(row=0, column=c, sticky="w",
                                                                                   padx=8, pady=(0, 4))
        self.qty_fields = []
        self.row_bgs = {}
        cart = self.cart()
        last_cat = None
        r = 1
        for it in items:
            if many and self.cat(it) != last_cat:
                last_cat = self.cat(it)
                tk.Label(g, text=last_cat.upper(), bg=BG_CARD, fg=FG_SEC, font=(FONT, 9, "bold")).grid(
                    row=r, column=0, sticky="w", padx=8, pady=(8, 2))
                r += 1
            self._item_row(g, r, it, cart.get(it["id"], 0))
            r += 1
        if not items:
            tk.Label(g, text="Nothing matches." if self.query else "No items here.", bg=BG_CARD, fg=FG_SEC,
                     font=(FONT, 11), pady=16).grid(row=1, column=0, columnspan=3)

    def _item_row(self, g, r, it, q0):
        nf = tk.Frame(g, bg=BG_CARD)
        nf.grid(row=r, column=0, sticky="we", padx=8, pady=3)
        nl = tk.Label(nf, text=it["name"], bg=BG_CARD, fg=FG, font=(FONT, 12, "bold"), anchor="w", cursor="hand2")
        nl.pack(anchor="w")
        hist = invm.item_history(self.inv, it["id"])
        bits = [x for x in (it.get("unit"), it.get("notes")) if x]
        bits.append(f"last ordered {hist[-1][0]:%b %d} ({hist[-1][1]:g})" if hist else "never ordered")
        tk.Label(nf, text="  ·  ".join(bits), bg=BG_CARD, fg=FG_SEC, font=(FONT, 9), anchor="w").pack(anchor="w")
        nl.bind("<Double-Button-1>", lambda e: self.item_dialog(it))
        Tooltip(nl, "Double-click to edit  \u00b7  right-click to edit or delete")
        self.bind_menu([nf, nl], it)
        rec = self.recs.get(it["id"])
        step = tk.Frame(g, bg=BG_CARD)
        q = Inp(step, width=5, justify="center", font=(FONT, 13, "bold"))
        if rec and rec["qty"] > 0:
            sl = tk.Label(g, text=f"✨ {rec['qty']:g}", bg="#EEF2FF" if rec["due"] else BG_CARD, fg=ACCENT,
                          font=(FONT, 11, "bold"), padx=8, pady=2, cursor="hand2")
            Tooltip(sl, rec["why"] + "\nClick to use it.")
            sl.bind("<Button-1>", lambda e, n=rec["qty"]: (q.set(fmt_qty(n)), self.commit_qty(it, q)))
        else:
            sl = tk.Label(g, text="—", bg=BG_CARD, fg="#D1D5DB", font=(FONT, 11), padx=8)
        sl.grid(row=r, column=1, sticky="w", padx=8)
        step.grid(row=r, column=2, padx=8, pady=3)
        minus = tk.Label(step, text="−", bg="#F3F4F6", fg=FG, font=(FONT, 14, "bold"), width=2, cursor="hand2")
        minus.pack(side="left")
        q.set(fmt_qty(q0))
        q.pack(side="left", ipady=3, padx=2)
        plus = tk.Label(step, text="+", bg="#F3F4F6", fg=FG, font=(FONT, 14, "bold"), width=2, cursor="hand2")
        plus.pack(side="left")
        minus.bind("<Button-1>", lambda e: self.bump(it, q, -1))
        plus.bind("<Button-1>", lambda e: self.bump(it, q, +1))
        hover([minus], "#F3F4F6", "#E0E7FF")
        hover([plus], "#F3F4F6", "#E0E7FF")
        q.bind("<FocusOut>", lambda e: self.commit_qty(it, q))
        for k, d in (("<Return>", 1), ("<KP_Enter>", 1), ("<Down>", 1), ("<Up>", -1)):
            q.bind(k, lambda e, d=d: self.move(it, q, d))
        q.bind("<plus>", lambda e: (self.bump(it, q, +1), "break")[1])
        q.bind("<minus>", lambda e: (self.bump(it, q, -1), "break")[1])
        self.qty_fields.append(q)
        self._paint_qty(q, q0)

    def _paint_qty(self, q, v):
        q.config(bg="#ECFDF5" if v else "#FFFFFF", highlightbackground=SUCCESS if v else BORDER)

    def bump(self, it, q, d):
        cur = to_float(q.get(), 0) or 0
        q.set(fmt_qty(max(0, cur + d)))
        self.commit_qty(it, q)

    def move(self, it, q, d):
        self.commit_qty(it, q)
        try:
            i = self.qty_fields.index(q) + d
        except ValueError:
            return "break"
        if 0 <= i < len(self.qty_fields):
            nxt = self.qty_fields[i]
            nxt.focus_set()
            self.sf.scroll_into_view(nxt)
        return "break"

    def commit_qty(self, it, q):
        raw = q.get().strip()
        v = to_float(raw, None) if raw else 0.0
        if raw and v is None:
            self.app.notice.warn("How many must be a number")
            q.set(fmt_qty(self.inv["draft"]["qty"].get(it["id"], 0)))
            return
        v = max(0.0, v or 0.0)
        if v != self.inv["draft"]["qty"].get(it["id"], 0):
            if v:
                self.inv["draft"]["qty"][it["id"]] = v
            else:
                self.inv["draft"]["qty"].pop(it["id"], None)
            self.save()
            if getattr(self, "cats_col", None) and self.cats_col.winfo_exists():
                self.render_cats()
            self._update_summary()
            self.app.refresh_badges()
        q.set(fmt_qty(v))
        self._paint_qty(q, v)

    def fill(self, items):
        for it in items:
            r = self.recs.get(it["id"])
            if r and r["qty"]:
                self.inv["draft"]["qty"][it["id"]] = r["qty"]
        self.save()
        self.render_cats()
        self.render_list()
        self._update_summary()
        self.app.refresh_badges()

    def _update_summary(self):
        n = len(self.cart())
        if getattr(self, "head_sub", None) and self.head_sub.winfo_exists():
            self.head_sub.config(text=f"{n} item{'s' if n != 1 else ''} in your cart" if n else
                                 "Type how many you need — ✨ shows what past orders suggest")
        if getattr(self, "cart_btn", None) and self.cart_btn.winfo_exists():
            self.cart_btn._lbl.config(text=f"\U0001F6D2  Show my cart  ({n})")

    def use_suggestions(self):
        n = 0
        for it in self._items():
            r = self.recs.get(it["id"])
            if r and r["due"] and not self.inv["draft"]["qty"].get(it["id"]):
                self.inv["draft"]["qty"][it["id"]] = r["qty"]
                n += 1
        self.save()
        self.build()
        if n:
            self.app.notice.show(f"Added {n} suggested item{'s' if n > 1 else ''} to your cart")
        else:
            self.app.notice.warn("No suggestions right now (items need at least 2 past orders)")

    def clear_draft(self):
        if self.cart() and not messagebox.askyesno("Empty the cart", "Remove everything from your cart?",
                                                   parent=self.app):
            return
        self.inv["draft"] = {"qty": {}, "done": []}
        self.save()
        self.build()

    # ── my cart ─────────────────────────────────────────────────────────────
    def build_cart(self):
        cart = self.cart()
        items = {i["id"]: i for i in self.inv["items"]}
        lines = [(items[k], v) for k, v in cart.items() if k in items]
        h = PageHeader(self.parent, "My cart", f"{len(lines)} item{'s' if len(lines) != 1 else ''}"
                       if lines else "Empty")
        Btn(h.actions, "✓ Mark as ordered", self.mark_ordered, "success",
            tip="Save this order to History and empty the cart").pack(side="right")
        MenuBtn(h.actions, "Share", [("Copy the list", self.copy_list),
                                     ("Save the list as CSV…", self.save_list),
                                     None, ("Empty the cart", self.clear_draft)], "ghost").pack(side="right", padx=8)
        Btn(h.actions, "← Keep adding", lambda: self.set_mode("shop"), "outline",
            tip="Back to the item list").pack(side="right")
        self.sf = ScrollFrame(self.parent)
        self.sf.pack(fill="both", expand=True, padx=28, pady=(0, 16))
        if not lines:
            empty_state(self.sf, "\U0001F6D2", "Your cart is empty", "← Add items",
                        lambda: self.set_mode("shop"), sub="Go back and type how many you need of each item.")
            return
        groups = {}
        for it, v in lines:
            groups.setdefault(self.cat(it), []).append((it, v))
        self.qty_fields = []
        for c in self._cat_order(groups):
            tk.Label(self.sf, text=c, bg=BG_PAGE, fg=FG, font=(FONT, 12, "bold")).pack(anchor="w", pady=(10, 4))
            card = Card(self.sf, padx=0, pady=0)
            card.pack(fill="x")
            g = tk.Frame(card, bg=BG_CARD, padx=12, pady=6)
            g.pack(fill="x")
            g.columnconfigure(0, weight=1)
            for r, (it, v) in enumerate(sorted(groups[c], key=lambda x: x[0]["name"].lower())):
                nm = tk.Label(g, text=it["name"], bg=BG_CARD, fg=FG, font=(FONT, 12, "bold"), anchor="w")
                nm.grid(row=r, column=0, sticky="w", padx=8, pady=5)
                step = tk.Frame(g, bg=BG_CARD)
                step.grid(row=r, column=1, padx=8)
                q = Inp(step, width=5, justify="center", font=(FONT, 13, "bold"))
                minus = tk.Label(step, text="−", bg="#F3F4F6", fg=FG, font=(FONT, 14, "bold"), width=2,
                                 cursor="hand2")
                minus.pack(side="left")
                q.set(fmt_qty(v))
                q.pack(side="left", ipady=3, padx=2)
                plus = tk.Label(step, text="+", bg="#F3F4F6", fg=FG, font=(FONT, 14, "bold"), width=2, cursor="hand2")
                plus.pack(side="left")
                tk.Label(g, text=it.get("unit", ""), bg=BG_CARD, fg=FG_SEC, font=(FONT, 10), width=8,
                         anchor="w").grid(row=r, column=2, sticky="w")
                x = tk.Label(g, text="✕", bg=BG_CARD, fg=DANGER, font=(FONT, 12, "bold"), cursor="hand2", padx=6)
                x.grid(row=r, column=3, padx=(4, 4))
                Tooltip(x, "Remove from cart")
                minus.bind("<Button-1>", lambda e, it=it, q=q: self.bump_cart(it, q, -1))
                plus.bind("<Button-1>", lambda e, it=it, q=q: self.bump_cart(it, q, +1))
                x.bind("<Button-1>", lambda e, it=it: self.remove(it))
                q.bind("<FocusOut>", lambda e, it=it, q=q: self.commit_cart(it, q))
                for k, d in (("<Return>", 1), ("<KP_Enter>", 1), ("<Down>", 1), ("<Up>", -1)):
                    q.bind(k, lambda e, it=it, q=q, d=d: self.move_cart(it, q, d))
                self.qty_fields.append(q)

    def bump_cart(self, it, q, d):
        cur = to_float(q.get(), 0) or 0
        new = max(0, cur + d)
        if new == 0:
            self.remove(it)
            return
        q.set(fmt_qty(new))
        self.commit_cart(it, q)

    def commit_cart(self, it, q):
        v = to_float(q.get().strip(), None)
        if v is None or v <= 0:
            q.set(fmt_qty(self.inv["draft"]["qty"].get(it["id"], 0)))
            return
        if v != self.inv["draft"]["qty"].get(it["id"]):
            self.inv["draft"]["qty"][it["id"]] = v
            self.save()

    def move_cart(self, it, q, d):
        self.commit_cart(it, q)
        i = self.qty_fields.index(q) + d
        if 0 <= i < len(self.qty_fields):
            self.qty_fields[i].focus_set()
            self.sf.scroll_into_view(self.qty_fields[i])
        return "break"

    def remove(self, it):
        self.inv["draft"]["qty"].pop(it["id"], None)
        self.save()
        keep = self.sf.position()
        self.build()
        self.sf.restore(keep)
        self.app.notice.show(f"Removed {it['name']}")
        self.app.refresh_badges()

    def _cart_lines(self):
        items = {i["id"]: i for i in self.inv["items"]}
        lines = [(items[k], v) for k, v in self.cart().items() if k in items]
        return sorted(lines, key=lambda x: (self.cat(x[0]) == OTHER, self.cat(x[0]).lower(), x[0]["name"].lower()))

    def copy_list(self):
        self.app._commit_focus()
        out, cur = [], None
        for it, v in self._cart_lines():
            if self.cat(it) != cur:
                cur = self.cat(it)
                out.append(("" if not out else "\n") + cur.upper())
            out.append(f"{v:g} {it.get('unit') or ''}  {it['name']}".replace("  ", " ").strip())
        self.app.clipboard_clear()
        self.app.clipboard_append(f"Order {date.today():%b %d}\n\n" + "\n".join(out))
        self.app.notice.show("List copied — paste it in a text, email or notes")

    def save_list(self):
        self.app._commit_focus()
        p = filedialog.asksaveasfilename(parent=self.app, defaultextension=".csv",
                                         initialfile=f"order_{date.today().isoformat()}.csv",
                                         filetypes=[("CSV", "*.csv")])
        if not p:
            return
        with open(p, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["Category", "Item", "How many", "Unit", "Notes"])
            for it, v in self._cart_lines():
                w.writerow([self.cat(it), it["name"], f"{v:g}", it.get("unit", ""), it.get("notes", "")])
        self.app.notice.show("List saved")

    def mark_ordered(self):
        self.app._commit_focus()
        lines = [{"item_id": it["id"], "name": it["name"], "unit": it.get("unit", ""),
                  "category": self.cat(it), "qty": v} for it, v in self._cart_lines()]
        if not lines:
            self.app.notice.warn("Your cart is empty")
            return
        if not messagebox.askyesno("Mark as ordered", f"Save this order ({len(lines)} items) to History "
                                                      "and empty the cart?", parent=self.app):
            return
        self.inv["orders"].append({"id": invm.gen_id(), "date": date.today().isoformat(), "lines": lines})
        self.inv["draft"] = {"qty": {}, "done": []}
        self.save()
        self.app._order_mode = "shop"
        self.app.notice.show("Order saved — suggestions will learn from it")
        self.build()
        self.app.refresh_badges()


# ═════════════════════════════════════════════════════════════════════════════
#  ITEMS
# ═════════════════════════════════════════════════════════════════════════════
class ItemsPage(_InvBase):
    def build(self):
        for w in self.parent.winfo_children():
            w.destroy()
        self.selecting = getattr(self, "selecting", False)
        self.selected = getattr(self, "selected", set()) if self.selecting else set()
        n = len(self.inv["items"])
        h = PageHeader(self.parent, "Items", f"{n} item{'s' if n != 1 else ''}" if n else "")
        Btn(h.actions, "+ Add item", self.item_dialog, tip=f"{MOD_SYM}N").pack(side="right")
        MenuBtn(h.actions, "More", [("Add many at once\u2026", self.bulk_dialog),
                                    ("Import items from a CSV file\u2026", self.import_csv)], "ghost").pack(side="right", padx=8)
        if n:
            Btn(h.actions, "Done" if self.selecting else "Select\u2026", self.toggle_select,
                "primary" if self.selecting else "ghost",
                tip="Pick several items to delete or move to another category").pack(side="right")
        if self.inv["items"]:
            bar = tk.Frame(self.parent, bg=BG_PAGE, padx=28)
            bar.pack(fill="x", pady=(0, 10))
            self._search(bar, lambda: (self.render(), self.sf.to_top()), width=34,
                         placeholder="Search items or categories").pack(side="left")
            if self.selecting:
                self.sel_bar = tk.Frame(bar, bg=BG_PAGE)
                self.sel_bar.pack(side="right")
        self.sf = ScrollFrame(self.parent)
        self.sf.pack(fill="both", expand=True, padx=28, pady=(0, 16))
        self.render()

    def toggle_select(self):
        self.selecting = not self.selecting
        self.selected = set()
        self.build()

    def paint_sel_bar(self):
        if not self.selecting or not getattr(self, "sel_bar", None):
            return
        for w in self.sel_bar.winfo_children():
            w.destroy()
        n = len(self.selected)
        tk.Label(self.sel_bar, text=f"{n} selected", bg=BG_PAGE, fg=FG_HDR, font=(FONT, 11, "bold")).pack(side="left", padx=8)
        Btn(self.sel_bar, "Select all shown", self.select_all, "ghost", small=True).pack(side="left", padx=2)
        if n:
            Btn(self.sel_bar, "Change category\u2026", self.move_selected, "outline", small=True).pack(side="left", padx=2)
            Btn(self.sel_bar, f"Delete {n}", self.delete_selected, "danger", small=True).pack(side="left", padx=2)

    def select_all(self):
        shown = [i["id"] for i in self.inv["items"] if self._match(i)]
        self.selected = set() if self.selected >= set(shown) else set(shown)
        self.render()

    def delete_selected(self):
        items = [i for i in self.inv["items"] if i["id"] in self.selected]
        if self.delete_items(items):
            self.selected = set()
            self.build()

    def move_selected(self):
        items = [i for i in self.inv["items"] if i["id"] in self.selected]
        if not items:
            return
        dlg = Dialog(self.app, f"Change category of {len(items)} items", width=420)
        field_label(dlg.body, "New category", "pick one or type a new one").pack(anchor="w")
        cb = ttk.Combobox(dlg.body, values=self._categories(), width=30)
        cb.pack(anchor="w", pady=(4, 0))

        def ok():
            c = cb.get().strip()
            for i in items:
                i["category"] = c
            self.save()
            dlg.destroy()
            self.selected = set()
            self.build()
            self.app.notice.show(f"Moved {len(items)} items to {c or OTHER}")
        dlg.buttons("Move", ok)
        dlg.show(focus=cb)

    def toggle_item(self, it):
        if it["id"] in self.selected:
            self.selected.discard(it["id"])
        else:
            self.selected.add(it["id"])
        keep = self.sf.position()
        self.render()
        self.sf.restore(keep)

    def import_csv(self):
        path = filedialog.askopenfilename(parent=self.app, title="Items CSV (Category, Item, Size, Quantity)",
                                          filetypes=[("CSV / text", "*.csv *.txt"), ("All files", "*.*")])
        if not path:
            return
        try:
            rows = invm.read_items_csv(path)
        except Exception as ex:
            messagebox.showerror("Can't read file", str(ex), parent=self.app)
            return
        if not rows:
            messagebox.showinfo("Nothing found", "No items in that file (it needs an Item or Name column).",
                                parent=self.app)
            return
        with_qty = len([r for r in rows if r["qty"]])
        cart = False
        if with_qty:
            cart = messagebox.askyesno("Quantities", f"{len(rows)} items. {with_qty} have a quantity.\n\n"
                                       "Put those quantities in your cart too?", parent=self.app)
        n, sk = invm.import_items(self.s, path, put_in_cart=cart)
        self.inv = invm.load(self.s)
        self.build()
        self.app.notice.show(f"Added {n} items" + (f" \u00b7 {sk} were already there" if sk else ""))
        self.app.refresh_badges()

    def render(self):
        for w in self.sf.winfo_children():
            w.destroy()
        if not self.inv["items"]:
            empty_state(self.sf, "\U0001F4E6", "No items yet", "+ Add item", self.item_dialog,
                        sub="Add everything you order: a name, the unit (case, box…) and a category. "
                            "Got a list? More ▾ → Add many at once.")
            return
        groups = self._groups([i for i in self.inv["items"] if self._match(i)])
        self.paint_sel_bar()
        if not groups:
            tk.Label(self.sf, text="Nothing matches.", bg=BG_PAGE, fg=FG_SEC, font=(FONT, 12), pady=30).pack()
            return
        for c in self._cat_order(groups):
            hd = tk.Frame(self.sf, bg=BG_PAGE)
            hd.pack(fill="x", pady=(10, 4))
            tk.Label(hd, text=c, bg=BG_PAGE, fg=FG, font=(FONT, 12, "bold")).pack(side="left")
            tk.Label(hd, text=f"{len(groups[c])}", bg=BG_PAGE, fg=FG_SEC, font=(FONT, 10)).pack(side="left", padx=8)
            card = Card(self.sf, padx=0, pady=0)
            card.pack(fill="x")
            for it in groups[c]:
                sel = it["id"] in self.selected
                bg = "#EEF2FF" if sel else BG_CARD
                r = tk.Frame(card, bg=bg, cursor="hand2")
                r.pack(fill="x")
                tk.Frame(card, bg="#F1F3F6", height=1).pack(fill="x")
                parts = [r]
                if self.selecting:
                    v = tk.BooleanVar(value=sel)
                    cbx = tk.Checkbutton(r, variable=v, bg=bg, command=lambda it=it: self.toggle_item(it))
                    cbx.pack(side="left", padx=(10, 0))
                nm = tk.Label(r, text=it["name"], bg=bg, fg=FG if it.get("active", True) else FG_SEC,
                              font=(FONT, 11, "bold"), anchor="w", padx=12, pady=9, cursor="hand2")
                nm.pack(side="left")
                sub = "  \u00b7  ".join(x for x in (it.get("unit"), it.get("notes"),
                                                    None if it.get("active", True) else "hidden") if x)
                sl = tk.Label(r, text=sub, bg=bg, fg=FG_SEC, font=(FONT, 10), cursor="hand2")
                sl.pack(side="left")
                parts += [nm, sl]
                if self.selecting:
                    for w in parts:
                        w.bind("<Button-1>", lambda e, it=it: self.toggle_item(it))
                else:
                    acts = tk.Frame(r, bg=bg)
                    acts.pack(side="right", padx=10)
                    Btn(acts, "Edit", lambda it=it: self.item_dialog(it), "outline", small=True).pack(side="left", padx=2)
                    Btn(acts, "Delete", lambda it=it: self.delete_items([it]) and self.build(), "ghost",
                        small=True).pack(side="left", padx=2)
                    parts.append(acts)
                    for w in parts:
                        w.bind("<Button-1>", lambda e, it=it: self.item_dialog(it))
                    self.bind_menu(parts, it)
                    hover(parts, BG_CARD, "#F5F7FF")


# ═════════════════════════════════════════════════════════════════════════════
#  HISTORY
# ═════════════════════════════════════════════════════════════════════════════
class HistoryPage(_InvBase):
    def build(self):
        for w in self.parent.winfo_children():
            w.destroy()
        orders = sorted(self.inv["orders"], key=lambda o: o["date"], reverse=True)
        h = PageHeader(self.parent, "Order History", f"{len(orders)} past orders" if orders else "")
        Btn(h.actions, "Export CSV", self.export_csv, "ghost", tip=f"{MOD_SYM}E").pack(side="right")
        if orders:
            sbar = tk.Frame(self.parent, bg=BG_PAGE, padx=28)
            sbar.pack(fill="x", pady=(0, 12))
            self._search(sbar, lambda: (self.render_list(), self.sf.to_top()), width=34,
                         placeholder="Find an item").pack(side="left")
        body = tk.Frame(self.parent, bg=BG_PAGE)
        body.pack(fill="both", expand=True)
        self.drawer = Drawer(body, width=420)
        self.sf = ScrollFrame(body)
        self.sf.pack(side="left", fill="both", expand=True, padx=(28, 12), pady=(0, 16))
        self.orders = orders
        if not orders:
            empty_state(self.sf, "\U0001F5C2", "No orders yet", "Go to Order", lambda: self.app.go("Order"),
                        sub="When you press “Mark as ordered” in your cart, the order is saved here "
                            "and the suggestions learn from it.")
            return
        self.render_list()

    def _line_cat(self, ln):
        if ln.get("category"):
            return ln["category"]
        it = next((i for i in self.inv["items"] if i["id"] == ln.get("item_id")), None)
        return self.cat(it) if it else OTHER

    def _order_hits(self, o):
        return [ln for ln in o["lines"] if matches(self.query, ln.get("name", ""), self._line_cat(ln))]

    def render_list(self):
        for w in self.sf.winfo_children():
            w.destroy()
        orders = self.orders
        if self.query:
            orders = [o for o in orders if self._order_hits(o)
                      or matches(self.query, date.fromisoformat(o["date"]).strftime("%a %b %d %Y %m/%d"))]
            if not orders:
                tk.Label(self.sf, text=f"No orders with “{self.query}”.", bg=BG_PAGE, fg=FG_SEC,
                         font=(FONT, 12), pady=30).pack()
                return
            total = sum(ln["qty"] for o in orders for ln in self._order_hits(o))
            tk.Label(self.sf, text=f"{len(orders)} orders  ·  {total:g} ordered in total", bg=BG_PAGE,
                     fg=FG_HDR, font=(FONT, 10, "bold")).pack(anchor="w", pady=(0, 6))
        card = Card(self.sf, padx=0, pady=0)
        card.pack(fill="x")
        for o in orders:
            d = date.fromisoformat(o["date"])
            r = tk.Frame(card, bg=BG_CARD, cursor="hand2")
            r.pack(fill="x")
            tk.Frame(card, bg="#F1F3F6", height=1).pack(fill="x")
            a = tk.Label(r, text=d.strftime("%a, %b %d %Y"), bg=BG_CARD, fg=FG, font=(FONT, 12, "bold"),
                         width=16, anchor="w", padx=16, pady=10, cursor="hand2")
            a.pack(side="left")
            b = tk.Label(r, text=f"{len(o['lines'])} items", bg=BG_CARD, fg=FG, font=(FONT, 11), width=9, anchor="w",
                         cursor="hand2")
            b.pack(side="left")
            hits = self._order_hits(o) if self.query else o["lines"]
            ctext = "  ·  ".join(f"{ln['qty']:g} × {ln['name']}" for ln in hits[:3]) + \
                ("  …" if len(hits) > 3 else "")
            c = tk.Label(r, text=ctext, bg=BG_CARD, fg=ACCENT if self.query else FG_SEC, font=(FONT, 10),
                         anchor="w", cursor="hand2")
            c.pack(side="left")
            parts = [r, a, b, c]
            for w in parts:
                w.bind("<Button-1>", lambda e, o=o: self.open_order(o))
            hover(parts, BG_CARD, "#F5F7FF")

    def open_order(self, o):
        d = date.fromisoformat(o["date"])
        self.drawer.open(d.strftime("%A, %B %d"), lambda b: self._order_body(b, o),
                         sub=f"{len(o['lines'])} items")

    def _order_body(self, b, o):
        cur = None
        for ln in sorted(o["lines"], key=lambda x: (self._line_cat(x) == OTHER, self._line_cat(x).lower(), x["name"])):
            if self._line_cat(ln) != cur:
                cur = self._line_cat(ln)
                tk.Label(b, text=cur.upper(), bg=BG_CARD, fg=FG_SEC, font=(FONT, 9, "bold")).pack(anchor="w", pady=(8, 2))
            r = tk.Frame(b, bg=BG_CARD)
            r.pack(fill="x", pady=1)
            tk.Label(r, text=f"{ln['qty']:g}", bg=BG_CARD, fg=ACCENT, font=(FONT, 11, "bold"), width=4,
                     anchor="e").pack(side="left")
            tk.Label(r, text=f"{ln['name']}" + (f"  ({ln['unit']})" if ln.get("unit") else ""), bg=BG_CARD, fg=FG,
                     font=(FONT, 10), anchor="w", wraplength=300, justify="left").pack(side="left", padx=8)
        tk.Frame(b, bg=BORDER, height=1).pack(fill="x", pady=12)
        Btn(b, "Put these in my cart again", lambda: self.reorder(o), "primary", small=True,
            tip="Adds these quantities to your current cart").pack(anchor="w")
        Btn(b, "Delete this order", lambda: self.delete_order(o), "danger", small=True).pack(anchor="w", pady=(10, 0))

    def reorder(self, o):
        ids = {i["id"] for i in self.inv["items"]}
        n = 0
        for ln in o["lines"]:
            if ln["item_id"] in ids:
                self.inv["draft"]["qty"][ln["item_id"]] = ln["qty"]
                n += 1
        self.save()
        self.app._order_mode = "cart"
        self.app.go("Order")
        self.app.notice.show(f"Put {n} items in your cart")

    def delete_order(self, o):
        if messagebox.askyesno("Delete order", f"Delete the order from {o['date']}?\n"
                               "Suggestions will no longer learn from it.", parent=self.app):
            self.inv["orders"].remove(o)
            self.save()
            self.build()

    def export_csv(self):
        p = filedialog.asksaveasfilename(parent=self.app, defaultextension=".csv",
                                         initialfile="inventory_orders.csv", filetypes=[("CSV", "*.csv")])
        if not p:
            return
        with open(p, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["Date", "Category", "Item", "Unit", "Qty"])
            for o in sorted(self.inv["orders"], key=lambda o: o["date"]):
                for ln in o["lines"]:
                    w.writerow([o["date"], self._line_cat(ln), ln["name"], ln.get("unit", ""), f"{ln['qty']:g}"])
        self.app.notice.show("CSV saved")

    export_pdf = export_csv

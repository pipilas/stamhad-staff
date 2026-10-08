"""Help page: every "how does this work" answer in one place, searchable.

Topic text mini-format (one item per line):
  ## Heading          - Step one (bullet)        1. Step (numbered)
  ! Tip box           key | meaning (key/value row)     plain line = paragraph
  **bold** works inside any line.
"""

from __future__ import annotations

import re
import tkinter as tk

from ui import *  # noqa: F401,F403

TOPICS = [
    ("start", "\U0001F44B", "Getting started", """
A new install starts **empty**. A welcome screen asks how tips are split and how to bring in your employees (Toast export, Stamhad Payroll, a file from another computer, or by hand).
Stamhad Staff keeps your **employees**, the **weekly schedule**, **hours & tips** and **inventory**. There's no payroll: at the end of the week it gives you **hours worked** and **total tips** for each person.
Everything is saved automatically the moment you change it. There's no Save button except in Settings.
## The sidebar
- **Home**: today at a glance. Who's working, hours and tips today, the week so far, supplies that are due, and anything that needs fixing. Click any card to go there.
- **Schedule**: plan the week.
- **Hours & Tips**: each day's hours (from Toast or typed in) and the tip split.
- **Week**: totals per person for the week, ready to export.
- **Order / Items / Order History**: inventory.
- **Employees / Positions / Settings**: setup.
## Moving around
- Click the **date** at the top of a page to open a calendar and jump to any day or week. **‹ ›** go back or forward and **Today** comes back.
- Click a person or **Details** to open the side panel on the right. **Esc** closes it.
- In any dropdown, **type letters** to narrow the list (e.g. "chri" shows only the Christophers).
! Everything automatic can be changed by hand: hours from Toast, tip hours, points, a fixed tip. Look for **Details**.
"""),
    ("install", "\U0001F4BB", "Install the app", """
Download the latest version from GitHub: **github.com/pipilas/stamhad-staff → Releases**.
## Windows: installer (recommended)
1. Download **StamhadStaff-Setup.exe** and double-click it. If SmartScreen warns, click **More info → Run anyway** (the app isn't signed by Microsoft).
2. Click through the steps. You can tick **Create a desktop shortcut**.
3. It installs into your user's programs folder (%LOCALAPPDATA%\\Programs\\Stamhad Staff). No administrator password is needed, so updates can install themselves too.
4. Open it from the **Start menu** or the desktop shortcut. To remove it: **Settings → Apps → Stamhad Staff → Uninstall**. Your data is kept.
## Windows: without installing
**StamhadStaff-<version>-portable.exe** is one file you can run from anywhere, like a USB stick. Keep it out of Downloads.
## Mac: installer (M1 or newer)
1. Download **StamhadStaff-<version>-mac.pkg**.
2. Double-click it. If macOS blocks it: **System Settings → Privacy & Security → Open Anyway**, then open it again.
3. Click through the steps (it asks for your Mac password). The app goes into **Applications**.
## Mac: disk image
Or download the **.dmg**, open it, and drag **Stamhad Staff** into **Applications**.
! Always open the app from **Applications** (Mac) or the **Start menu** (Windows), not from the download, so updates can replace it.
## Where is my data?
Your data is in its own folder, separate from the app, so updating or reinstalling never touches it:
- Mac: ~/Library/Application Support/StamhadStaff
- Windows: %APPDATA%\\StamhadStaff
**Settings → Data → Open data folder** opens it.
"""),
    ("Schedule", "\U0001F4C5", "Schedule", """
## Week view
- Each cell is filled with the shift colour: **yellow = Morning**, **green = Brunch**, **blue = Dinner**.
- Someone working **both** shifts that day gets a cell split **diagonally**: day shift top-left, Dinner bottom-right.
- The time only shows when it's different from the usual (Settings → Schedule).
- **Click a day's header** to pick who works that day (with search). **Click a cell** to change one person.
## Day view
One day at a time, with each shift's people listed. Click someone to change their shift.
## More ▾
- **Copy last week**: start from last week's schedule.
- **Clear this week**.
- **Export PDF / CSV**: Front of House and Back of House come out separately (one page each in the PDF), with no hours or totals, ready to print or post.
! Search (**⌘F**) finds a person or a position in the grid.
"""),
    ("Hours & Tips", "⏱", "Hours & Tips", """
Each day has two steps, done one shift at a time (Morning/Brunch | Dinner tabs).
## 1 Hours
- **Get hours ▾ → Download from Toast**: gets last night's clock-ins (see "Toast connection").
- **Get hours ▾ → From a CSV file**: a Toast Time Entries export.
- **Get hours ▾ → Copy the schedule**: uses the scheduled times.
- **+ Add person** types someone in by hand.
- Names the app doesn't know show in red with **+ Add**, which creates the employee and remembers the Toast name next time.
- In, Out and Hours can all be edited. Click **Details** for tip hours, points, a fixed tip, or to remove the person.
## Doubles
If someone works the day shift and Dinner (e.g. 10 AM → 11 PM), the app spots it and offers to **split the double** into two entries, one per shift, so each shift's tips are shared correctly.
## 2 Tips
Type **Floor tips** and **Bar tips** for the shift. The payout list updates as you type. See "How tips are split".
! The yellow bar "Scheduled but not here" lists people on the schedule with no hours. Click **Add them** if they worked.
"""),
    ("tips", "\U0001F4B5", "How tips are split", """
## Two ways, you choose
Pick one in **Settings → Tips & shifts → How are tips split?** It applies to every day.
- **By points only** (new installs start here): each person's share = their **position points**. Everyone on the shift gets their full points, however long they stayed.
- **By time worked × points**: share = **tip hours × points**, so who came earlier or stayed longer gets more.
## Example: points only
Floor tips $336. Two servers (9), one busser (6), two bartenders (9) = 42 points.
- $336 ÷ 42 = $8 per point
- Each server and bartender gets 9 × $8 = **$72**, and the busser 6 × $8 = **$48**, even if one server worked 7 hours and the other 2½.
## Tip hours (only when splitting by time)
- **Dinner**: the tip clock **starts at 4:05 PM** and **stops at 11:00 PM**.
  - Clock in before 4:05 → counts from 4:05 (a few minutes of space, so 3:55 and 4:01 are treated the same).
  - Still working after 11 PM → counts as 11:00, so everyone who stays gets the full share.
- **Morning / Brunch**: every hour counts (unless you set times).
- The times are in **Settings → Tips & shifts** ("Starts" / "Stops"), shown when "By time worked" is chosen.
! Tip hours only affect tips. **Hours worked are never changed.**
## Example: by time
Floor tips $226.86, both 9 points, both on 6.75 tip hours:
- 6.75 × 9 = 60.75 point-hours each → 121.50 total
- $226.86 ÷ 121.50 = $1.867 per point-hour
- Each gets 60.75 × $1.867 = **$113.43**
## Who gets nothing from the pool
- Positions with **0 points** (kitchen, host…). They're listed under the payout as "not in the tip split".
- People with a **fixed tip** (Details → fixed tip). Fixed tips come off the pool first.
## Bar tips
Bar tips are a separate pool. The **barback's %** comes off first, and the rest is split between the **bartenders**: evenly with "points only", by tip hours with "by time". Bartenders also share in floor tips by their points.
"""),
    ("Week", "\U0001F4CA", "Week summary & export", """
- **Totals**: hours and tips per person for the week. **By day**: day by day.
- Click a person to see their days and add a **weekly adjustment** (extra hours or tips with a note).
- **Export ▾ → PDF or CSV**.
! A star (*) on a total in the PDF means it includes a manual adjustment.
"""),
    ("inventory", "\U0001F6D2", "Inventory", """
## Order
- Pick a category on the left, find the item (search with **⌘F**) and set how many with **− / +**.
- ✨ **Suggestions** come from your past orders: how often you order each item and how much.
- **Show my cart** shows everything you've added. There you can **Share ▾** (copy the list or save a CSV) and **✓ Mark as ordered**, which saves it to Order History.
## Items
Everything you order, by category. Click **Edit** or **Delete**, use **Select…** to change many at once, or **Import items from a CSV file…**.
## Order History
Past orders. Click one to see it, **put it in the cart again**, or delete it.
"""),
    ("Employees", "\U0001F465", "Employees & positions", """
## Employees
- **Active / Inactive / All** filter, search, and click someone to edit them.
- **More ▾ → Import from a Toast employee export** replaces your list with the one from Toast.
- **Import from Stamhad Payroll** copies employees and positions (wages aren't copied).
## Positions
Each position has **tip points**, **Front or Back of House**, whether it **gets bar tips**, and a **bar share %** (for barbacks).
! Changing points changes the tip split for every day that isn't locked with a fixed tip, so set them before entering tips.
"""),
    ("toast", "\U0001F50C", "Toast connection", """
Hours come from Toast's nightly data export over SFTP.
## Set up (once)
1. Toast Web → **Integrations → Data exports**: turn on **Time Entries** (Employee, Job Title, In Date, Out Date, Payable Hours).
2. Add the app's **SSH public key** in Toast (the line starting with "ssh-rsa"; not the SHA256 fingerprint).
3. Settings → **Toast**: host, username, export ID and the key. **Save setup file…** writes one file you can load on other computers, so they use the same key.
## Why isn't last night there?
Toast makes the export overnight. If it says there's no file for a date, the export wasn't made yet, or Time Entries isn't turned on.
"""),
    ("share", "\U0001F4E4", "Share, receive & sync", """
Move all the data between computers, or send it to be checked, as **one file**. Find it in **Settings → Data**.
## Share files…
Saves everything into one **.stamhad** file: employees, positions, schedule, hours & tips, inventory, settings and the **error log**. Send it by email, WhatsApp or AirDrop.
! The Toast key is **never** included.
## Receive files…
Open a .stamhad file. It shows what's in it compared with this computer, **backs up your data first**, then you choose:
- **Sync (merge)**: adds what's missing here. Where both have the same thing, the one changed **more recently** wins. Nothing is deleted.
- **Replace everything**: makes this computer exactly like the file. This computer's Toast connection is kept.
- **Save their error log…**: pulls out the other computer's log to read what went wrong.
## Getting a problem checked from far away
1. On the restaurant computer: **Share files…** and send the file.
2. It gets opened on another computer with **Receive files**, checked and fixed.
3. The fixed data comes back the same way: **Receive files → Sync** (or Replace).
"""),
    ("updates", "⬇️", "Updates", """
The app checks GitHub when it opens. If there's a new version it **asks**: **Update now**, **Later**, or **Skip this version**. It never updates on its own.
You can also check any time in **Settings → Data → Check for updates**, and turn the automatic check off there.
## What happens when you update
1. Your data is **backed up** (data folder → backups).
2. The new version is downloaded and **checked** (size and SHA-256). A damaged download is thrown away and nothing changes.
3. The app closes. A small helper swaps in the new version and opens it.
4. If anything goes wrong, the helper **puts the old version back** and opens that. The app tells you on the next start.
! If the update window says the app is "running from the download / disk image", move it to Applications first (Mac) or out of Downloads (Windows).
"""),
    ("trouble", "\U0001F6E0", "Backups & error log", """
## Backups
Made automatically before every update and before receiving files: **data folder → backups** (the last 15 are kept). Each one is a .zip of all your data.
## Error log
Errors are written to **logs/stamhad-staff.log** in the data folder. **Settings → Data → Open error log** opens it, and it's included when you **Share files**.
## Something looks wrong?
1. Note what you clicked and roughly when.
2. **Settings → Data → Share files…** and send the file. It has the data and the log.
## Undo a Receive
Unzip the newest **before-receive-….zip** from the backups folder into the data folder (with the app closed).
"""),
    ("keys", "⌨", "Keyboard shortcuts", "@SHORTCUTS"),
    ("dev", "\U0001F527", "New version (developer)", """
1. Change **version.txt** (e.g. 0.7.1).
2. Add a **## 0.7.1** section to **CHANGELOG.md**. That text is what people see in the update window.
3. Double-click **publish_to_github.command**. It uploads the code and waits while GitHub builds and **tests** the installers (about 10 minutes).
4. Only if every test passes does it publish the release: Setup.exe, portable .exe, Mac .pkg and .dmg. Running apps will offer the update.
! Private files (CSV exports, keys, preset.json, .stamhad files) are blocked from being uploaded.
"""),
]

PAGE_TOPIC = {"Home": "start", "Schedule": "Schedule", "Hours & Tips": "Hours & Tips", "Week": "Week",
              "Order": "inventory", "Items": "inventory", "Order History": "inventory",
              "Employees": "Employees", "Positions": "Employees", "Settings": "share"}


def topic_text(key):
    for k, _, title, body in TOPICS:
        if k == key:
            return title, body
    return "", ""


class HelpPage:
    def __init__(self, app, parent):
        self.app, self.parent = app, parent
        self.key = getattr(app, "_help_topic", None) or "start"
        self.query = getattr(app, "_help_query", "")
        self.build()

    def build(self):
        h = PageHeader(self.parent, "Help", "How everything works — search or pick a topic")
        Btn(h.actions, "Keyboard shortcuts", self.app.show_shortcuts, "ghost").pack(side="right")
        sbar = tk.Frame(self.parent, bg=BG_PAGE, padx=28)
        sbar.pack(fill="x", pady=(0, 10))
        self.search_box = SearchBox(sbar, self.on_query, "Search help (e.g. tips, update, sync)", width=36,
                                    value=self.query)
        self.search_box.pack(side="left")
        body = tk.Frame(self.parent, bg=BG_PAGE)
        body.pack(fill="both", expand=True, padx=28, pady=(0, 16))
        self.side = tk.Frame(body, bg=BG_CARD, highlightthickness=1, highlightbackground=BORDER, width=250)
        self.side.pack(side="left", fill="y")
        self.side.pack_propagate(False)
        right = tk.Frame(body, bg=BG_CARD, highlightthickness=1, highlightbackground=BORDER)
        right.pack(side="left", fill="both", expand=True, padx=(12, 0))
        sb = ttk.Scrollbar(right, orient="vertical")
        sb.pack(side="right", fill="y")
        self.text = tk.Text(right, wrap="word", bg=BG_CARD, fg=FG, relief="flat", bd=0, highlightthickness=0,
                            padx=28, pady=20, font=(FONT, 12), spacing1=2, spacing3=4, cursor="arrow",
                            yscrollcommand=sb.set)
        self.text.pack(side="left", fill="both", expand=True)
        sb.config(command=self.text.yview)
        t = self.text
        t.tag_configure("title", font=(FONT, 20, "bold"), spacing3=10)
        t.tag_configure("h2", font=(FONT, 14, "bold"), foreground=ACCENT, spacing1=14, spacing3=4)
        t.tag_configure("p", lmargin1=0, lmargin2=0)
        t.tag_configure("li", lmargin1=12, lmargin2=30)
        t.tag_configure("li2", lmargin1=36, lmargin2=54)
        t.tag_configure("bold", font=(FONT, 12, "bold"))
        t.tag_configure("tip", background="#EEF2FF", lmargin1=12, lmargin2=12, rmargin=12,
                        spacing1=8, spacing3=8, foreground="#3730A3")
        t.tag_configure("key", font=(FONT, 11, "bold"), foreground=ACCENT, background="#EEF2FF")
        t.tag_configure("hit", background="#FDE68A")
        t.tag_configure("sep", font=(FONT, 4))
        self.render()

    # ── topics list ────────────────────────────────────────────────────────
    def _topics_shown(self):
        if not self.query:
            return TOPICS
        out = []
        for tp in TOPICS:
            body = self._shortcuts_text() if tp[3] == "@SHORTCUTS" else tp[3]
            if matches(self.query, tp[2], body):
                out.append(tp)
        return out

    def render(self):
        for w in self.side.winfo_children():
            w.destroy()
        shown = self._topics_shown()
        tk.Label(self.side, text="TOPICS" if not self.query else f"{len(shown)} MATCHING",
                 bg=BG_CARD, fg=FG_SEC, font=(FONT, 9, "bold"), anchor="w", padx=16).pack(fill="x", pady=(12, 4))
        if self.query and shown and self.key not in [k for k, *_ in shown]:
            self.key = shown[0][0]
        for k, icon, title, _ in shown:
            on = k == self.key
            bg = "#EEF2FF" if on else BG_CARD
            row = tk.Frame(self.side, bg=bg, cursor="hand2")
            row.pack(fill="x", padx=6, pady=1)
            a = tk.Label(row, text=icon, bg=bg, fg=FG, font=(FONT, 12), width=2, cursor="hand2")
            a.pack(side="left", padx=(8, 4), pady=6)
            b = tk.Label(row, text=title, bg=bg, fg=ACCENT if on else FG, anchor="w", cursor="hand2",
                         font=(FONT, 11, "bold" if on else "normal"))
            b.pack(side="left", fill="x", expand=True)
            for w in (row, a, b):
                w.bind("<Button-1>", lambda e, k=k: self.open(k))
            if not on:
                hover([row, a, b], BG_CARD, "#F3F4F6")
        if not shown:
            tk.Label(self.side, text="Nothing found.\nTry another word.", bg=BG_CARD, fg=FG_SEC,
                     font=(FONT, 11), justify="left", padx=16).pack(anchor="w", pady=8)
        self.show_topic()

    def open(self, key):
        self.key = key
        self.app._help_topic = key
        self.render()

    def on_query(self, q):
        self.query = q
        self.app._help_query = q
        self.render()

    # ── the text ───────────────────────────────────────────────────────────
    def _shortcuts_text(self):
        return "\n".join(f"{k} | {v}" for k, v in getattr(self.app, "shortcuts", []))

    def _inline(self, line, base):
        t = self.text
        parts = re.split(r"(\*\*.+?\*\*)", line)
        for p in parts:
            if p.startswith("**") and p.endswith("**"):
                t.insert("end", p[2:-2], (base, "bold"))
            elif p:
                t.insert("end", p, (base,))

    def show_topic(self):
        t = self.text
        t.config(state="normal")
        t.delete("1.0", "end")
        title, body = topic_text(self.key)
        if not title:
            t.config(state="disabled")
            return
        if body == "@SHORTCUTS":
            body = self._shortcuts_text()
        body = "".join(c for c in body if ord(c) <= 0xFFFF)   # Tk 8.6 text search crashes on emoji
        t.insert("end", title + "\n", ("title",))
        n = 0
        for raw in body.strip("\n").split("\n"):
            line = raw.rstrip()
            if not line.strip():
                continue
            s = line.lstrip()
            sub = len(line) - len(s) >= 2
            if s.startswith("## "):
                t.insert("end", s[3:] + "\n", ("h2",))
                n = 0
            elif s.startswith("- "):
                t.insert("end", "•  ", ("li2" if sub else "li",))
                self._inline(s[2:], "li2" if sub else "li")
                t.insert("end", "\n", ("li",))
            elif re.match(r"^\d+\. ", s):
                n += 1
                t.insert("end", f"{n}.  ", ("li", "bold"))
                self._inline(s.split(". ", 1)[1], "li")
                t.insert("end", "\n", ("li",))
            elif s.startswith("! "):
                t.insert("end", "\u2605 ", ("tip", "bold"))      # BMP only: non-BMP chars crash Tk's text search
                self._inline(s[2:], "tip")
                t.insert("end", "\n", ("tip",))
            elif " | " in s and self.key == "keys":
                k, v = s.split(" | ", 1)
                t.insert("end", f" {k} ", ("key",))
                t.insert("end", "   " + v + "\n", ("li",))
            else:
                self._inline(s, "p")
                t.insert("end", "\n", ("p",))
        # highlight search words
        first = None
        for w in (self.query or "").split():
            start = "1.0"
            while True:
                pos = t.search(w, start, stopindex="end", nocase=True)
                if not pos:
                    break
                end = f"{pos}+{len(w)}c"
                t.tag_add("hit", pos, end)
                first = first or pos
                start = end
        t.config(state="disabled")
        t.yview_moveto(0)
        if first:
            t.see(first)

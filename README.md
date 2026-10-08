# Stamhad Staff

Employees, weekly schedule, hours and tips. There is no payroll or wage calculation. At the end of the week the app gives you **hours worked** and **total tips** for each person.

## Download
Get the latest version from **[Releases](https://github.com/pipilas/stamhad-staff/releases/latest)**:

| | File | What it does |
|---|---|---|
| **Windows** | `StamhadStaff-Setup.exe` | Installer: program folder in `%LOCALAPPDATA%\Programs\Stamhad Staff`, Start menu, optional desktop shortcut, uninstaller. No admin needed. |
| Windows | `StamhadStaff-<v>-portable.exe` | Single file, no install. |
| **Mac** (M1+) | `StamhadStaff-<v>-mac.pkg` | Installer: puts the app in Applications. |
| Mac | `StamhadStaff-<v>-mac.dmg` | Drag to Applications. |

Unsigned app: on Windows SmartScreen → *More info → Run anyway*; on Mac → *System Settings → Privacy & Security → Open Anyway*.
Direct link to the newest Windows installer: `https://github.com/pipilas/stamhad-staff/releases/latest/download/StamhadStaff-Setup.exe`

Your data is kept in its own folder (Mac: `~/Library/Application Support/StamhadStaff`, Windows: `%APPDATA%\StamhadStaff`), so it survives updates and reinstalls.

## Updates
The app checks GitHub when it opens and **asks** before updating (Settings → Data → *Check for updates*; the automatic check can be turned off there). While updating:
1. Your data is backed up (data folder → `backups`).
2. The new version is downloaded and its SHA-256 checksum is verified, and a damaged download is thrown away.
3. A small helper waits for the app to close, swaps in the new version, and starts it. If anything fails, it puts the old version back and starts that instead, and the app tells you on the next start.

## Share, receive & sync (and remote debugging)
Settings → Data:
- **Share files…** saves everything (employees, schedule, hours & tips, inventory, settings **and the error log**) into one `.stamhad` file to send by email, WhatsApp or AirDrop. The Toast key is never included.
- **Receive files…** opens a `.stamhad` file. It backs up first, then:
  - **Sync (merge):** add what's missing; where both sides have the same thing, the more recently changed one wins. Nothing is deleted.
  - **Replace everything:** make this computer identical to the file. The Toast connection here is kept.
  - **Save their error log…** extracts the log so you can read what went wrong on the other computer.
- **Open error log:** errors are written to `logs/stamhad-staff.log` in the data folder.

## Releasing a new version (developer)
1. Bump `version.txt` and add a `## <version>` section to `CHANGELOG.md` (that text becomes the update notes).
2. Double-click `publish_to_github.command`. It pushes the code and waits while GitHub Actions builds and **tests** both installers (installs them, runs them, updates over them, uninstalls). Only if everything passes does it tag the version.
3. The tag publishes the release (Setup.exe, portable .exe, .pkg, .dmg, `SHA256SUMS.txt`). Running apps will offer the update.

## Run from source
```
pip3 install -r requirements.txt   # optional: Toast download + PDF export
python3 app.py                     # or double-click run_mac.command
```
The first time it opens, a welcome screen asks how tips are split and how to add employees (Toast employee export, a file from another computer, or by hand).

## Layout
The sidebar on the left has three sections. Each page shows one thing at a time, and details open in a side panel on the right (Esc closes it).

- **Home:** today at a glance. Who's working, today's hours and tips, the week's totals, supplies that are due, and anything that needs fixing. Every card opens its page.
- **STAFF**
  - **Schedule:** a **Week** grid where each cell is filled with the shift colour (doubles split diagonally; times only show when they differ from the usual). Click a date to pick staff, or click a cell to change one person. The **Day** view lists each shift's people. More ▾ has Copy last week, Clear, and Export.
  - **Hours & Tips:** two steps, one shift at a time (Brunch/Morning | Dinner tabs).
    - **1 Hours:** Get hours ▾ (Toast download, CSV file, or copy the schedule), then a simple table of name, position, in, out and hours.
    - **2 Tips:** type Floor and Bar tips; the payout list updates as you type.
    - Click **Details** or any person to open the side panel: tip hours, points, a fixed tip, split a double, remove them.
  - **Week:** **Totals** (hours and tips per person) or **By day**. Click a person for their days and a weekly adjustment.
- **INVENTORY**
  - **Order:** pick a website on the left and type quantities. Each website has ✨ Use suggestions, Open N links, and (Amazon only) Add all to cart.
  - **Items:** everything you order, grouped by website. Click an item to edit or delete it.
  - **Order History:** past orders. Click one to see it, order it again, or delete it.
- **SETUP:** Employees (Active/Inactive filter, search, click to edit), Positions, and Settings (tabs: Tips & shifts, Schedule, Toast, Data).

## Using it quickly
- **Enter** presses the main button in a dialog (Save / Import) and **Esc** closes it.
- In the Day table, **Enter**, **↑** and **↓** save the field you're in and move to the row above or below. **Tab** goes to the next field.
- Clicking into a field selects what's there, so you can just type over it.
- In a dropdown, type a few letters to jump to that name (e.g. "sak" → Sakis).
- Shortcuts: **⌘1–⌘9** go to the pages in sidebar order and **⌘,** opens Settings; **⌘← / ⌘→** go to the previous or next day or week, **⌘T** jumps to today, **⌘N** adds a new entry, employee or position, **⌘D** downloads from Toast, **⌘I** imports a CSV, **⌘E** exports a PDF, **⌘S** saves settings. Press **⌘/** or the **?** button for the full list.
- Scrolling is smooth. The mouse wheel over a dropdown scrolls the page and never changes the dropdown's value. Pages keep their scroll position when you come back to them.
- The app remembers the window size and the last page you had open.

## New people & doubles
- **Toast import:** names the app doesn't know are shown in red with a **+ Add** button. It fills in the name as First Last and the position from the Toast job, and it fixes every row with that name at once. **+ Add all new people** goes through them one by one. Next time the same Toast name is matched automatically.
- Every employee dropdown has **+ New employee…** at the top, on the Day page and in the import preview. The schedule's **Pick staff** window has a **+ New employee** button, and the employee dialog has **+ New position**.
- A position that doesn't exist yet (e.g. "Line Cook") can be typed in and is created on the spot. You can tell it to always treat that Toast job as one of your positions.
- Position dropdowns list the person's own positions first, then all the others. Picking another one adds it to that person.
- **Shift detection:** each clock-in goes to the shift whose usual hours it covers most. On a brunch day, 1:46 PM–11:31 PM counts as Dinner.
- **Doubles:** someone who came in around the start of brunch and stayed through dinner is split into Brunch and Dinner (at the Dinner start time, 4 PM by default), so they get tips from both. This is ticked by default in the import and can be unticked. On the Day page you can also split a row with the ✂ button.

## Inventory
- **Items:** paste a product link and the **name** and **website** fill themselves in; the link is optional. "Get name from page" reads the real product title when the site allows it. **Paste many links…** adds a whole list at once, one link per line. **Save & add another** keeps the unit and category for the next item.
- **Order:** type how many of each item you want. Items are grouped by website, and each website has **Open N links**, which opens every product page in a separate tab. Amazon also gets **Add all to Amazon cart**: one link that puts every item with its quantity into your cart. Tick **In cart** as you go. **Mark as ordered** saves the order to History.
- Items with no link get a 🔎 **find** button that searches for them on their website.
- **Suggestions (✨):** a small model learns from your past orders. It looks at how fast each item gets used up, how you usually pack it (e.g. always 2 cases) and how long ago you last ordered it. It needs at least 2 orders of an item. Hover over ✨ to see why it suggests that amount, and click it to use it. **Use suggestions** fills in every item that's due. You always decide the final numbers.
- **History:** every past order, with **Order again** and CSV export.

## Tip rule
For each shift the app splits two pools:
- **Floor tips** are shared by `tip hours × position points`.
  *Tip hours* run from clock-in to clock-out. On Dinner they stop at **11:00 PM**. Anyone still working at 11 gets the full share for the time they arrived, however late they leave. Morning and Brunch count all hours. You can change these times in Settings.
- **Bar tips**: each barback gets a fixed % first. Bartenders split the rest by tip hours.
- **Fixed amounts**: when you type a Tip $ for someone, the app pays them exactly that and splits the rest among everyone else. The pool always adds up.

Brunch is Saturday and Sunday. Clock-ins before 2:00 PM count as the day shift. Both are set in Settings.

## Data
Your data is saved as plain JSON the moment you change anything:
- Mac: `~/Library/Application Support/StamhadStaff/`
- Windows: `%APPDATA%\StamhadStaff\`

The app uses the Toast SSH key that Stamhad Payroll already has.

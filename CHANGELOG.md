# Changelog

The release notes shown in the app's update window come from this file:
the section whose heading matches the version being released.

## 0.8.0
- Sign in with your Stamhad account (email and password). The password isn't stored on the computer
- Subscription check when the app opens and every few hours; works offline for 7 days after the last check
- Settings → Account: plan, paid until, last check, change password, sign out
- If the subscription isn't active you can still save all your data

## 0.7.4
- Removed the "Import from Stamhad Payroll" option (welcome screen, Employees and Settings)

## 0.7.3
- Fixed: on Windows the update said the new version would open but it never did. Installed copies now hand the update to the installer directly, and the app only closes once the updater has really started

## 0.7.2
- Fixed: on Windows, clicking any button showed a "bad screen distance" error
- Tips: choose how they're split in Settings → Tips & shifts: by points only, or by time worked × points. New installs start with points only; existing installs keep splitting by time
- New installs start empty with a welcome screen: choose how tips are split and how to add employees (Toast export, Stamhad Payroll, a file from another computer, or by hand)
- Employees → More: import from a Toast employee export

## 0.7.1
- Installers: StamhadStaff-Setup.exe for Windows (Start menu, desktop shortcut, uninstaller) and a .pkg installer for Mac
- Updates work for installed copies too (the new installer runs by itself in the background)
- Help page: install instructions for the new installers

## 0.7.0
- Now available as a Windows app (.exe) and a Mac app (.dmg)
- Updates: the app checks for a new version when it opens and asks before updating. Your data is backed up first, and if anything goes wrong the old version stays
- Settings → Data: Share files and Receive files (with Sync or Replace) to move data between computers or send it for checking
- Help page (sidebar → ? Help, or F1): how everything works, with search
- Error log: problems are saved to a log that's included when you share files
- Calendar: click the date to pick any day or week
- Dropdowns: type letters to narrow the list
- Schedule: whole-cell shift colours, diagonal split for doubles; export split into Front / Back of House with no hours
- Tips: Dinner tip clock starts 4:05 PM (editable in Settings)

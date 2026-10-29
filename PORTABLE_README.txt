LifeOS for Windows x64 - current weekly-checklist build

START
Double-click LifeOS.exe. Keep the _internal folder alongside it.
Copy the entire LifeOS folder when moving the app. No separate Python,
virtual environment, VS Code, installer or internet connection is needed.

YOUR DATA
Normal profile: %LOCALAPPDATA%\LifeOS\lifeos.sqlite3.
Logs and backups are alongside your profile, outside this application folder.
Moving/updating this application folder does not reset or move your profile.
Use Settings > Data safety for Backup and Restore. Restore first creates a
safety backup. Never overwrite an active database manually.
LIFEOS_DATA_DIR or --data-dir selects a separate profile when desired.
No personal database, credentials or saved user records ship in this package.

WORKOUT CHECKLIST
Choose Monday-Sunday, select muscles, type any target and optional goal,
then Add target or press Enter. Tick/untick directly, edit/remove/reorder.
Plans/checkmarks save automatically. Reset asks confirmation and preserves
names, goals and muscles, with a snapshot in Workout history. No session
start/finish or set logging is required. Earlier workout records remain
read-only in history; checklist ticks do not fabricate measured sets.

OTHER FEATURES
DSA records and code versions; subjects and study sessions; dated meals,
food/recipe lookup, nutrition, hydration and measurements; daily tasks,
routines and persistent focus timer; analytics; backup and settings.
The food library starts with source-labelled references, not your records.

APPEARANCE
Settings > Appearance / Theme switches immediately between Current Theme
(monochrome photographic glass) and CMD / Robotic Command Center.
The selection persists. Icons, photos and dependency fonts work offline.
Windows supplies Segoe UI/Consolas; native file/message dialogs use OS styling.
Tk glass uses stable compositing rather than native OS backdrop blur.
Lucide license: _internal\lifeos\assets\LUCIDE-LICENSE.txt.
Photo provenance/license: _internal\lifeos\assets\backgrounds\.

LIMITS
Windows x64 desktop package. No installer, OS notification service or
code-signing certificate. Reminders run while open. Running focus timers
count elapsed time while closed up to the planned duration; pause to stop.
Reference food values and recipes are approximate and editable.

The source project and its Launch LifeOS.cmd remain separate and unchanged.
Older archived executables/ZIP files are previous builds; use this folder's
LifeOS.exe for this packaged version. See BUILD_INFO.json when present.

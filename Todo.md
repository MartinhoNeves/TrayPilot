# TrayPilot — Development Roadmap

**Design spec:** `G:\Obsidian Vaults\claude\Projects\TrayPilot\260406220939 - TrayPilot design spec.md`
**Alarms spec:** `G:\Obsidian Vaults\claude\Projects\TrayPilot\260407142815 - alarms feature spec.md`

## Table of Contents

- [M1 — Persistent Settings Foundation](#m1--persistent-settings-foundation) ✅
- [M2 — Window State Persistence & Pin Behavior](#m2--window-state-persistence--pin-behavior) ✅
- [M3 — Infrastructure & Google Auth](#m3--infrastructure--google-auth) ✅
- [M4 — System Tray & Popup Flyout](#m4--system-tray--popup-flyout) ✅  
- [M5 — Full Window Shell & Layout](#m5--full-window-shell--layout) ✅
- [M6 — Centralized color control](#m6--centralized-color-control) ✅
- [M7 — Filesystem, Paths, and User Data Isolation](#m7--filesystem-paths-and-user-data-isolation) ✅
- [M8 — Calendar Widget & Date Selection](#m8--calendar-widget--date-selection) ✅
- [M9 — Slide-in Event Form & CRUD](#m9--slide-in-event-form--crud) ✅
- [M10 — Alarms & Reminders](#m10--alarms--reminders) ✅
- [M11 — Gmail New Mail Awareness](#m11--gmail-new-mail-awareness) ✅
- [M12 — Gmail Inbox Read & Manage](#m12--gmail-inbox-read--manage) ✅
- [M13 — Settings Tab](#m13--settings-tab)
- [M14 — About Tab](#m14--about-tab)
- [M15 — Popup Segmentation & Tray Menu Tab Shortcuts](#m15--popup-segmentation--tray-menu-tab-shortcuts) ✅
- [M16 — Visual Polish & Dark Theme](#m16--visual-polish--dark-theme)
- [M17 — Filesystem & Release Readiness](#m17--filesystem--release-readiness)

---

## M1 — Persistent Settings Foundation

**Goal:** Add a persistent settings layer backed by `settings.json` so user preferences survive app restarts.

**Why here:** Preferences are cross-cutting behavior. Implementing this first avoids scattered ad hoc settings writes and ensures dark/light mode becomes a true user preference instead of a session-only toggle.

**Topic notes:** Start with theme preference (`dark`/`light`) and keep schema extensible for future settings.

**Implementation notes:** Use `Paths.settings_json()` as the canonical storage path. Add a small settings helper module with load/save and defaults, plus safe handling for missing/corrupted files.

- [x] `SET-01` Create a shared settings helper module backed by `settings.json`
- [x] `SET-02` Define settings schema with `theme_mode` key (`dark` or `light`) and defaults
- [x] `SET-03` Load settings at app startup and apply persisted theme before showing primary UI
- [x] `SET-04` Save `theme_mode` immediately when user toggles theme in the main window
- [x] `SET-05` Handle missing/corrupted `settings.json` gracefully by restoring defaults without crashing

---

## M2 — Window State Persistence & Pin Behavior

**Goal:** Persist main-window dimensions, always open centered, and provide a persistent Always-on-Top toggle.

**Why here:** These are core desktop-behavior expectations and should be solved early so UX behavior is stable before additional features build on top.

**Topic notes:** Persist window size only (not position), then center on show so layout remains predictable across screen setups and resolution changes.

**Implementation notes:** Store `window_size` and `always_on_top` in `settings.json`. Apply both at startup for `MainWindow`. Add a small button next to the theme switch to toggle pin/always-on-top in real time and persist immediately.

- [x] `WINCFG-01` Persist main-window dimensions to `settings.json` on resize and restore on startup
- [x] `WINCFG-02` Center main window each time it is shown, regardless of restored dimensions
- [x] `WINCFG-03` Add a small Always-on-Top toggle button next to the theme switch
- [x] `WINCFG-04` Persist Always-on-Top state in `settings.json` and apply it on startup
- [x] `WINCFG-05` Apply Always-on-Top changes immediately when the user toggles the button

---

## M3 — Infrastructure & Google Auth

**Goal:** Project skeleton, path resolution, and Google Calendar OAuth2 working end-to-end before any UI is built.

**Why here:** Nothing else can be built until the API connection is proven. Auth is the highest-risk dependency — validate it first.

**Topic notes:** Keep API/auth concerns isolated from UI so tray/window code never manages OAuth directly.

**Implementation notes:** `google_client.py` must be fully UI-independent. All mutable data goes to `%LOCALAPPDATA%\mn-projects\TrayPilot\`. Follow the same `paths.py` pattern used in other mn-projects tools.

- [x] `INFRA-01` Create project folder structure and `requirements.txt` (`PyQt6`, `google-api-python-client`, `google-auth-oauthlib`, `platformdirs`)
- [x] `INFRA-02` Create `paths.py` — resolve `%LOCALAPPDATA%\mn-projects\TrayPilot\` for token, credentials, settings; auto-create dirs
- [x] `INFRA-03` Create `google_client.py` — implement `get_events()`, `create_event()`, `update_event()`, `delete_event()`
- [x] `INFRA-04` Implement OAuth2 browser flow in `google_client.py` — check for `token.json`, open browser if missing, save token on approval
- [x] `INFRA-05` Implement silent token refresh on expiry; re-trigger auth flow on revocation
- [x] `INFRA-06` Test script at `Docs/test_google_client.py` — run to verify OAuth2 + API headless

---

## M4 — System Tray & Popup Flyout

**Goal:** Tray icon live with single-click popup showing today's events and urgent events for the next 30 days.

**Why here:** The tray and popup are the core identity of the app — the thing users interact with most. Build and validate this before the full window.

**Topic notes:** Urgent = `colorId == "10"` (Tomato) OR `"urgent"` in title/description (case-insensitive).

**Implementation notes:** Popup uses `FramelessWindowHint | WindowStaysOnTopHint | Tool` flags. Position anchored to bottom-right of screen above tray. Auto-close on focus loss.

- [x] `TRAY-01` Create `tray.py` — `QSystemTrayIcon` with icon, single-click → popup, double-click → full window
- [x] `TRAY-02` Add right-click context menu: Open · Refresh · Quit
- [x] `TRAY-03` Create `popup.py` — frameless `QWidget`, anchored bottom-right, auto-closes on focus loss
- [x] `TRAY-04` Populate popup: header with today's date (orange accent), today's events as compact cards
- [x] `TRAY-05` Add urgent events section — divider + urgent event cards (red dot · date · title); "No urgent events" fallback
- [x] `TRAY-06` Add popup footer event navigation controls (`Previous Event` / `Today` / `Next Event`) for quick event-to-event browsing

---

## M5 — Full Window Shell & Layout

**Goal:** Full `QMainWindow` with tab bar (Calendar / Alarms), split layout under Calendar tab — agenda list left, calendar grid right — populated with real data.

**Why here:** Window shell must exist before the calendar widget, slide-in form, and alarms tab can be built into it.

**Topic notes:** This milestone establishes structure and interaction surfaces, not full CRUD workflows.

**Implementation notes:** Keep Alarms as a non-functional stub tab until alarm modules are introduced in M10.

- [x] `WIN-01` Create `window_main.py` — `QMainWindow`, tab bar at top (`📅 Calendar` / `⏰ Alarms`), split layout (left panel + right panel) under Calendar tab, taskbar presence
- [x] `WIN-02` Create `widget_event_list.py` — scrollable agenda list, events grouped by date, colour dot · time · title per row
- [x] `WIN-03` Add row selection — click row activates Edit and Delete buttons
- [x] `WIN-04` Add `+ New Event` button at top of list — stub (wired in M9)
- [x] `WIN-05` Create `widget_calendar.py` — `QCalendarWidget` restyled for dark theme, integrated into right panel
- [x] `WIN-06` Fetch and display events in list on window open; re-fetch on month change

---

## M6 — Centralized color control

**Goal:** Centralize all colour values in one place to prepare for future light/dark mode support.

**Why here:** Colors are currently duplicated across UI modules. Consolidating now reduces future theme-switching work and avoids drift.

**Topic notes:** This is a pure refactor milestone; behavior and visual output should remain unchanged.

**Implementation notes:** Create `colour_theme.py` as the single source of truth. Replace hardcoded literals in UI files with imports/constants from `colour_theme.py`. Implement runtime dark/light mode support with a switch in `window_main.py`, using `Assets/theme_dark.png` and `Assets/theme_light.png` as the toggle icons. Theme changes must apply immediately when the user presses the theme button.

- [x] `CLR-01` Create `colour_theme.py` with centralized app palette constants (background, text, accent, borders, status colors, semantic colors)
- [x] `CLR-02` Move popup colors (`popup.py`) to `colour_theme.py` and remove local duplicates
- [x] `CLR-03` Move main-window/list colors (`window_main.py`, `widget_event_list.py`) to `colour_theme.py` and remove local duplicates
- [x] `CLR-04` Move calendar colors (`widget_calendar.py`) to `colour_theme.py` while preserving custom paint behavior
- [x] `CLR-05` Ensure no single-use hardcoded UI color literals remain outside `colour_theme.py` (except temporary debug-only values)
- [x] `CLR-06` Document palette usage conventions in module docstring/comments so future light/dark mode can be implemented safely
- [x] `CLR-07` Add dark/light mode toggle control (top-right corner of window) in `window_main.py` and use `Assets/theme_dark.png` / `Assets/theme_light.png` for visual state
- [x] `CLR-08` Apply theme in real time when the user presses the dark/light toggle button

---

## M7 — Filesystem, Paths, and User Data Isolation

**Goal:** Ensure the application follows standard desktop filesystem rules and never writes mutable data into the installation directory.

**Why here:** A finished project is not ready to sell if it only works in a developer folder. The first commercial-readiness foundation is correct path handling, especially for installed builds under restricted directories such as `Program Files`.

**Topic notes:** This milestone applies to any already-finished desktop project that creates settings, caches, logs, history, profiles, exports, temporary files, or user-generated content.

**Implementation notes:** Centralize all writable paths behind one shared path-resolution layer. Use the platform-appropriate user data location. On Windows, mutable data should go under `%LOCALAPPDATA%\\mn-projects\\<AppName>\\` unless there is a clear reason to use another known folder.

### PATH-01

- [x] Audit every place in the codebase that reads from or writes to disk
- [x] Classify each file as install-time asset, runtime mutable data, cache, temp file, export, or log
- [x] Produce one canonical list of all application-managed files and folders
- [x] Identify every location currently derived from the executable folder or current working directory

### PATH-02

- [x] Create a single shared helper module for resolving all application paths
- [x] Use a standard cross-platform library like `platformdirs` to natively handle OS-specific path conventions where applicable
- [x] Add a dedicated function for the base user-data directory (`data_dir()`)
- [x] Add dedicated path helpers for runtime JSON under user data: settings, OAuth token, alarms (`settings_json()`, `token_json()`, `alarms_json()`)
- [ ] Add dedicated path helpers for cache, logs, temp data, exports, history, or profiles when those features need writable storage
- [x] Remove ad hoc path construction scattered across the codebase

### PATH-03

- [x] Move all mutable JSON, TXT, DB, cache, and profile files into the user-data directory
- [x] Ensure parent directories are created automatically before first write
- [x] Ensure the app behaves correctly when the directory does not yet exist
- [x] Ensure the app does not require administrator privileges to create or update user data

---

## M8 — Calendar Widget & Date Selection

**Goal:** Calendar shows event indicators and drives the event list filter.

**Why here:** Calendar interaction is the primary navigation mechanic — must be complete before the form is wired in.

**Topic notes:** Date filtering must remain reversible and predictable to avoid trapping users in a filtered view.

**Implementation notes:** Selection-state toggling should be centralized so calendar/list/form interactions stay in sync.

- [x] `CAL-01` Add orange dot beneath dates that have events; red dot for dates with urgent events
- [x] `CAL-02` Click a date → filter event list to that day
- [x] `CAL-03` Click selected date again → clear filter, show all events
- [x] `CAL-04` Click a date → also open slide-in form pre-filled with that date (stub — activated in M9)

---

## M9 — Slide-in Event Form & CRUD

**Goal:** Complete add, edit, and delete operations via the animated slide-in form panel.

**Why here:** All UI surfaces are in place. This milestone wires them together into a working product.

**Topic notes:** CRUD feedback must be immediate and non-destructive when API calls fail.

**Implementation notes:** Form panel lives inside the left panel. `QPropertyAnimation` animates width 0 → full (~250ms ease-out). Config always saves lang-key values, never display strings.

- [x] `FORM-01` Create `panel_event_form.py` — hidden panel (width=0) inside left panel
- [x] `FORM-02` Implement open animation — `QPropertyAnimation` width 0 → full, ease-out ~250ms
- [x] `FORM-03` Implement close animation — reverse; triggered by Cancel or after Save
- [x] `FORM-04` Add form fields: Title · Date · Start time · End time · Colour picker · Description
- [x] `FORM-05` Wire `+ New Event` button → open form pre-filled with today
- [x] `FORM-06` Wire calendar date click → open form pre-filled with selected date (activates `CAL-04` stub)
- [x] `FORM-07` Wire Edit button → open form pre-filled with selected event data
- [x] `FORM-08` Implement Save — call `google_client.create_event()` or `update_event()`; refresh list on success
- [x] `FORM-09` Implement Delete — confirmation dialog; call `google_client.delete_event()`; refresh list on success
- [x] `FORM-10` Handle API errors inline — show error message in form without closing it
- [x] `FORM-11` Add recurring-delete scope dialog (`This event only` / `This and following` / `All events in series`) and apply correct Google Calendar behavior for each option

---

## M10 — Alarms & Reminders

**Goal:** Fully working alarm system — standalone and calendar-linked alarms, recurrence, audio, toast + dialog notification, snooze.

**Why here:** All calendar UI surfaces are complete. Alarms are a self-contained new feature; polish comes after everything is functional.

**Spec:** `G:\Obsidian Vaults\claude\Projects\TrayPilot\260407142815 - alarms feature spec.md`

**Topic notes:** Alarm scheduling logic must be deterministic and testable independently from UI.
**Assets:** Alarm - `Assets/alarm_event.wav`, Calendar - `Assets/calendar_event.wav`, Email - `Assets/email_event.wav`

**Implementation notes:** `alarm_scheduler.py` must be UI-independent — emits a Qt signal, never touches widgets directly. Audio via `QMediaPlayer` (PyQt6.QtMultimedia). Toast via `QSystemTrayIcon.showMessage()`. No extra pip dependencies.

- [x] `ALARM-01` Add `alarms_json` path to `paths.py`; update `main.py` to initialise scheduler on start
- [x] `ALARM-02` Create `alarms.py` — `Alarm` dataclass, load/save `alarms.json`, CRUD helpers, recurrence advance logic
- [x] `ALARM-03` Create `alarm_scheduler.py` — `QTimer` every 30s, due-alarm detection, `alarm_fired(Alarm)` signal; snooze and dismiss logic
- [x] `ALARM-04` Create `alarm_notification.py` — always-on-top `QDialog`; Dismiss + Snooze dropdown (5/10/30 min + Custom spinbox); calls scheduler dismiss/snooze methods
- [x] `ALARM-05` Wire `QSystemTrayIcon.showMessage()` toast on alarm fire; notification appears independently of toast interaction
- [x] `ALARM-06` Implement audio playback — `QMediaPlayer` plays per-alarm sound or global default from `settings.json`; silent if no sound configured
- [x] `ALARM-07` Create `widget_alarm_list.py` — scrollable list, rows (dot · title · next fire · recurrence label · enabled toggle), click to select, Edit/Delete buttons
- [x] `ALARM-08` Create `panel_alarm_form.py` — slide-in form (`QPropertyAnimation` width 0 → full, ~250ms ease-out); fields: Title, Date+Time, Recurrence, Sound picker, Calendar event link + offset
- [x] `ALARM-09` Wire `+ Add Alarm` button → open blank form; Edit button → open form pre-filled; Delete → confirmation dialog
- [x] `ALARM-10` Calendar-linked alarms: populate event dropdown from `google_client.get_events()`; recalculate `next_fire` on each refresh
- [x] `ALARM-11` Use exact scheduler triggering (nearest-alarm single-shot timer) so alarms fire at scheduled time instead of timer-window delay
- [x] `ALARM-12` Add trust notice UX: one-time acknowledgment persisted in `settings.json` + tray menu action to review notice on demand
- [x] `ALARM-13` Harden responsiveness with background worker threads for popup/main-window calendar fetch paths so tray interactions stay responsive under slow network/API calls
- [x] `ALARM-14` Improve alarm form usability: split Date/Time fields, add explicit ▲/▼ controls, increase label readability, and widen slide-in panel to ~50% in alarms workflow
- [x] `ALARM-15` Improve calendar-link scanability: show event date/time alongside title in aligned two-column style for mixed timed/all-day entries
- [x] `ALARM-16` Ensure existing alarms load automatically when opening the window and when switching to the Alarms tab
- [x] `ALARM-17` Standardize trust-notice persistence to `settings.json` only (no extra marker file) for Windows auto-start compatibility

---

## M11 — Gmail New Mail Awareness

**Goal:** Add a lightweight Gmail awareness layer that indicates when new mail has arrived without turning TrayPilot into a full mail client.

**Why here:** By this stage, tray UI, popup/window surfaces, authentication patterns, and scheduler-style background checks already exist. Gmail awareness can be added cleanly before final polish/release hardening.

**Topic notes:** This milestone is notification/state awareness only (unread counts and/or latest-unread signal), not full inbox browsing or message composition.

**Implementation notes:** Keep Gmail logic UI-independent (`gmail_client.py` or equivalent service module). Use Gmail read-only scope and integrate with existing OAuth token flow. Poll at a conservative interval and emit signals only on meaningful state change to avoid notification spam.

- [x] `MAIL-01` Extend auth scopes to include Gmail read-only access and preserve existing Calendar functionality
- [x] `MAIL-02` Handle OAuth migration path for existing users (scope change requires re-consent/token refresh)
- [x] `MAIL-03` Create a UI-independent Gmail service module to query unread/new-mail state
- [x] `MAIL-04` Implement background polling (timer-based) with safe interval and offline/error handling
- [x] `MAIL-05` Track last-seen state and emit a signal only when newly unread mail is detected
- [x] `MAIL-06` Surface mail state in tray context (tooltip and/or popup section) without disrupting existing event UX
- [x] `MAIL-07` Add user setting(s) for mail awareness behavior (enable/disable, polling interval or notification mode)
- [x] `MAIL-08` Ensure theme consistency and clear visual hierarchy for mail indicators in both dark and light modes
- [x] `MAIL-09` Verify no credentials/content leakage in logs or UI; display only minimal metadata needed for awareness

---

## M12 — Gmail Inbox Read & Manage ✅

**Goal:** Expand Gmail awareness into a lightweight inbox browser — users can see unread message subjects and senders, open and read messages in plain text, and move them to trash, all without leaving the app.

**Why here:** M11 established the auth and polling foundation. Inbox browsing is the natural next step before visual polish, while the Gmail plumbing is fresh.

**Topic notes:** Read + trash only — no compose, no reply, no labels management. Scope upgrades from `gmail.readonly` to `gmail.modify` to support trash and mark-as-read. A new token re-auth is required.

**Implementation notes:** Keep all Gmail API calls in `gmail_client.py`. UI surfaces (popup row list, Emails tab, reader dialog) are purely reactive — they receive data via signals and call back via methods, never touching the API directly. Remove messages from local state immediately on trash/read so the UI feels instant without waiting for the next poll.

- [x] `INBOX-01` Upgrade OAuth scope from `gmail.readonly` to `gmail.modify` in `google_client.py`; delete `token.json` and re-auth to obtain new token
- [x] `INBOX-02` Extend `GmailClient` to fetch list of unread messages (id, sender, subject, date, snippet) — cap at 50, newest first; emit new signal `messages_changed(list)`
- [x] `INBOX-03` Add `GmailClient.get_message_body(msg_id) -> str` — fetch and decode plain-text part of a message; fallback to snippet if no plain-text part
- [x] `INBOX-04` Add `GmailClient.trash_message(msg_id)` — move to Gmail trash; remove from local message list and emit `messages_changed`
- [x] `INBOX-05` Add `GmailClient.mark_as_read(msg_id)` — remove `UNREAD` label; remove from local unread list and emit `messages_changed`
- [x] `INBOX-06` Create reusable `_EmailRow` widget (sender bold + subject truncated, single line) used in both popup and Emails tab
- [x] `INBOX-07` Popup flyout: replace mail bar with a scrollable unread message list; 5 rows visible without scrolling, more accessible via scroll; click row → reader dialog
- [x] `INBOX-08` Emails tab (`widget_email_stub.py`): replace stub rows with live scrollable unread list using `_EmailRow`; same click-to-read behaviour
- [x] `INBOX-09` Email reader: `QDialog` showing From / Subject / Date + plain-text body in `QTextBrowser`; Trash button (moves to trash + closes) + Close button; marks as read automatically on open
- [x] `INBOX-10` Instant local state update — on trash or mark-as-read, remove the message from the in-memory list immediately so UI reflects change without waiting for next poll cycle

---

## M13 — Settings Tab

**Goal:** Consolidate all user-configurable preferences into a dedicated Settings tab in the main window, replacing scattered controls in the toolbar and Emails tab.

**Why here:** All major features are complete. Centralising settings now cleans up the toolbar, gives Gmail and alarm options a proper home, and adds the high-value launch-at-startup feature before visual polish locks in the final layout.

**Topic notes:** Main tab order through M14: **Calendar → Emails → Alarms → Settings → About**. Toolbar theme and always-on-top buttons are removed and moved to Settings. Mail settings are removed from the Emails tab (inbox-only after this milestone).

**Implementation notes:** All settings read/write go through `settings.py` as usual. Launch-at-startup writes to `HKCU\Software\Microsoft\Windows\CurrentVersion\Run` (no admin required). Full About UI lives on the dedicated **About** tab (M14); tray no longer exposes About.

- [x] `SET-10` Add Settings tab to main window tab bar (last position); create `widget_settings.py`
- [x] `SET-11` Appearance section: theme toggle (dark/light) and always-on-top toggle — remove both buttons from toolbar
- [x] `SET-12` Gmail section: move "Enable Gmail awareness" and "Check every N min" controls from Emails tab to Settings tab; Emails tab becomes inbox-only
- [x] `SET-13` Alarms section: default alarm sound (dropdown of `.wav` files in `Assets/`); default snooze duration (dropdown: 5 / 10 / 15 / 30 min)
- [x] `SET-14` Notifications section: "Show balloon on new mail" toggle; "Show balloon on alarm" toggle
- [x] `SET-15` Startup section: "Launch at Windows startup" toggle — reads/writes `HKCU\...\Run` registry key via `winreg`
- [x] `SET-16` ~~About section in Settings~~ superseded by M14 — dedicated About tab + shared `AboutPanel` (`dialog_about.py`)

---

## M14 — About Tab

**Goal:** Give About its own main-window tab with the same content as the former modal About dialog (logo, title, version from `version.md`, editable body copy).

**Why here:** Settings was getting crowded; About is discoverable without burying it at the bottom of a scroll area.

**Topic notes:** Tab order: **Calendar → Emails → Alarms → Settings → About**. `AboutDialog` remains available for programmatic use; it embeds the same `AboutPanel` as the tab.

**Implementation notes:** Refactor `dialog_about.py` to expose `AboutPanel(QWidget)`; add `widget_about.py` (`AboutTabWidget` with `QScrollArea`). Remove the compact About block from the Settings tab.

- [x] `ABT-01` Add **About** tab after Settings; `widget_about.py` hosting scrollable content
- [x] `ABT-02` Shared `AboutPanel` — logo (`Assets/app.png`), `ABOUT_TITLE` / `ABOUT_BODY`, version via `APP_VERSION` in `main.py`; `AboutDialog` wraps panel + OK
- [x] `ABT-03` Remove About section from `widget_settings.py`; refresh version when the About tab is selected

---

## M15 — Popup Segmentation & Tray Menu Tab Shortcuts ✅

**Goal:** Improve tray popup information architecture and tray context navigation by splitting popup content into three equal sections and enabling direct tab opening from right-click menu entries.

**Why here:** Core Gmail/Calendar/Alarm surfaces are already live; this milestone refines daily interaction speed and clarity without introducing new external dependencies.

**Topic notes:** Popup sections are now: Events, Unread Mail, and Active Alarms. Active alarms are shown below mail with a separator and a cap of 5 rows.

**Implementation notes:** Keep popup section sizing deterministic by dividing usable body height into thirds. Reuse existing accent typography for section labels to preserve visual consistency. Tray menu actions should map directly to `MainWindow` tabs via a stable tab-selection API.

- [x] `UX-01` Split popup usable body area into 3 equal-height sections (events, unread mail, active alarms)
- [x] `UX-02` Add dedicated `ACTIVE ALARMS` section below unread mail with horizontal separator and empty-state fallback
- [x] `UX-03` Limit active alarms list to at most 5 enabled alarms in popup
- [x] `UX-04` Apply orange accent styling to requested popup section headers for visual parity with unread mail
- [x] `UX-05` Add right-click tray actions for direct tab opening (`Calendar`, `Emails`, `Alarms`, `Settings`, `About`)
- [x] `UX-06` Remove generic `Open` menu action and simplify tab actions by dropping the `Open` prefix
- [x] `UX-07` Add horizontal separator between `About` and `Refresh` in tray context menu

---

## M16 — Visual Polish & Dark Theme ✅

**Goal:** Consistent dark theme across all surfaces including the new alarms tab; app looks and feels like a finished mn-projects product.

**Why here:** All functional surfaces exist. Polish is the final layer before release readiness.

**Topic notes:** Brand colours — background `#1a1a2e`, accent `#e8922a`. Consistent with mn-projects aesthetic.

**Implementation notes:** Apply styles via shared constants/themes to avoid drift and reduce duplicated inline style strings.

- [x] `THEME-01` Write and apply global dark stylesheet — background, text, accent, hover states, borders
- [x] `THEME-02` Style popup panel — rounded corners, drop shadow, compact cards
- [x] `THEME-03` Style full window — tab bar, list rows, selected state, dividers, calendar grid
- [x] `THEME-04` Style slide-in forms — field focus states, button hover, Save/Cancel distinction
- [x] `THEME-05` Style alarm notification dialog — consistent with dark theme, snooze dropdown
- [x] `THEME-06` Add app icon (tray icon + window icon) — consistent with mn-projects branding
- [x] `THEME-07` Calendar weekday headers (Sat/Sun) — override Qt's default red weekend colouring to uniform dim gray `#555`
- [x] `THEME-08` Remove status-bar item separator lines around bottom-right controls for cleaner dark-theme footer

---

## M17 — Filesystem & Release Readiness

**Goal:** App is installable in `Program Files` without elevated privileges and behaves correctly on a clean machine.

**Why here:** Follows the Release Readiness Checklist M1 pattern applied to all mn-projects commercial tools.

**Topic notes:** Release checks are validation-focused and should not introduce new end-user features.

**Implementation notes:** Validate path discipline and first-run behavior in both dev and packaged modes.

- [x] `REL-01` Audit all disk reads/writes — confirm nothing writes beside the executable
- [x] `REL-02` Confirm `paths.py` covers all mutable files (`token.json`, `credentials.json`, `settings.json`, `alarms.json`); no ad hoc path construction anywhere
- [x] `REL-03` Test from a protected installation directory — confirm AppData writes work correctly
- [x] `REL-04` Test first-run on a clean machine (no token, no credentials) — verify auth flow guides the user
- [x] `REL-05` Wire `APP_VERSION` into main window title and About panel; keep changelog in `version.md`

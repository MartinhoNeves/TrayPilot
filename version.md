260410 — 1.1

- **Popup flyout layout (`popup.py`):** body is now split into 3 equal-height sections (events, unread mail, active alarms) using dynamic height allocation on resize/show instead of the previous 2-section layout.
- **Active alarms in popup (`popup.py`):** added a dedicated **ACTIVE ALARMS** block under the email list (max 5 enabled alarms), with horizontal separator, count label, and empty state text.
- **Popup visual consistency (`popup.py`):** section headers updated to orange accent styling where requested (including `SELECTED DAY EVENTS` and `ACTIVE ALARMS`, matching unread mail tone).
- **Tray context menu tab shortcuts (`tray.py`, `window_main.py`):** right-click menu actions now open the main window directly on a target tab via new `MainWindow.open_tab(...)` wiring.
- **Tray menu wording/structure (`tray.py`):** removed generic `Open`; renamed actions to tab names only (`Calendar`, `Emails`, `Alarms`, `Settings`, `About`); inserted separator between `About` and `Refresh`.

260409 — 1.0

- **Product rename:** **CalendarTray** → **TrayPilot** across UI strings, `paths.py` app data folder (`%LOCALAPPDATA%\mn-projects\TrayPilot\`), Windows **Run** registry value, PyInstaller **`TrayPilot.spec`** / **`spec/TrayPilot.spec.template`**, and docs. Existing data under `...\CalendarTray\` is not migrated automatically — copy or re-auth if needed. Local wheel path in `requirements.txt` still points at the repo directory name on disk.

- **M13 — Settings tab (`widget_settings.py`, `settings.py`, `window_main.py`):** single **Settings** tab after Alarms — appearance (dark/light + always-on-top), Gmail awareness + **Check every** (same `NoButtons` spin + 20×14 ▲/▼ pattern as the event form), default alarm sound (`.wav` from `Assets/`) + default snooze (5/10/15/30 min), tray balloon toggles for new mail and alarms, **Launch at Windows startup** (`windows_startup.py` / HKCU `Run`). Status-bar theme and pin controls removed; Emails tab is inbox-only (mail prefs live here). **Display version:** `APP_VERSION` in `main.py` (About tab); this file is the human changelog only.
- **M14 — About tab (`widget_about.py`, `dialog_about.py`):** **About** tab after Settings; shared **`AboutPanel`** (logo `Assets/app.png`, `ABOUT_TITLE` / `ABOUT_BODY`, version string); tray **About** menu entry removed. **`AboutDialog`** remains in `dialog_about.py` for optional use but is not wired to the tray.
- **Main window tab wiring:** order **Calendar → Emails → Alarms → Settings → About**; `QTabWidget.blockSignals` while building tabs plus initial `_settings_tab_index` / `_about_tab_index` to avoid a re-entrant `currentChanged` crash before indices are assigned.
- **Settings layout pass:** Appearance on one row (theme, always-on-top, startup); Alarms (sound + snooze combos) and Notifications (both balloon checkboxes) each on one row; startup checkbox moved out of a separate section.
- **New mail audio:** on new unread mail (with Gmail awareness on), **`tray.py`** plays **`email_event.wav`** (`SOUND_EMAIL`); tray balloon for new mail still follows the Settings toggle.
- **Version packaging:** dropped **`version_info.py`** and parsing **`version.md`** at runtime. The shipped version string is **`APP_VERSION`** in **`main.py`** (bumped manually); **`QApplication.setApplicationVersion`** uses the same value. Fewer loose files in PyInstaller **`_internal`**, and the About tab still shows the correct version in compiled builds without bundling `version.md`.
- **Calendar tab layout (`window_main.py`):** agenda + slide-in event form column vs month **`CalendarWidget`** use a fixed **50 / 50** `QHBoxLayout` stretch (replacing the old **65 / 35** bias) so the calendar stays half the tab width whether **New Event / Edit** is open or closed.

260409 — 0.1.3

- **M11 — Gmail awareness (`gmail_client.py`, `google_client.py`, `settings.py`, `tray.py`, `popup.py`, `main.py`):** `gmail.modify` scope; UI-independent `GmailClient` with polling, unread count + `messages_changed`, tray tooltip/toast on new mail; `credentials` + `revoke_and_reauth()` on `GoogleClient`; settings `mail_awareness_enabled` / `mail_poll_interval_minutes`.
- **M12 — Inbox read & manage:** `widget_email_row.py` (`EmailRow`), `dialog_email_reader.py` (plain-text body, mark-read on open, Trash); `GmailClient` batch metadata fetch (3 round-trips); `get_message_body`, `trash_message`, `mark_as_read` with instant local list updates; Emails tab live list + popup scroll list (taller flyout).
- **Emails tab UX:** main-window tab order **Calendar → Emails → Alarms**; “Check every” uses `NoButtons` spinbox + visible `▲`/`▼` `QToolButton`s; optional row checkboxes + **Trash selected** (before Open Gmail) with confirm; popup rows stay checkbox-free (`selectable=False`).
- **Trust notice removed:** deleted `trust_notice.py` and `trust_notice_ack` settings; startup one-shot and tray **Trust Notice** replaced by **`dialog_about.py`** + tray **About** (`ABOUT_TITLE` / `ABOUT_BODY` editable at top of file).

260409 — 0.1.2

- **M9 implemented end-to-end (`window_main.py`, `widget_event_list.py`, `panel_event_form.py`):** slide-in event form now fully wired for add/edit/delete with Google Calendar CRUD, confirmation on delete, inline API error handling, and roadmap `FORM-01`..`FORM-10` marked done in `Todo.md`.
- **Form behavior + UX flow:** calendar click no longer auto-opens form; `+ New Event` opens form using currently selected calendar date; `Today` button added beside `+ New Event` to jump calendar month/year and selection to today.
- **Event form fields expanded:** title/date/start/end/colour/description + recurrence (`No recurrence`, `Daily`, `Monthly`, `Yearly`) + reminder editing (`Default`/`None`/`Notification`/`Email` with minutes) mapped to Google Calendar `recurrence` and `reminders` payloads for both create and update.
- **Validation improvements:** creating new events in past dates now shows warning and is blocked.
- **Colour picker improvements:** per-item colour swatches added inside combobox list; removed external right-side swatch; light-mode combobox background/list rendering corrected.
- **Calendar readability:** weekday header/day-label colors in dark mode changed from dim to active/readable tone.
- **Layout responsiveness overhaul:** left agenda/form area now expands responsively (biased ~65/35 vs calendar), and open form width is dynamic; latest adjustment sets form to occupy ~50% of agenda area when open, with inner content no longer constrained by old fixed-width bottlenecks.
- **Spinner controls reliability fix:** replaced problematic native up/down hit areas on time/reminder controls with explicit `▲`/`▼` buttons (auto-repeat), ensuring both increment and decrement work reliably in dark/light themes.

260408 — 0.1.1

- **`widget_calendar.py` — year combobox (rework):** replaced the built-in `QSpinBox` year editor with a proper `QComboBox` (2010–2040). Previous attempts to manipulate Qt's internal nav bar widgets caused segfaults (`setParent(None)`) or styling cascade failures. Final approach: hide Qt's nav bar entirely (`setNavigationBarVisible(False)`) and replace it with a custom nav bar (`◄ | Month ▼ | Year ▼ | ►`) owned by a `QWidget` wrapper (`CalendarWidget`). The inner `_InnerCalendar(QCalendarWidget)` handles `paintCell` and dots; the wrapper proxies all signals and methods used by `window_main.py`. No Qt-internal widget manipulation.

- **M8 — Calendar date selection** (`window_main.py`, `widget_event_list.py`): click a calendar day filters the agenda to that day; click the same day again clears the filter; calendar click stores a form-prefill date for M9.
- **`widget_calendar.py` — year picker:** built-in year `QSpinBox` is hidden; a nav-bar `QToolButton` (`yearPickerBtn`) opens a **top-level** 5×5 year grid (`YearPickerPopup`) with ▲/▼ window shifts, avoiding Z-order and event-filter issues with Qt’s internal editor.
- **`popup.py` / `tray.py`:** removed **+ New Event** from the tray flyout; footer controls are **Previous Event**, **Today**, and **Next Event** (event-based navigation + jump back to today).
- **`Todo.md`:** M7 path checklist refined; M8 marked complete; TRAY-06 rewritten for the new popup footer behavior.
- Calendar navigation arrows in `widget_calendar.py` were reworked to use Unicode triangles (`◀` / `▶`) so theme color applies reliably in both dark/light modes.
- Arrow size was increased (~75%) for better visibility (`qt_calendar_prevmonth` / `qt_calendar_nextmonth` styling).
- Tray activation behavior in `tray.py` was fixed to prevent popup flicker on double-click:
  - single-click popup is delayed via `QTimer` debounce,
  - double-click cancels pending single-click action,
  - opening main window now hides popup first.
- Roadmap updated in `Todo.md` with a new milestone:
  - `M11 — Gmail New Mail Awareness` (`MAIL-01` … `MAIL-09`)
  - downstream milestones renumbered (`M12`, `M13`) and TOC updated.

260408 — 0.1.0 (pre-release)

Roadmap position per `Todo.md`: snapshot only — see newer entries above for current state.

---

### M1 — Infrastructure & Google Auth (done)

- Project layout, `requirements.txt` (PyQt6 commercial wheel, Google APIs, `platformdirs`)
- `paths.py`: AppData data dir, `token.json`, `settings.json`, `alarms.json` path, assets dir, `credentials.json`
- `google_client.py`: `get_events`, `create_event`, `update_event`, `delete_event`, in-memory cache, `refresh()`; OAuth2 browser flow; token refresh / re-auth; Qt signals (`auth_required`, `auth_success`, `error`, **`ready`** when service is built)

### M2 — System Tray & Popup Flyout (done)

- `tray.py`: tray icon, single-click popup / double-click main window, context menu Open · Refresh · Quit, `ready`-driven refresh of popup and visible window
- `popup.py`: frameless anchored flyout, focus-loss close, today’s events + urgent (30-day) section, styling and cards; footer **Previous Event / Today / Next Event** for event-to-event navigation

### M3 — Full Window Shell & Layout (done)

- `window_main.py`: `QMainWindow` ~780×520, Calendar / Alarms tabs (Alarms page empty stub), split agenda + calendar, status bar (connection + last sync), month change + `showEvent` → fetch and populate list + calendar dots
- `widget_event_list.py`: grouped-by-date agenda, colour dot · time · title, row selection shows Edit/Delete, **+ New Event** emits `new_event_requested` (not connected in `MainWindow` yet — M9)
- `widget_calendar.py`: custom `paintCell` dark calendar, orange/red dots for events/urgent

### M4 — Calendar Widget & Date Selection (done)

- `CAL-01` — dots under dates for events and urgent events
- `CAL-02`–`CAL-04` — calendar day click filters list (toggle clears); form-prefill stub for M9; custom year picker via `yearPickerBtn` + `YearPickerPopup`

### M5 — Slide-in Event Form & CRUD (not started)

- `panel_event_form.py` exists as an **empty stub** (`EventFormPanel` minimal `QWidget`); no animation, fields, or API wiring
- Edit/Delete handlers in `EventListWidget` are `pass` placeholders

### Alarms, theme polish, release (open per `Todo.md`)

- **M9** slide-in event form & CRUD; **M10** alarms; **M12** visual polish; **M13** release checks — not covered by this version bump
- Version string not wired into window title (still `"TrayPilot"`) or About dialog

### Build & run

- PyInstaller config: `TrayPilot.spec`, entry `main.py`, onedir, no console
- `Assets/app.ico` used for app/tray/window icons

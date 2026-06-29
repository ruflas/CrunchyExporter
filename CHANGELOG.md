# Changelog

All notable changes to CrunchyExporter GUI will be documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [1.3.0] — 2026-06-29

### Fixed
- **AniList/MAL export — wrong season overwritten**: Crunchyroll rarely puts
  the season number in the episode title, so exporting season 2+ of a show
  always matched and overwrote season 1's AniList/MAL entry. The exporter
  now follows the sequel relation chain to resolve the correct season entry.
- **AniList/MAL export — progress could be overwritten with stale data**:
  exports now check the existing remote progress first and skip the series
  instead of writing a lower episode count or status.

### Fixed
- **MAL export — search fails on long titles**: MAL's `/anime` search
  rejects queries past ~64 characters with `400 invalid q`, which happened
  routinely with Crunchyroll's long English subtitles (e.g. "Hensuki - Are
  you willing to fall in love with a pervert, as long as she's a cutie?").
  The search now retries with the part before a subtitle separator, then a
  hard truncation, before giving up.
- **Missing dependencies**: `click` and `rich` are used by the bundled
  `src/main.py` (invoked by the Schedule tab when running from source) but
  were never declared in `requirements.txt`, breaking scheduled syncs on a
  fresh install.

### Added
- **Export preview & confirmation**: before writing to AniList/MAL, a dry-run
  pass shows exactly what would change. Confirmation is a non-modal panel
  under the log (not a blocking dialog), so the log stays scrollable while
  reviewing. You can apply every change at once, or review and
  approve/skip each series individually per target.
- **"Only since" date filter**: optionally export only episodes watched on
  or after a given date — useful if older history is already tracked
  elsewhere (e.g. MALSync).
- **My Library — manual edit**: a pencil button per series opens an editor
  for title, season number and progress. Saved corrections are stored
  separately from the raw watch history and can be reverted.
- **Settings tab — version footer**: shows the current app version at the
  bottom, linking to the GitHub releases page, and highlights when a newer
  release is available (checked once on startup).
- **Video tutorial** in the README.

---

## [1.2.0] — 2026-06-19

### Added
- **MAL Settings — App Type selector**: a new checkbox lets you mark your
  MyAnimeList app as App Type `web`, revealing a Client Secret field. App Type
  `other` (the simpler, recommended option) still needs only the Client ID.

### Fixed
- **MAL OAuth — Client Secret never sent**: the Settings dialog always
  exchanged the authorization code with an empty client_secret, so MAL `web`
  type apps failed authentication even with a valid access token. The secret
  entered in Settings is now passed through to the token exchange.

---

## [1.1.0] — 2026-05-20

### Fixed
- **Schedule tab — GUI freeze**: creating or removing a scheduled task blocked
  the main thread while `schtasks` ran. All subprocess calls now run in daemon
  threads and marshal results back via `frame.after(0, callback)`.
- **MAL export — early stop on HTTP errors**: the exporter now continues with
  remaining entries instead of stopping at the first HTTP error.
- **MAL search — silent failures**: `search_anime()` now reports detailed error
  messages when a request fails instead of returning an empty result.

### Added
- **Export log persistence**: the sync/export log is now written to disk so
  history survives application restarts.
- **Unit tests and CI**: 73 tests across auth, history store, exporters and
  export log, with a GitHub Actions workflow.

---

## [1.0.1] — 2026-05-14

### Fixed
- **Frozen exe — config and data paths**: when running as a PyInstaller bundle,
  `config.yaml` and `data/` were being written to `sys._MEIPASS` (PyInstaller's
  temp extraction dir) and lost on every close. They now resolve correctly to the
  directory containing the executable.
- **Frozen exe — schedule command**: the scheduled task was generating a path to
  `src/main.py` inside the temp extraction dir (e.g.
  `C:\Users\<user>\AppData\Local\Temp\_MEI...\src\main.py`) which breaks after
  the dir is cleaned up. When frozen, the command is now
  `CrunchyExporter.exe --headless-sync --target <target>`.
- **Frozen exe — tray "Sync Now"**: same fix as schedule; tray sync now calls
  `CrunchyExporter.exe --headless-sync` instead of the temp path.

### Added
- `gui/paths.py`: `resource_root()` / `data_root()` helpers to distinguish
  bundled resources from user-writable files in both frozen and script modes.
- `--headless-sync` mode in `main.py` for scheduled/tray sync when running
  as a frozen executable.

---

## [1.0.0] — 2026-05-13

### Added
- **Sync tab** — fetch Crunchyroll watch history with per-page progress and cancel support
- **My Library tab** — scrollable table of all watched series with episode counts
- **Export tab** — export to AniList, MyAnimeList and local MAL XML with per-target status cards
- **Schedule tab** — register/remove a daily auto-sync task (Windows Task Scheduler / crontab)
- **Settings tab** — full config editor with inline OAuth flows for AniList and MAL
- **Status bar** — at-a-glance indicators for cookie, history, AniList, MAL and XML readiness
- **System tray** (opt-in) — minimize to background with "Sync Now" and toast notifications
- **i18n** — English and Spanish; add new languages by dropping a JSON file in `locales/`
- Custom window icon (PNG → ICO auto-generated on first run)
- Dark mode UI with CustomTkinter

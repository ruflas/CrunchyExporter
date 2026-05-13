# Changelog

All notable changes to CrunchyExporter GUI will be documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

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

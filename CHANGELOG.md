# Changelog

All notable changes to CrunchyExporter GUI will be documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [1.0.0] — 2026-05-13

### Added
- **Sync tab** — fetch Crunchyroll watch history with per-page progress and cancel support
- **My Library tab** — scrollable table of all watched series with episode counts
- **Export tab** — export to AniList, MyAnimeList and local MAL XML with per-target status cards
- **Schedule tab** — register/remove a daily auto-sync task (Windows Task Scheduler / crontab); delegates to the CLI's `sync` command
- **Settings tab** — full config editor with inline OAuth flows for AniList and MAL
- **Status bar** — at-a-glance indicators for cookie, history, AniList, MAL and XML readiness
- **System tray** (opt-in) — minimize to background; "Sync Now" delegates to CLI `sync`; toast notifications
- **i18n** — English and Spanish included; add new languages by dropping a JSON file in `locales/`
- **Two-source library strategy** — uses live `CrunchyExporter-cli` source when present as sibling folder; falls back to bundled `src/` for standalone distribution
- Custom window icon (PNG → ICO auto-generated on first run)
- Dark mode UI with CustomTkinter

### Notes
- Requires [CrunchyExporter-cli](https://gitea.homelab/ruflas/crunchyexporter-cli) as a sibling folder for full functionality (scheduled tasks, tray sync)
- Bundled `src/` copy included for standalone use; sync it before each release with:
  `Copy-Item -Path ..\CrunchyExporter-cli\src -Destination .\src -Recurse -Force`

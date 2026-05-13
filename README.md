<p align="center">
  <img src="crunchyexporterbanner.png" alt="CrunchyExporter" width="300"/>
</p>

<h1 align="center">CrunchyExporter</h1>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/github/license/ruflas/CrunchyExporter" alt="License"></a>
  <a href="https://github.com/ruflas/CrunchyExporter/releases"><img src="https://img.shields.io/github/v/release/ruflas/CrunchyExporter" alt="Release"></a>
  <img src="https://img.shields.io/badge/python-3.11%2B-blue" alt="Python">
  <a href="https://github.com/ruflas/CrunchyExporter/releases/latest"><img src="https://img.shields.io/github/downloads/ruflas/CrunchyExporter/total" alt="Downloads"></a>
</p>

<p align="center">Fetches your Crunchyroll watch history and exports it to <b>AniList</b>, <b>MyAnimeList</b>, and a local <b>MAL-compatible XML</b> file.</p>

Exports include watch progress, series status (watching/completed), and real start/finish dates from your Crunchyroll history.

---

## What it does

1. **Sync** — fetches your full Crunchyroll watch history using the `etp_rt` session cookie
2. **Export** — pushes it to AniList and/or MyAnimeList via their APIs, or generates a local XML importable anywhere (AniList, Kitsu, etc.)
3. **Schedule** — registers a daily background task (Windows Task Scheduler / crontab) that runs automatically
4. **System tray** (optional) — keeps the app running in the background with a "Sync Now" shortcut

Built on the [CrunchyExporter-cli](https://github.com/ruflas/CrunchyExporter-cli) library, which is bundled in `src/`.

---

## Requirements

- Python 3.11+

---

## Installation

```bash
pip install -r requirements.txt
python main.py
```

Dependencies: `customtkinter`, `pillow`, `pystray`, `requests`, `pyyaml`

---

## Configuration

Copy `config.example.yaml` to `config.yaml` and fill in your values:

```yaml
locale: "en-US"

ui:
  language: "en"        # en | es | any file in locales/
  tray_enabled: false   # true to minimize to system tray on close

crunchyroll:
  etp_rt: ""            # session cookie — see the Sync tab for instructions

exporters:
  anilist:
    client_id: ""       # create an app at anilist.co/settings/developer
    access_token: ""    # obtained via the Settings tab
  mal:
    client_id: ""       # create an app at myanimelist.net/apiconfig
    access_token: ""    # obtained via the Settings tab
  mal_xml:
    path: "data/animelist.xml"

storage:
  path: "data/history.json"
```

All credentials can also be entered and saved directly from the **Settings** tab.

---

## Adding a language

1. Copy `locales/en.json` → `locales/<lang_code>.json`
2. Translate the values (do not change the keys)
3. Set `ui.language: "<lang_code>"` in `config.yaml` and restart
4. Submit a pull request — contributions welcome

Current languages: **English** (`en`), **Spanish** (`es`)

---

## Project structure

```
CrunchyExporter/
├── src/                  # bundled library copy (fallback for standalone use)
├── gui/
│   ├── app.py            # main window
│   ├── i18n.py           # locale loader
│   ├── tray.py           # system tray
│   ├── statusbar.py      # status bar
│   └── tabs/             # one module per tab
├── locales/
│   ├── en.json
│   └── es.json
├── main.py               # entry point
├── config.example.yaml
└── requirements.txt
```

---

## Related

- [CrunchyExporter-cli](https://github.com/ruflas/CrunchyExporter-cli) — CLI version / underlying library



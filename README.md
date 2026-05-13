<p align="center">
  <img src="crunchyexporterbanner.png" alt="CrunchyExporter" width="300"/>
</p>

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

## Tutorial

### 1. First-time setup

Open the **Settings** tab and fill in your credentials before doing anything else.

<!-- screenshot: settings tab -->

**Crunchyroll cookie (`etp_rt`)**

The app authenticates with Crunchyroll using a session cookie from your browser:

1. Log in to [crunchyroll.com](https://www.crunchyroll.com) in your browser
2. Press **F12** to open DevTools
3. Go to **Application** → **Cookies** → `https://www.crunchyroll.com`
4. Find the cookie named `etp_rt` and copy its value
5. Paste it in the **etp_rt Cookie** field in Settings and click **Save Settings**

> The cookie expires when you log out of Crunchyroll. If sync stops working, get a fresh one.

**AniList** *(optional)*

1. Go to [anilist.co/settings/developer](https://anilist.co/settings/developer) and create a new API client
2. Set the Redirect URI to `https://anilist.co/api/v2/oauth/pin`
3. Copy the **Client ID** into Settings
4. Click **Get Token** — your browser will open, authorize the app, then paste the token back

**MyAnimeList** *(optional)*

1. Go to [myanimelist.net/apiconfig](https://myanimelist.net/apiconfig) and create a new client
2. Set **App Type** to `web` and **Redirect URI** to `http://localhost`
3. Copy the **Client ID** into Settings
4. Click **Authorize MAL** and follow the instructions

---

### 2. Sync your watch history

Go to the **Sync** tab and click **Sync Now**.

<!-- screenshot: sync tab -->

The app will fetch your full Crunchyroll watch history and save it locally.
The first sync downloads everything; subsequent syncs only fetch new episodes.

---

### 3. Check your library

Open the **My Library** tab to see all the series from your history.

<!-- screenshot: library tab -->

---

### 4. Export

Go to the **Export** tab. Each card shows whether a target is configured and ready.

<!-- screenshot: export tab -->

Select the targets you want and click **Export**.
If a token is missing, the authorization flow starts automatically.

- **AniList** / **MyAnimeList** — updates your list with progress, status (watching/completed) and real dates
- **Local XML** — generates a MAL-compatible XML file you can import at myanimelist.net, AniList, Kitsu, etc.

---

### 5. Schedule automatic daily syncs *(optional)*

Go to the **Schedule** tab, pick a time, select export targets, and click **Create scheduled task**.

<!-- screenshot: schedule tab -->

The task runs silently every day at the chosen time even if the app is closed.

---

### 6. System tray *(optional)*

Enable **System tray** in Settings to keep the app running in the background when you close the window.
Right-click the tray icon to sync immediately or exit the app.

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



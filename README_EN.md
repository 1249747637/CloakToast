# CloakToast

English | [中文](README.md)

Multi-browser instance manager built on [cloakbrowser](https://pypi.org/project/cloakbrowser/) (anti-fingerprint Chromium powered by Playwright). Create multiple browser profiles with independent fingerprints, proxies, and traffic policies. Launch and stop them on demand — all profiles share a single set of bookmarks.

## Features

- **Multi-Profile Management** — Each profile gets its own user_data_dir, proxy, and fingerprint config; drag-and-drop reordering
- **Anti-Fingerprint Browser** — Full coverage: screen resolution, CPU/GPU, WebRTC, geolocation, User-Agent, fonts, and more
- **Proxy & Chain Proxy** — HTTP/SOCKS5 proxy + relay proxy support (e.g. mihomo → target proxy, two-hop chain)
- **Resource Blocking** — Block video streams (MP4/HLS/DASH), limit image size to save proxy bandwidth
- **WebRTC Leak Protection** — Three modes: custom IP / mask (10.0.0.1) / fully disabled
- **GeoIP Auto-Detection** — Automatically sets timezone, locale, and geolocation based on proxy exit IP
- **Shared Bookmarks** — Centrally managed bookmarks, injected into Chromium's native bookmark bar on launch
- **Tag Filtering** — Custom tags with multi-tag AND filtering
- **Import/Export** — Profile configs as JSON, supports cross-machine migration

## Getting Started

### Prerequisites

- Python 3.10+
- Node.js 18+

### Quick Start (Windows)

```bat
start.bat
```

This will: install dependencies → kill any process on port 8765 → build the frontend → start the server in the background → open `http://localhost:8765` once ready.

### Development Mode

```bash
# Install dependencies
pip install -r backend/requirements.txt
pip install "cloakbrowser[geoip]"   # optional, enables GeoIP auto-detection
cd frontend && npm install

# Terminal 1 — backend (hot reload)
uvicorn backend.main:app --host 0.0.0.0 --port 8765 --reload

# Terminal 2 — frontend (HMR)
cd frontend && npm run dev
# → http://localhost:5173, API proxied to :8765
```

## Testing

```bash
# Unit + integration tests (~2s)
python -m pytest tests/ -v

# Full suite including real Chromium E2E (~55s)
CLOAKTOAST_E2E=1 python -m pytest tests/ -v
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python · FastAPI · SQLAlchemy · SQLite · uvicorn |
| Frontend | Vite · React 18 · TypeScript · Ant Design 5 · react-router |
| Browser Engine | cloakbrowser (Playwright Chromium) |
| Platform | Windows (primary); Linux / macOS partial support |

## Project Structure

```
CloakToast/
├── backend/
│   ├── main.py                # FastAPI application entry point
│   ├── database.py            # SQLite + SQLAlchemy + auto-migration
│   ├── models.py              # ORM models
│   ├── schemas.py             # Pydantic validation schemas
│   ├── routers/
│   │   ├── profiles.py        # Profile CRUD / reorder / import & export
│   │   ├── instances.py       # Browser instance launch / stop
│   │   ├── bookmarks.py       # Shared bookmarks CRUD
│   │   └── system.py          # System info / update / license
│   └── services/
│       ├── browser.py         # Process management
│       ├── browser_worker.py  # Browser subprocess
│       └── chain_proxy.py     # SOCKS5 chain proxy
├── frontend/src/
│   ├── pages/
│   │   ├── Profiles/          # Profile management (card grid + drag-and-drop)
│   │   ├── Bookmarks/         # Shared bookmarks table
│   │   └── Settings/          # Settings page
│   ├── api/                   # API client modules
│   └── components/            # Shared components
├── tests/                     # Test suite
├── data/                      # Runtime data (gitignored)
└── start.bat                  # Windows one-click launcher
```

## Architecture

```
uvicorn (FastAPI :8765)
 └── browser.py: process manager + watcher
      └── subprocess: browser_worker.py
           └── [optional] chain_proxy (relay → target)
                └── cloakbrowser → Chromium
```

Browser instances run as independent subprocesses. The main process monitors their lifecycle via watcher tasks. Chain proxy supports a relay → target two-hop path (e.g. mihomo → target proxy → Internet).

## API Overview

| Method | Path | Description |
|--------|------|-------------|
| GET/POST | `/api/profiles` | List / create profiles |
| PUT/DELETE | `/api/profiles/{id}` | Update / delete |
| POST | `/api/profiles/{id}/duplicate` | Duplicate |
| POST | `/api/profiles/reorder` | Batch reorder |
| GET/POST | `/api/profiles/export` `/import` | Import & export |
| POST | `/api/instances/launch` | Launch browser |
| POST | `/api/instances/stop/{id}` | Stop browser |
| GET/POST/PUT/DELETE | `/api/bookmarks` | Bookmarks CRUD |
| GET | `/api/system/info` | Version + license |

## Data Directory

Runtime data is stored in `data/` (gitignored):

```
data/
├── cloaktoast.db          # SQLite database
├── config.json            # License key and other config
└── profiles/<id>/         # Per-profile user_data_dir
    ├── Default/Bookmarks  # Chromium bookmarks file, written on launch
    └── _cloaktoast_worker.log
```

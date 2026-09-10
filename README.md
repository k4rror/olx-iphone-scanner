# olx-iphone-scanner

[![CI](https://github.com/k4rror/olx-iphone-scanner/actions/workflows/ci.yml/badge.svg)](https://github.com/k4rror/olx-iphone-scanner/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

**English** | [Polski](README.pl.md) | [Deutsch](README.de.md) | [Українська](README.uk.md) | [Беларуская](README.be.md)

Scans iPhone listings on OLX Poland (`olx.pl`) and stores structured appraisals in a local SQLite database. Search pages are fetched with a Chrome 120 TLS fingerprint, accessories and non-Apple listings are dropped by regex heuristics, and the remaining offers are sent to DeepSeek to extract model, storage, battery health, damage and lock status.

Two front ends share the same database: a Rich terminal UI (`olx-scanner`) and a FastAPI/Jinja2 web dashboard (`olx-dashboard`).

## Quick start

```bash
git clone https://github.com/k4rror/olx-iphone-scanner.git
cd olx-iphone-scanner
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\Activate.ps1
pip install -e .
olx-scanner
```

The first run starts an interactive wizard (language, DeepSeek API key, proxy mode, page count) and writes `scanner_config.json`. A DeepSeek API key is required.

## Features

- **TLS fingerprinting:** `tls-client` is configured with a Chrome 120 profile and emulated headers, so requests look like a normal browser without a CAPTCHA-solving service.
- **Proxy pool:** proxy lists are tested asynchronously against OLX over HTTPS tunnels and ranked before the scan starts. A static proxy, a local rotator, or direct TLS are all supported.
- **Heuristic pre-filter:** regex rules reject cases, boxes, chargers, spare parts and other brands (Samsung, Xiaomi, Pixel) before any DeepSeek request, which keeps token usage down.
- **DeepSeek extraction:** each listing is parsed into typed fields (model, storage in GB, color, battery health percent, condition, damage details, Face ID, iCloud lock) plus a one-sentence verdict. Malformed JSON responses are repaired and validated with Pydantic.
- **Deduplication and early stopping:** page fingerprints are computed from the MD5 hash of the listing IDs on that page. If page 1 is unchanged since the last cycle, or a later page adds zero new offers, the scan stops early.
- **Terminal dashboard:** a Rich Live view with KPI counters, a table of recently analyzed offers, progress and a rolling event log. `--inline` disables the alternate screen buffer for CI or non-interactive shells.
- **Web dashboard:** FastAPI and Jinja2 pages for scanner control, the offers table (filters, sorting, favorites, notes), analytics and CSV export.
- **Storage:** SQLite in WAL mode with indexed columns, safe for concurrent writers.
- **Internationalization:** UI strings and AI prompts in English, Polish, Ukrainian, German and Belarusian.

## Installation

### Requirements

- Python 3.10 or newer.
- A DeepSeek API key from [platform.deepseek.com](https://platform.deepseek.com/).
- Network access to `olx.pl`.

### Install

```bash
git clone https://github.com/k4rror/olx-iphone-scanner.git
cd olx-iphone-scanner
python -m venv .venv

# Linux / macOS:
source .venv/bin/activate
# Windows (PowerShell):
.venv\Scripts\Activate.ps1

pip install -e .
```

The base install includes the web dashboard dependencies (`fastapi`, `uvicorn`, `jinja2`). To run the test suite and linter as well:

```bash
pip install -e ".[dev]"
```

## Usage

### Terminal scanner

```bash
# Interactive wizard (first run, or after deleting scanner_config.json)
olx-scanner

# Re-run the wizard at any time
olx-scanner --setup

# One cycle over 3 pages in a chosen region, no prompts
olx-scanner --non-interactive --pages 3 --region mazowieckie

# Continuous monitoring: 5 pages, then wait 60 seconds and repeat
olx-scanner --pages 5 --watch --interval 60

# Force the interface and AI prompt language
olx-scanner --lang pl

# Proxy: a single endpoint, or a tested list from a file
olx-scanner --proxy http://user:pass@127.0.0.1:8080
olx-scanner --proxy-file proxies.txt --min-proxies 20

# Non-interactive output for CI or logging
olx-scanner --inline
```

Region may also be passed as `--wojewodztwo`. Accepted values are voivodeship slugs such as `mazowieckie`, `slaskie`, `malopolskie`; omit it to scan all of OLX Poland.

### CLI options

| Flag | Description | Default |
| :--- | :--- | :--- |
| `--setup`, `--reconfigure` | Run the interactive setup wizard | `False` |
| `--non-interactive`, `-y` | Skip pre-flight prompts and use the stored config | `False` |
| `--lang` | Interface and prompt language (`en`, `pl`, `uk`, `de`, `be`) | config, else `pl` |
| `--region`, `--wojewodztwo` | Voivodeship slug, e.g. `mazowieckie` | all regions |
| `--api-key` | DeepSeek API key override | config / `.env` |
| `--model` | DeepSeek model identifier | `deepseek-v4-flash-vision-exp` |
| `--proxy` | Single static proxy (`http://host:port`) | `None` |
| `--proxy-file`, `-pf` | Proxy list file (`.txt` or `.json`) | `None` |
| `--min-proxies` | Minimum valid proxies required in the pool | `15` |
| `--proxy-workers` | Threads used to verify proxies | `150` |
| `--pages` | Search pages scanned per cycle | `3` |
| `--threads` | Concurrent threads for AI analysis | `8` |
| `--watch` | Repeat the scan in a loop | `False` |
| `--interval` | Seconds between cycles in watch mode | `120` |
| `--inline` | Scrolling output instead of the full-screen TUI | `False` |
| `--log-file` | Execution log path | `olx_scanner.log` |

### Web dashboard

```bash
olx-dashboard
```

This serves the dashboard on `http://127.0.0.1:8000` and opens it in the default browser. The entry point accepts:

| Flag | Description | Default |
| :--- | :--- | :--- |
| `--host` | Bind address | `127.0.0.1` |
| `--port` | Listening port | `8000` |
| `--db` | Path to the SQLite database file | `olx_iphones.db` |
| `--no-browser` | Do not open the browser on startup | `False` |

Pages: `/scanner` (start/stop the scan), `/offers` (filter, sort, favorite, annotate, delete, export CSV), `/analytics` (per-model price statistics and margin over the market average).

The dashboard exposes a JSON API over the same data. The main routes:

| Method | Route | Purpose |
| :--- | :--- | :--- |
| `GET` | `/api/stats` | Database KPIs and analytics summary |
| `GET` | `/api/offers` | Paged, filtered offer list |
| `GET` | `/api/offers/{olx_id}` | Single offer details |
| `POST` | `/api/offers/{olx_id}/favorite` | Toggle the favorite flag |
| `PATCH` | `/api/offers/{olx_id}/notes` | Save user notes |
| `DELETE` | `/api/offers/{olx_id}` | Delete an offer |
| `GET` | `/api/export` | CSV export of the current filter |
| `GET` | `/api/models/stats` | Price and battery statistics for a model |
| `GET` | `/api/scanner/status` | Current scanner snapshot |
| `POST` | `/api/scanner/start` | Start a scan cycle |
| `POST` | `/api/scanner/stop` | Stop the running scan |
| `GET` | `/api/scanner/probe` | Listing count and page count for a region |

### Configuration

`.env` in the project root:

```env
DEEPSEEK_API_KEY=your_deepseek_api_key_here
OLX_PROXY=
```

`scanner_config.json`, written by the wizard and editable by hand:

```json
{
  "language": "pl",
  "api_key": "your_deepseek_api_key_here",
  "model": "deepseek-v4-flash-vision-exp",
  "proxy_mode": "rotator",
  "custom_proxy": "http://127.0.0.1:8080",
  "proxy_file": null,
  "region": "mazowieckie",
  "pages": 3,
  "threads": 8,
  "watch": false,
  "interval": 120
}
```

Command-line flags take precedence over the config file, which takes precedence over `.env`.

## Database schema

SQLite, WAL mode, created automatically at `olx_iphones.db`.

`iphone_offers`:

| Column | Notes |
| :--- | :--- |
| `id` | Primary key |
| `olx_id` | Unique OLX listing ID, indexed |
| `url`, `title`, `price`, `currency`, `location`, `posted_at`, `description`, `scraped_at` | Raw listing data |
| `ai_analyzed` | `0` = pending, `1` = analyzed, indexed |
| `model_name`, `storage_gb`, `color` | Normalized device data |
| `battery_health_pct` | Integer, `NULL` when the seller did not state it |
| `condition_state`, `is_damaged`, `damage_details` | Condition and defects, indexed on `is_damaged` |
| `face_id_working`, `icloud_clean` | `1` / `0` / `NULL` |
| `ai_summary` | One-sentence verdict |
| `ai_raw_json` | Raw DeepSeek response |
| `is_favorite`, `user_notes` | Added by the web dashboard |

`scanned_pages`: `page_number`, `scanned_at`, `offers_total`, `new_offers`, `fingerprint` (MD5), `duration_s`. Used by the early-stopping check.

## Testing

```bash
pip install -e ".[dev]"
ruff check .
pytest tests/unit -v
```

Unit tests run against fixtures and need no network access or API key. CI runs `ruff check .` and `pytest tests/unit/ -v` on Python 3.10, 3.11 and 3.12.

## Limitations

- The web dashboard runs a single scan cycle. Continuous watch mode is disabled in the web UI (`WATCH_MODE_ENABLED = False` in `src/olx_scanner/web/app.py`); use the CLI `--watch` flag instead.
- State is a single local SQLite file. There is no server deployment, no authentication and no multi-user support; the dashboard binds to `127.0.0.1` by default.
- The scraper depends on OLX HTML structure and will break when the markup changes. There is no offline mode or bundled dataset.
- A paid DeepSeek API key is required for analysis. Listings are still stored without it, but stay unanalyzed.
- This project is not affiliated with OLX. Respect the OLX terms of service and your local regulations when scraping.

## Contributing

Fork the repository, create a topic branch, and make sure `ruff check .` and `pytest tests/unit -v` pass before opening a pull request.

## License

MIT. See [LICENSE](LICENSE).

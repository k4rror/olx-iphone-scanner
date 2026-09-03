# 📱 OLX iPhone Scanner & DeepSeek AI Appraiser

[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![Terminal UI](https://img.shields.io/badge/UI-Rich%20TUI-cyan.svg)](https://github.com/Textualize/rich)
[![AI Engine](https://img.shields.io/badge/AI-DeepSeek-magenta.svg)](https://www.deepseek.com/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

An intelligent, real-time terminal scanner and deal appraiser for iPhone listings on **OLX Poland** (`olx.pl`). 

Finding genuine iPhone bargains on OLX is notoriously tedious: sellers frequently hide critical battery health metrics in informal descriptions (e.g. *"kondycja 84%"*, *"nowa bateria zamiennik"*), fail to disclose locked iCloud accounts, or flood categories with accessories (cases, boxes, screen protectors).

**OLX iPhone Scanner** automates this entire pipeline: it scrapes fresh listings with browser-grade TLS fingerprinting, filters out junk with high-speed heuristics, and uses **DeepSeek AI** to evaluate technical conditions and battery health into a structured SQLite database and an interactive, real-time terminal dashboard.

---

## 🌟 Key Features

- **⚡ Cloudflare & Anti-Bot Bypass:** Utilizes `tls-client` configured with Chrome 120 TLS fingerprints, custom headers, and request emulation to access OLX without blocks or CAPTCHAs.
- **🧠 DeepSeek AI Appraisal:** Extracts exact device specs from unformatted, raw Polish descriptions:
  - Exact model & storage capacity (GB)
  - Color
  - Battery Health percentage (`battery_health_pct`)
  - Physical & functional condition
  - Damage detection & defect descriptions
  - Face ID & iCloud lock status
  - Concise one-sentence appraiser verdict
- **🛡️ Token-Saving Heuristic Pre-filter:** Filters out phone cases, boxes, replacement parts, chargers, and non-Apple brands (Samsung, Xiaomi, Pixel) using deterministic regex rules **before** making AI API calls.
- **🔄 Smart Proxy Management & Rotator Support:**
  - Direct TLS mode (uses your machine's connection).
  - Native integration with local rotators (auto-detects `http://127.0.0.1:8080`).
  - Asynchronous multi-threaded proxy pool testing (validates HTTPS tunnels directly to OLX).
- **📊 Interactive Rich Live TUI:** Real-time terminal interface displaying:
  - KPI cards (Total scanned, AI-analyzed, Healthy, Damaged, Skipped duplicates).
  - Live table of newly analyzed iPhone listings.
  - Scan progress indicators and countdown timers for watch mode.
  - Rolling real-time event log.
- **⚡ Anti-Duplicate & Early-Stopping Engine:** Generates MD5 page fingerprints and checks against local SQLite history. If a page contains 100% known listings, the scanner triggers early stopping to avoid redundant requests.
- **🌐 Native Multi-Language Support:** Full localization for UI and AI prompts in **5 languages**:
  - 🇬🇧 English (`en`)
  - 🇵🇱 Polish (`pl`)
  - 🇺🇦 Ukrainian (`uk`)
  - 🇩🇪 German (`de`)
  - 🇧🇾 Belarusian (`be`)
- **💾 Local SQLite Storage with WAL:** Persists all raw offers and AI appraisal outputs safely with WAL (Write-Ahead Logging) and concurrency-safe connection handling.

---

## 🏗️ Architecture & Pipeline

```text
  [ OLX.pl iPhone Feed ]
            │
            ▼ (TLS Client - Chrome 120 Fingerprint / Proxy Pool)
  [ Scraper & HTML Parser ]
            │
            ▼ (MD5 Page Fingerprint / Duplicate Check)
  [ SQLite Deduplication ] ────► (Already analyzed? -> Skip)
            │
            ▼
  [ Heuristic Filter ] ────► (Case / Box / Android detected? -> Discard)
            │
            ▼ (Threaded AI Queue)
  [ DeepSeek API Analyzer ]
            │
            ├─► Auto-repair JSON & Pydantic Validation
            ├─► Save to SQLite Database (`olx_iphones.db`)
            └─► Push to Live Rich Dashboard & Log file
```

---

## 📦 Installation

### 1. Prerequisites
- Python **3.10** or newer installed.
- DeepSeek API key (obtainable at [platform.deepseek.com](https://platform.deepseek.com/)).

### 2. Clone and Setup Environment

```bash
git clone https://github.com/k4rror/olx-iphone-scanner.git
cd olx-iphone-scanner

# Create and activate virtual environment
python -m venv .venv

# On Linux/macOS:
source .venv/bin/activate

# On Windows (PowerShell):
.venv\Scripts\Activate.ps1
```

### 3. Install Dependencies

Install the project in editable mode with development tools:

```bash
pip install -e .
```

Or install dependencies directly:

```bash
pip install -r pyproject.toml
```

---

## 🚀 Quick Start

### First Launch & Interactive Wizard

Simply run the CLI entry point:

```bash
olx-scanner
```

On your first run, the interactive configuration wizard will guide you through:
1. Preferred interface and prompt language (`en`, `pl`, `uk`, `de`, `be`).
2. DeepSeek API Key input.
3. Connection mode (Direct TLS, Local Rotator on `127.0.0.1:8080`, or custom proxy list).
4. Default scan depth (number of pages) and background watch mode settings.

Configuration is saved automatically to `scanner_config.json`. You can re-run the wizard at any time:

```bash
olx-scanner --setup
```

---

## ⚙️ Configuration

### 1. Environment Variables (`.env`)
You can store your API key in a `.env` file in the project root:

```env
DEEPSEEK_API_KEY=your_deepseek_api_key_here
```

### 2. `scanner_config.json`
Generated by the wizard, customizable manually:

```json
{
  "language": "en",
  "api_key": "your_deepseek_api_key_here",
  "model": "deepseek-v4-flash-vision-exp",
  "proxy_mode": "rotator",
  "custom_proxy": "http://127.0.0.1:8080",
  "proxy_file": null,
  "pages": 3,
  "threads": 8,
  "watch": false,
  "interval": 120
}
```

---

## 💻 CLI Usage & Commands

### Basic Scan
Scans the first 3 pages and exits:
```bash
olx-scanner --pages 3
```

### Continuous Monitoring (Watch Mode)
Scans 5 pages, analyzes new offers, and waits 60 seconds before scanning again:
```bash
olx-scanner --pages 5 --watch --interval 60
```

### Change Language on the Fly
Run the interface and prompt appraisals in Polish or Ukrainian:
```bash
olx-scanner --lang pl
olx-scanner --lang uk
```

### Custom Proxy Configuration
Use a static proxy or a list of proxies from a text/JSON file:
```bash
# Single proxy:
olx-scanner --proxy http://user:pass@127.0.0.1:8080

# Proxy list file (tested automatically before scanning):
olx-scanner --proxy-file proxies.txt --min-proxies 20
```

### Inline Mode (for CI/CD or Non-Interactive Terminals)
Disables the alternate full-screen screen buffer:
```bash
olx-scanner --inline
```

---

## 📋 CLI Reference

| Option | Flag | Description | Default |
| :--- | :--- | :--- | :--- |
| **Setup** | `--setup`, `--reconfigure` | Launch the initial interactive setup wizard | `False` |
| **Language** | `--lang` | UI and AI language (`en`, `pl`, `uk`, `de`, `be`) | `en` |
| **API Key** | `--api-key` | Override DeepSeek API Key | Config / `.env` |
| **Model** | `--model` | DeepSeek model identifier | `deepseek-v4-flash-vision-exp` |
| **Pages** | `--pages` | Number of OLX search pages to scan per cycle | `3` |
| **Threads** | `--threads` | Concurrent threads for parallel AI analysis | `8` |
| **Watch Mode** | `--watch` | Enable continuous polling loop | `False` |
| **Interval** | `--interval` | Seconds to wait between cycles in watch mode | `120` |
| **Proxy** | `--proxy` | Single static proxy (`http://host:port`) | `None` |
| **Proxy File** | `--proxy-file`, `-pf`| Path to proxy list (`.txt` or `.json`) | `None` |
| **Min Proxies**| `--min-proxies` | Minimum valid proxies required in pool | `15` |
| **Proxy Workers** | `--proxy-workers` | Concurrency for initial proxy verification | `150` |
| **Inline View**| `--inline` | Run in standard scrolling mode (no TUI alt screen) | `False` |
| **Log File** | `--log-file` | Target file for comprehensive execution logs | `olx_scanner.log` |

---

## 🗄️ Database Schema (`olx_iphones.db`)

All scanned offers are stored in a local SQLite database with indexing and WAL mode enabled:

- **`iphone_offers`**:
  - `olx_id`: Unique OLX listing identifier.
  - `title`, `price`, `location`, `posted_at`, `description`, `url`.
  - `ai_analyzed`: Status flag (`0` = unanalyzed, `1` = analyzed).
  - `model_name`: Extracted model (e.g., `iPhone 13 Pro`).
  - `storage_gb`: Capacity (e.g., `128`, `256`).
  - `battery_health_pct`: Battery percentage integer (or `NULL` if not stated).
  - `condition_state`: Overall visual and technical condition.
  - `is_damaged`: Boolean flag indicating damage.
  - `damage_details`: Specific flaws (e.g., *"cracked rear glass, non-working Face ID"*).
  - `face_id_working`: Boolean flag.
  - `icloud_clean`: Boolean flag.
  - `ai_summary`: 1-sentence appraiser summary verdict.
  - `ai_raw_json`: Full JSON returned by DeepSeek.
- **`scanned_pages`**: Tracks page numbers, timestamps, duration, and MD5 fingerprints for early-stopping optimization.

---

## 🧪 Testing

Run unit and parsing tests with `pytest`:

```bash
pytest tests/unit -v
```

---

## 🛡️ Best Practices & Notes

1. **Proxy Rotation:** If scanning dozens of pages frequently, use a proxy rotator (such as a local gateway at `http://127.0.0.1:8080`) or specify a working `--proxy-file` to prevent temporary rate limits on OLX.
2. **DeepSeek API Usage:** Thanks to the built-in heuristic filter and page fingerprint deduplication, the scanner only sends actual, newly discovered iPhone listings to DeepSeek, minimizing your API token consumption.

---

## 📄 License

Distributed under the **MIT License**. See `LICENSE` for more information.
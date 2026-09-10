# olx-iphone-scanner

[![CI](https://github.com/k4rror/olx-iphone-scanner/actions/workflows/ci.yml/badge.svg)](https://github.com/k4rror/olx-iphone-scanner/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![Lizenz: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

[English](README.md) | [Polski](README.pl.md) | **Deutsch** | [Українська](README.uk.md) | [Беларуская](README.be.md)

Scannt iPhone-Angebote auf OLX Polen (`olx.pl`) und speichert strukturierte Bewertungen in einer lokalen SQLite-Datenbank. Suchseiten werden mit einem Chrome-120-TLS-Fingerprint abgerufen, Zubehör und Angebote anderer Marken werden durch Regex-Heuristiken verworfen, und die verbleibenden Angebote werden an DeepSeek gesendet, um Modell, Speicher, Batteriezustand, Schäden und Sperrstatus zu extrahieren.

Zwei Frontends nutzen dieselbe Datenbank: eine Rich-Terminal-UI (`olx-scanner`) und ein FastAPI/Jinja2-Web-Dashboard (`olx-dashboard`).

## Schnellstart

```bash
git clone https://github.com/k4rror/olx-iphone-scanner.git
cd olx-iphone-scanner
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\Activate.ps1
pip install -e .
olx-scanner
```

Beim ersten Start beginnt ein interaktiver Assistent (Sprache, DeepSeek-API-Schlüssel, Proxy-Modus, Seitenanzahl) und schreibt `scanner_config.json`. Ein DeepSeek-API-Schlüssel ist erforderlich.

## Funktionen

- **TLS-Fingerprinting:** `tls-client` ist mit einem Chrome-120-Profil und emulierten Headern konfiguriert, sodass Anfragen wie von einem normalen Browser aussehen, ohne einen Dienst zum Lösen von CAPTCHAs.
- **Proxy-Pool:** Proxy-Listen werden asynchron gegen OLX über HTTPS-Tunnel getestet und vor dem Start des Scans sortiert. Unterstützt werden ein statischer Proxy, ein lokaler Rotator oder direktes TLS.
- **Heuristischer Vorfilter:** Regex-Regeln verwerfen Hüllen, Kartons, Ladegeräte, Ersatzteile und andere Marken (Samsung, Xiaomi, Pixel), bevor eine DeepSeek-Anfrage gesendet wird, was den Token-Verbrauch senkt.
- **DeepSeek-Extraktion:** Jedes Angebot wird in typisierte Felder geparst (Modell, Speicher in GB, Farbe, Batteriezustand in Prozent, Zustand, Schadensdetails, Face ID, iCloud-Sperre) plus ein Urteil in einem Satz. Fehlerhafte JSON-Antworten werden repariert und mit Pydantic validiert.
- **Deduplizierung und Early Stopping:** Seiten-Fingerprints werden aus dem MD5-Hash der Angebots-IDs auf der jeweiligen Seite berechnet. Wenn Seite 1 seit dem letzten Zyklus unverändert ist oder eine spätere Seite keine neuen Angebote liefert, endet der Scan vorzeitig.
- **Terminal-Dashboard:** eine Rich-Live-Ansicht mit KPI-Zählern, einer Tabelle der zuletzt analysierten Angebote, Fortschritt und einem laufenden Ereignisprotokoll. `--inline` deaktiviert den alternativen Bildschirmpuffer für CI oder nicht interaktive Shells.
- **Web-Dashboard:** FastAPI- und Jinja2-Seiten zur Scanner-Steuerung, für die Angebotstabelle (Filter, Sortierung, Favoriten, Notizen), Analytik und CSV-Export.
- **Speicher:** SQLite im WAL-Modus mit indizierten Spalten, sicher für gleichzeitige Schreiber.
- **Internationalisierung:** UI-Texte und KI-Prompts in Englisch, Polnisch, Ukrainisch, Deutsch und Belarussisch.

## Installation

### Anforderungen

- Python 3.10 oder neuer.
- Ein DeepSeek-API-Schlüssel von [platform.deepseek.com](https://platform.deepseek.com/).
- Netzwerkzugriff auf `olx.pl`.

### Installation

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

Die Basisinstallation enthält die Abhängigkeiten des Web-Dashboards (`fastapi`, `uvicorn`, `jinja2`). Um zusätzlich die Tests und den Linter auszuführen:

```bash
pip install -e ".[dev]"
```

## Verwendung

### Terminal-Scanner

```bash
# Interaktiver Assistent (erster Start oder nach dem Löschen von scanner_config.json)
olx-scanner

# Assistenten jederzeit erneut starten
olx-scanner --setup

# Ein Zyklus über 3 Seiten in einer gewählten Region, ohne Rückfragen
olx-scanner --non-interactive --pages 3 --region mazowieckie

# Kontinuierliche Überwachung: 5 Seiten, dann 60 Sekunden warten und wiederholen
olx-scanner --pages 5 --watch --interval 60

# Sprache der Oberfläche und der KI-Prompts erzwingen
olx-scanner --lang pl

# Proxy: ein einzelner Endpunkt oder eine getestete Liste aus einer Datei
olx-scanner --proxy http://user:pass@127.0.0.1:8080
olx-scanner --proxy-file proxies.txt --min-proxies 20

# Nicht interaktive Ausgabe für CI oder Logging
olx-scanner --inline
```

Die Region kann auch als `--wojewodztwo` übergeben werden. Akzeptiert werden Wojewodschafts-Slugs wie `mazowieckie`, `slaskie`, `malopolskie`; ohne Angabe wird ganz OLX Polen gescannt.

### CLI-Optionen

| Flag | Beschreibung | Standard |
| :--- | :--- | :--- |
| `--setup`, `--reconfigure` | Interaktiven Einrichtungsassistenten starten | `False` |
| `--non-interactive`, `-y` | Vorab-Rückfragen überspringen und die gespeicherte Konfiguration verwenden | `False` |
| `--lang` | Sprache der Oberfläche und der Prompts (`en`, `pl`, `uk`, `de`, `be`) | config, sonst `pl` |
| `--region`, `--wojewodztwo` | Wojewodschafts-Slug, z. B. `mazowieckie` | alle Regionen |
| `--api-key` | DeepSeek-API-Schlüssel überschreiben | config / `.env` |
| `--model` | DeepSeek-Modellbezeichner | `deepseek-v4-flash-vision-exp` |
| `--proxy` | Einzelner statischer Proxy (`http://host:port`) | `None` |
| `--proxy-file`, `-pf` | Datei mit Proxy-Liste (`.txt` oder `.json`) | `None` |
| `--min-proxies` | Mindestanzahl gültiger Proxys im Pool | `15` |
| `--proxy-workers` | Threads zur Überprüfung der Proxys | `150` |
| `--pages` | Suchseiten pro Zyklus | `3` |
| `--threads` | Parallele Threads für die KI-Analyse | `8` |
| `--watch` | Scan in einer Schleife wiederholen | `False` |
| `--interval` | Sekunden zwischen den Zyklen im Watch-Modus | `120` |
| `--inline` | Scrollende Ausgabe statt Vollbild-TUI | `False` |
| `--log-file` | Pfad der Ausführungsprotokolldatei | `olx_scanner.log` |

### Web-Dashboard

```bash
olx-dashboard
```

Das Dashboard wird unter `http://127.0.0.1:8000` bereitgestellt und im Standardbrowser geöffnet. Der Einstiegspunkt akzeptiert:

| Flag | Beschreibung | Standard |
| :--- | :--- | :--- |
| `--host` | Bind-Adresse | `127.0.0.1` |
| `--port` | Listen-Port | `8000` |
| `--db` | Pfad zur SQLite-Datenbankdatei | `olx_iphones.db` |
| `--no-browser` | Browser beim Start nicht öffnen | `False` |

Seiten: `/scanner` (Scan starten/stoppen), `/offers` (filtern, sortieren, favorisieren, mit Notizen versehen, löschen, CSV exportieren), `/analytics` (Preisstatistiken pro Modell und Marge gegenüber dem Marktdurchschnitt).

Das Dashboard stellt eine JSON-API über dieselben Daten bereit. Die wichtigsten Routen:

| Methode | Route | Zweck |
| :--- | :--- | :--- |
| `GET` | `/api/stats` | Datenbank-KPIs und Zusammenfassung der Analytik |
| `GET` | `/api/offers` | Seitenweise, gefilterte Angebotsliste |
| `GET` | `/api/offers/{olx_id}` | Details eines einzelnen Angebots |
| `POST` | `/api/offers/{olx_id}/favorite` | Favoriten-Flag umschalten |
| `PATCH` | `/api/offers/{olx_id}/notes` | Benutzernotizen speichern |
| `DELETE` | `/api/offers/{olx_id}` | Angebot löschen |
| `GET` | `/api/export` | CSV-Export des aktuellen Filters |
| `GET` | `/api/models/stats` | Preis- und Batteriestatistiken für ein Modell |
| `GET` | `/api/scanner/status` | Aktueller Scanner-Zustand |
| `POST` | `/api/scanner/start` | Einen Scan-Zyklus starten |
| `POST` | `/api/scanner/stop` | Laufenden Scan stoppen |
| `GET` | `/api/scanner/probe` | Anzahl der Angebote und Seiten für eine Region |

### Konfiguration

`.env` im Projektstamm:

```env
DEEPSEEK_API_KEY=your_deepseek_api_key_here
OLX_PROXY=
```

`scanner_config.json`, vom Assistenten erzeugt und von Hand editierbar:

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

Kommandozeilen-Flags haben Vorrang vor der Konfigurationsdatei, und die Konfigurationsdatei vor `.env`.

## Datenbankschema

SQLite im WAL-Modus, automatisch unter `olx_iphones.db` angelegt.

`iphone_offers`:

| Spalte | Hinweise |
| :--- | :--- |
| `id` | Primärschlüssel |
| `olx_id` | Eindeutige OLX-Angebots-ID, indiziert |
| `url`, `title`, `price`, `currency`, `location`, `posted_at`, `description`, `scraped_at` | Rohdaten des Angebots |
| `ai_analyzed` | `0` = ausstehend, `1` = analysiert, indiziert |
| `model_name`, `storage_gb`, `color` | Normalisierte Gerätedaten |
| `battery_health_pct` | Ganzzahl, `NULL`, wenn der Verkäufer sie nicht angegeben hat |
| `condition_state`, `is_damaged`, `damage_details` | Zustand und Defekte, Index auf `is_damaged` |
| `face_id_working`, `icloud_clean` | `1` / `0` / `NULL` |
| `ai_summary` | Urteil in einem Satz |
| `ai_raw_json` | Rohantwort von DeepSeek |
| `is_favorite`, `user_notes` | Vom Web-Dashboard ergänzt |

`scanned_pages`: `page_number`, `scanned_at`, `offers_total`, `new_offers`, `fingerprint` (MD5), `duration_s`. Wird von der Early-Stopping-Prüfung verwendet.

## Tests

```bash
pip install -e ".[dev]"
ruff check .
pytest tests/unit -v
```

Unit-Tests laufen gegen Fixtures und benötigen keinen Netzwerkzugriff und keinen API-Schlüssel. CI führt `ruff check .` und `pytest tests/unit/ -v` auf Python 3.10, 3.11 und 3.12 aus.

## Einschränkungen

- Das Web-Dashboard führt einen einzelnen Scan-Zyklus aus. Der kontinuierliche Watch-Modus ist in der Weboberfläche deaktiviert (`WATCH_MODE_ENABLED = False` in `src/olx_scanner/web/app.py`); stattdessen das CLI-Flag `--watch` verwenden.
- Der Zustand ist eine einzelne lokale SQLite-Datei. Es gibt kein Server-Deployment, keine Authentifizierung und keine Mehrbenutzerunterstützung; das Dashboard bindet standardmäßig an `127.0.0.1`.
- Der Scraper hängt von der HTML-Struktur von OLX ab und bricht, wenn sich das Markup ändert. Es gibt keinen Offline-Modus und keinen mitgelieferten Datensatz.
- Für die Analyse ist ein kostenpflichtiger DeepSeek-API-Schlüssel erforderlich. Ohne ihn werden Angebote trotzdem gespeichert, bleiben aber unanalysiert.
- Dieses Projekt steht in keiner Verbindung zu OLX. Beim Scrapen sind die Nutzungsbedingungen von OLX und die lokalen Vorschriften zu beachten.

## Mitwirken

Forke das Repository, erstelle einen Themen-Branch und stelle sicher, dass `ruff check .` und `pytest tests/unit -v` durchlaufen, bevor du einen Pull Request öffnest.

## Lizenz

MIT. Siehe [LICENSE](LICENSE).

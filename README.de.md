# 📱 OLX iPhone Scanner & DeepSeek AI Appraiser

[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![Terminal-Benutzeroberfläche](https://img.shields.io/badge/UI-Rich%20TUI-cyan.svg)](https://github.com/Textualize/rich)
[![KI-Engine](https://img.shields.io/badge/AI-DeepSeek-magenta.svg)](https://www.deepseek.com/)
[![Lizenz](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

Ein intelligenter Echtzeit-Terminal-Scanner und Schnäppchen-Gutachter für iPhone-Inserate auf **OLX Polen** (`olx.pl`), angetrieben von **DeepSeek AI**.

Die Suche nach echten iPhone-Schnäppchen auf OLX ist oft mühsam: Verkäufer verstecken wichtige Informationen zum Akkuzustand häufig im Fließtext (z. B. *"kondycja 84%"*, *"nowa bateria zamiennik"*), verschweigen iCloud-Sperren oder überfluten die Kategorie mit Zubehör (Hüllen, leere Verpackungen, Schutzfolien).

Der **OLX iPhone Scanner** automatisiert diesen Ablauf vollständig: Er erfasst aktuelle Angebote mit Browser-identischem TLS-Fingerprinting, filtert Zubehör per Heuristik heraus und analysiert technische Details mit **DeepSeek AI**. Alle Daten werden in einer lokalen SQLite-Datenbank strukturiert und auf einem interaktiven Live-Dashboard dargestellt.

---

## 🌟 Hauptfunktionen

- **⚡ Cloudflare- & Bot-Schutz-Umgehung:** Nutzt `tls-client` mit Chrome-120-Fingerprints und maßgeschneiderten Headern, um OLX ohne IP-Sperren oder CAPTCHA-Hürden abzufragen.
- **🧠 DeepSeek KI-Begutachtung:** Präzise Extraktion technischer Parameter aus unstrukturierten polnischen Inseratstexten:
  - Exaktes Modell und Speicherkapazität (GB)
  - Gehäusefarbe
  - Batteriegesundheit in Prozent (`battery_health_pct`)
  - Optischer und technischer Gesamtzustand
  - Erkennung von Mängeln und Beschädigungen (z. B. Displayriss, Rückseite defekt)
  - Funktionsstatus von Face ID und iCloud-Sperre
  - Prägnantes Gutachter-Urteil in einem Satz
- **🛡️ Token-sparender Heuristik-Filter:** Sortiert Hüllen, OVP-Boxen, Ersatzteile, Netzteile und Fremdmarken (Samsung, Xiaomi, Pixel) per Regex aus, **bevor** die KI-API aufgerufen wird.
- **🔄 Proxy-Verwaltung & Rotator-Integration:**
  - Direkte TLS-Verbindung über die eigene IP.
  - Automatische Anbindung an lokale Rotatoren (standardmäßig `http://127.0.0.1:8080`).
  - Asynchroner Multi-Thread-Tester für HTTPS-Tunnel zu OLX aus benutzerdefinierten Proxy-Listen.
- **📊 Interaktives Terminal-Dashboard (Rich Live TUI):**
  - KPI-Karten (Gesamt in Datenbank, Von KI analysiert, Einwandfrei, Defekt, Übersprungene Duplikate).
  - Live-Tabelle der zuletzt analysierten iPhones.
  - Fortschrittsbalken und Countdown für den Hintergrund-Überwachungsmodus (`watch`).
  - Ereignisprotokoll in Echtzeit.
- **⚡ Duplikaterkennung & Early Stopping:** Erstellt MD5-Seiten-Fingerprints. Enthält eine Seite zu 100 % bereits bekannte Inserate, bricht der Scanner frühzeitig ab, um Ressourcen zu schonen.
- **🌐 Mehrsprachigkeit (i18n):** Vollständige Lokalisierung für 5 Sprachen: Deutsch (`de`), Englisch (`en`), Polnisch (`pl`), Ukrainisch (`uk`), Belarussisch (`be`).
- **💾 Lokale SQLite-Datenbank mit WAL-Modus:** Sichere Speicherung mit Write-Ahead Logging für parallele Schreibvorgänge in `olx_iphones.db`.

---

## 🏗️ Systemarchitektur

```text
  [ OLX.pl iPhone-Angebote ]
                │
                ▼ (TLS-Client - Chrome 120 Fingerprint / Proxy-Pool)
  [ Scraper & HTML-Parser ]
                │
                ▼ (MD5-Seitenfingerprint / Duplikatsprüfung)
  [ SQLite-Deduplizierung ] ────► (Bereits erfasst? -> Überspringen)
                │
                ▼
  [ Heuristik-Filter ] ────► (Hülle / Box / Fremdmarke erkannt? -> Verwerfen)
                │
                ▼ (Parallele KI-Warteschlange)
  [ DeepSeek API Analyzer ]
                │
                ├─► JSON-Autoreparatur & Pydantic-Validierung
                ├─► Speichern in SQLite (`olx_iphones.db`)
                └─► Aktualisierung des Live-Dashboards & Log-Datei
```

---

## 📦 Installation

### 1. Voraussetzungen
- Python **3.10** oder neuer.
- DeepSeek API-Schlüssel (erhältlich unter [platform.deepseek.com](https://platform.deepseek.com/)).

### 2. Repository klonen & Umgebung einrichten

```bash
git clone https://github.com/k4rror/olx-iphone-scanner.git
cd olx-iphone-scanner

# Virtuelle Umgebung erstellen und aktivieren
python -m venv .venv

# Linux / macOS:
source .venv/bin/activate

# Windows (PowerShell):
.venv\Scripts\Activate.ps1
```

### 3. Paket installieren

```bash
pip install -e .
```

---

## 🚀 Schnelleinstieg

### Ersteinrichtungs-Assistent

Starten Sie das Programm einfach im Terminal:
```bash
olx-scanner
```

Beim ersten Start führt Sie ein interaktiver Einrichtungsassistent durch die Konfiguration:
1. Auswahl der Menü- und Prompt-Sprache (`de`, `en`, `pl`, `uk`, `be`).
2. Eingabe des DeepSeek-API-Schlüssels.
3. Verbindungsmodus (Direktes TLS, lokaler Rotator auf `127.0.0.1:8080` oder Proxy-Liste).
4. Standard-Seitenzahl und Einstellungen für den Überwachungsmodus.

Die Einstellungen werden in `scanner_config.json` abgelegt. Der Assistent kann jederzeit erneut gestartet werden:
```bash
olx-scanner --setup
```

---

## ⚙️ Konfiguration

### Umgebungsvariablen (`.env`)
Sie können Ihren Schlüssel in einer `.env`-Datei hinterlegen:
```env
DEEPSEEK_API_KEY=ihr_deepseek_api_schluessel
```

### Konfigurationsdatei `scanner_config.json`
```json
{
  "language": "de",
  "api_key": "ihr_deepseek_api_schluessel",
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

## 💻 Anwendungsbeispiele

### Einzelner Suchlauf
Prüft die ersten 3 Seiten und beendet den Vorgang:
```bash
olx-scanner --pages 3
```

### Dauerhafte Überwachung (Watch-Modus)
Scannt 5 Seiten, bewertet neue Angebote und wiederholt den Zyklus alle 60 Sekunden:
```bash
olx-scanner --pages 5 --watch --interval 60
```

### Sprache flexibel wechseln
Startet das Interface auf Deutsch oder Polnisch:
```bash
olx-scanner --lang de
olx-scanner --lang pl
```

### Proxy-Konfiguration
Verwendung eines statischen Proxys oder einer Prüfliste:
```bash
# Einzelner Proxy:
olx-scanner --proxy http://user:pass@127.0.0.1:8080

# Proxy-Liste (wird vorab automatisch auf Latenz getestet):
olx-scanner --proxy-file proxies.txt --min-proxies 20
```

### Inline-Modus
Deaktiviert die Vollbild-Terminalansicht (praktisch für CI/CD):
```bash
olx-scanner --inline
```

---

## 📋 Befehlszeilenparameter

| Option | Flag | Beschreibung | Standard |
| :--- | :--- | :--- | :--- |
| **Setup** | `--setup`, `--reconfigure` | Startet den Einrichtungsassistenten | `False` |
| **Sprache** | `--lang` | Sprache für Benutzeroberfläche und KI (`de`, `en`, `pl`, `uk`, `be`)| `en` |
| **API-Key** | `--api-key` | Überschreibt den DeepSeek-API-Schlüssel | Aus Config / `.env` |
| **Modell** | `--model` | DeepSeek-Modellbezeichnung | `deepseek-v4-flash-vision-exp` |
| **Seiten** | `--pages` | Anzahl der zu scannenden Seiten pro Durchlauf | `3` |
| **KI-Threads** | `--threads` | Parallele Threads für die KI-Analyse | `8` |
| **Watch-Modus** | `--watch` | Aktiviert die kontinuierliche Überwachungsschleife | `False` |
| **Intervall** | `--interval` | Wartezeit in Sekunden zwischen Zyklen im Watch-Modus | `120` |
| **Proxy** | `--proxy` | Statische Proxy-URL (`http://host:port`) | `None` |
| **Proxy-Datei**| `--proxy-file`, `-pf` | Pfad zu einer Datei mit Proxy-Adressen (`.txt`/`.json`) | `None` |
| **Min. Proxies**| `--min-proxies` | Erforderliche Mindestanzahl funktionsfähiger Proxies | `15` |
| **Worker** | `--proxy-workers` | Anzahl paralleler Threads für den Proxy-Test | `150` |
| **Inline-Ansicht**| `--inline` | Fortlaufender Standard-Textmodus ohne Terminal-Clear | `False` |
| **Log-Datei** | `--log-file` | Zielpfad für die Protokolldatei | `olx_scanner.log` |

---

## 🗄️ Datenbankschema (`olx_iphones.db`)

- **`iphone_offers`**:
  - `olx_id`: Eindeutige Kennung des OLX-Inserats.
  - `title`, `price`, `location`, `posted_at`, `description`, `url`.
  - `ai_analyzed`: Analysestatus (`0` = ausstehend, `1` = analysiert).
  - `model_name`: Erkanntes Modell (z. B. `iPhone 13 Pro`).
  - `storage_gb`: Speicherplatz in GB (z. B. `128`).
  - `battery_health_pct`: Akkuzustand in % (oder `NULL`).
  - `condition_state`: Beschreibung des optischen und technischen Zustands.
  - `is_damaged`: Beschädigungsstatus (1 = defekt, 0 = in Ordnung).
  - `damage_details`: Details zu erfassten Schäden.
  - `face_id_working`: Funktionsfähigkeit von Face ID (1 / 0 / NULL).
  - `icloud_clean`: Keine iCloud-Sperre vorhanden (1 / 0 / NULL).
  - `ai_summary`: Zusammenfassendes Urteil der KI.
  - `ai_raw_json`: Vollständige Rohantwort der DeepSeek-API.
- **`scanned_pages`**: Scan-Historie der Seiten mit MD5-Prüfsummen für die Early-Stopping-Optimierung.

---

## 🧪 Tests

Ausführen der Tests mit `pytest`:
```bash
pytest tests/unit -v
```

---

## 📄 Lizenz

Dieses Projekt ist unter der **MIT-Lizenz** veröffentlicht. Weitere Details finden Sie in der Datei `LICENSE`.

# olx-iphone-scanner

[![CI](https://github.com/k4rror/olx-iphone-scanner/actions/workflows/ci.yml/badge.svg)](https://github.com/k4rror/olx-iphone-scanner/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![Licencja: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

[English](README.md) | **Polski** | [Deutsch](README.de.md) | [Українська](README.uk.md) | [Беларуская](README.be.md)

Skaner ogłoszeń iPhone z OLX Polska (`olx.pl`), który zapisuje ustrukturyzowane wyceny w lokalnej bazie SQLite. Strony wyników pobiera z odciskiem TLS Chrome 120, odrzuca akcesoria i ogłoszenia innych marek za pomocą heurystyk opartych na wyrażeniach regularnych, a pozostałe oferty wysyła do DeepSeek, aby wyciągnąć model, pamięć, kondycję baterii, uszkodzenia i status blokad.

Z tej samej bazy korzystają dwa interfejsy: terminalowy panel Rich (`olx-scanner`) oraz panel web FastAPI/Jinja2 (`olx-dashboard`).

## Szybki start

```bash
git clone https://github.com/k4rror/olx-iphone-scanner.git
cd olx-iphone-scanner
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\Activate.ps1
pip install -e .
olx-scanner
```

Przy pierwszym uruchomieniu startuje kreator konfiguracji (język, klucz API DeepSeek, tryb proxy, liczba stron) i zapisuje plik `scanner_config.json`. Klucz API DeepSeek jest wymagany.

## Funkcje

- **Odcisk TLS:** biblioteka `tls-client` jest skonfigurowana profilem Chrome 120 i emulowanymi nagłówkami, dzięki czemu zapytania wyglądają jak zwykła przeglądarka, bez usługi rozwiązującej CAPTCHA.
- **Pula proxy:** listy proxy są testowane asynchronicznie względem OLX przez tunele HTTPS i sortowane przed startem skanu. Obsługiwane są statyczne proxy, lokalny rotator oraz bezpośrednie połączenie TLS.
- **Filtr heurystyczny:** reguły regex odrzucają etui, pudełka, ładowarki, części zamienne i inne marki (Samsung, Xiaomi, Pixel) przed wysłaniem zapytania do DeepSeek, co ogranicza zużycie tokenów.
- **Ekstrakcja DeepSeek:** każde ogłoszenie jest parsowane do pól o określonych typach (model, pamięć w GB, kolor, kondycja baterii w procentach, stan, opis uszkodzeń, Face ID, blokada iCloud) oraz jednozdaniowego werdyktu. Błędne odpowiedzi JSON są naprawiane i walidowane przez Pydantic.
- **Deduplikacja i early stopping:** odcisk strony liczony jest jako skrót MD5 identyfikatorów ogłoszeń na danej stronie. Jeśli pierwsza strona nie zmieniła się od ostatniego cyklu albo kolejna strona nie wnosi nowych ofert, skan kończy się wcześniej.
- **Panel terminalowy:** widok Rich Live z licznikami KPI, tabelą ostatnio przeanalizowanych ofert, postępem i bieżącym dziennikiem zdarzeń. Flaga `--inline` wyłącza pełnoekranowy bufor dla CI lub powłok nieinteraktywnych.
- **Panel web:** strony FastAPI i Jinja2 do sterowania skanerem, przeglądania ofert (filtry, sortowanie, ulubione, notatki), analityki oraz eksportu CSV.
- **Baza danych:** SQLite w trybie WAL z zindeksowanymi kolumnami, bezpieczny dla równoległych zapisów.
- **Internacjonalizacja:** teksty interfejsu i prompty AI w językach angielskim, polskim, ukraińskim, niemieckim i białoruskim.

## Instalacja

### Wymagania

- Python 3.10 lub nowszy.
- Klucz API DeepSeek z [platform.deepseek.com](https://platform.deepseek.com/).
- Dostęp sieciowy do `olx.pl`.

### Instalacja

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

Instalacja podstawowa zawiera zależności panelu web (`fastapi`, `uvicorn`, `jinja2`). Aby uruchomić także testy i linter:

```bash
pip install -e ".[dev]"
```

## Użycie

### Skaner terminalowy

```bash
# Kreator konfiguracji (pierwsze uruchomienie lub po usunięciu scanner_config.json)
olx-scanner

# Ponowne uruchomienie kreatora w dowolnym momencie
olx-scanner --setup

# Jeden cykl po 3 stronach w wybranym województwie, bez pytań
olx-scanner --non-interactive --pages 3 --region mazowieckie

# Ciągły monitoring: 5 stron, potem 60 sekund przerwy i powtórka
olx-scanner --pages 5 --watch --interval 60

# Wymuszenie języka interfejsu i promptów AI
olx-scanner --lang pl

# Proxy: pojedynczy adres albo przetestowana lista z pliku
olx-scanner --proxy http://user:pass@127.0.0.1:8080
olx-scanner --proxy-file proxies.txt --min-proxies 20

# Wyjście nieinteraktywne, dla CI lub logowania
olx-scanner --inline
```

Region można też podać jako `--wojewodztwo`. Przyjmowane są slugi województw, np. `mazowieckie`, `slaskie`, `malopolskie`. Pominięcie oznacza skan całej Polski.

### Opcje CLI

| Flaga | Opis | Domyślnie |
| :--- | :--- | :--- |
| `--setup`, `--reconfigure` | Uruchom interaktywny kreator konfiguracji | `False` |
| `--non-interactive`, `-y` | Pomiń pytania wstępne i użyj zapisanej konfiguracji | `False` |
| `--lang` | Język interfejsu i promptów (`en`, `pl`, `uk`, `de`, `be`) | z configu, inaczej `pl` |
| `--region`, `--wojewodztwo` | Slug województwa, np. `mazowieckie` | wszystkie regiony |
| `--api-key` | Nadpisanie klucza API DeepSeek | config / `.env` |
| `--model` | Identyfikator modelu DeepSeek | `deepseek-v4-flash-vision-exp` |
| `--proxy` | Pojedynczy statyczny proxy (`http://host:port`) | `None` |
| `--proxy-file`, `-pf` | Plik z listą proxy (`.txt` lub `.json`) | `None` |
| `--min-proxies` | Minimalna liczba działających proxy w puli | `15` |
| `--proxy-workers` | Liczba wątków weryfikujących proxy | `150` |
| `--pages` | Liczba stron wyników na cykl | `3` |
| `--threads` | Liczba równoległych wątków analizy AI | `8` |
| `--watch` | Powtarzanie skanu w pętli | `False` |
| `--interval` | Liczba sekund między cyklami w trybie watch | `120` |
| `--inline` | Wyjście przewijane zamiast pełnoekranowego TUI | `False` |
| `--log-file` | Ścieżka pliku logu | `olx_scanner.log` |

### Panel web

```bash
olx-dashboard
```

Panel działa pod `http://127.0.0.1:8000` i otwiera się w domyślnej przeglądarce. Punkt wejścia przyjmuje:

| Flaga | Opis | Domyślnie |
| :--- | :--- | :--- |
| `--host` | Adres nasłuchu | `127.0.0.1` |
| `--port` | Port nasłuchu | `8000` |
| `--db` | Ścieżka pliku bazy SQLite | `olx_iphones.db` |
| `--no-browser` | Nie otwieraj przeglądarki przy starcie | `False` |

Strony: `/scanner` (uruchamianie i zatrzymywanie skanu), `/offers` (filtrowanie, sortowanie, ulubione, notatki, usuwanie, eksport CSV), `/analytics` (statystyki cen dla modelu i marża względem średniej rynkowej).

Panel udostępnia też API JSON nad tymi samymi danymi. Najważniejsze trasy:

| Metoda | Trasa | Przeznaczenie |
| :--- | :--- | :--- |
| `GET` | `/api/stats` | Wskaźniki bazy i podsumowanie analityki |
| `GET` | `/api/offers` | Stronicowana, filtrowana lista ofert |
| `GET` | `/api/offers/{olx_id}` | Szczegóły pojedynczej oferty |
| `POST` | `/api/offers/{olx_id}/favorite` | Przełączenie flagi ulubionych |
| `PATCH` | `/api/offers/{olx_id}/notes` | Zapis notatek użytkownika |
| `DELETE` | `/api/offers/{olx_id}` | Usunięcie oferty |
| `GET` | `/api/export` | Eksport CSV bieżącego filtra |
| `GET` | `/api/models/stats` | Statystyki cen i baterii dla modelu |
| `GET` | `/api/scanner/status` | Bieżący stan skanera |
| `POST` | `/api/scanner/start` | Start cyklu skanowania |
| `POST` | `/api/scanner/stop` | Zatrzymanie działającego skanu |
| `GET` | `/api/scanner/probe` | Liczba ogłoszeń i stron dla regionu |

### Konfiguracja

Plik `.env` w katalogu głównym projektu:

```env
DEEPSEEK_API_KEY=twoj_klucz_api_deepseek
OLX_PROXY=
```

Plik `scanner_config.json`, tworzony przez kreator i edytowalny ręcznie:

```json
{
  "language": "pl",
  "api_key": "twoj_klucz_api_deepseek",
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

Flagi wiersza poleceń mają pierwszeństwo przed plikiem konfiguracyjnym, a plik konfiguracyjny przed `.env`.

## Schemat bazy danych

SQLite w trybie WAL, tworzona automatycznie jako `olx_iphones.db`.

Tabela `iphone_offers`:

| Kolumna | Opis |
| :--- | :--- |
| `id` | Klucz główny |
| `olx_id` | Unikalny identyfikator ogłoszenia OLX, zindeksowany |
| `url`, `title`, `price`, `currency`, `location`, `posted_at`, `description`, `scraped_at` | Surowe dane ogłoszenia |
| `ai_analyzed` | `0` = oczekuje, `1` = przeanalizowane, zindeksowane |
| `model_name`, `storage_gb`, `color` | Znormalizowane dane urządzenia |
| `battery_health_pct` | Liczba całkowita, `NULL`, gdy sprzedawca jej nie podał |
| `condition_state`, `is_damaged`, `damage_details` | Stan i usterki, indeks na `is_damaged` |
| `face_id_working`, `icloud_clean` | `1` / `0` / `NULL` |
| `ai_summary` | Jednozdaniowy werdykt |
| `ai_raw_json` | Surowa odpowiedź DeepSeek |
| `is_favorite`, `user_notes` | Dodawane przez panel web |

Tabela `scanned_pages`: `page_number`, `scanned_at`, `offers_total`, `new_offers`, `fingerprint` (MD5), `duration_s`. Używana przez mechanizm early stopping.

## Testy

```bash
pip install -e ".[dev]"
ruff check .
pytest tests/unit -v
```

Testy jednostkowe działają na fixtures i nie wymagają dostępu do sieci ani klucza API. CI uruchamia `ruff check .` oraz `pytest tests/unit/ -v` na Pythonie 3.10, 3.11 i 3.12.

## Ograniczenia

- Panel web wykonuje pojedynczy cykl skanowania. Tryb ciągły (watch) jest w nim wyłączony (`WATCH_MODE_ENABLED = False` w `src/olx_scanner/web/app.py`); do monitoringu służy flaga `--watch` w CLI.
- Stan to jedna lokalna baza SQLite. Nie ma wdrożenia serwerowego, uwierzytelniania ani obsługi wielu użytkowników; panel domyślnie nasłuchuje na `127.0.0.1`.
- Skaner zależy od struktury HTML OLX i przestaje działać, gdy znaczniki się zmienią. Nie ma trybu offline ani dołączonego zbioru danych.
- Analiza wymaga płatnego klucza API DeepSeek. Bez niego ogłoszenia są zapisywane, ale pozostają nieprzeanalizowane.
- Projekt nie jest powiązany z OLX. Przy skanowaniu należy przestrzegać regulaminu OLX i lokalnych przepisów.

## Współpraca

Zrób fork repozytorium, utwórz gałąź tematyczną i upewnij się, że `ruff check .` oraz `pytest tests/unit -v` przechodzą, zanim otworzysz pull request.

## Licencja

MIT. Szczegóły w pliku [LICENSE](LICENSE).

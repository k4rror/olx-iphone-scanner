# 📱 OLX iPhone Scanner & DeepSeek AI Appraiser

[![Wersja Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![Interfejs Terminala](https://img.shields.io/badge/UI-Rich%20TUI-cyan.svg)](https://github.com/Textualize/rich)
[![Silnik AI](https://img.shields.io/badge/AI-DeepSeek-magenta.svg)](https://www.deepseek.com/)
[![Licencja](https://img.shields.io/badge/licencja-MIT-green.svg)](LICENSE)

Inteligentny, działający w czasie rzeczywistym skaner terminalowy i rzeczoznawca ofert iPhone z serwisu **OLX Polska** (`olx.pl`), napędzany sztuczną inteligencją **DeepSeek**.

Wyszukiwanie prawdziwych okazji cenowych iPhone'ów na OLX bywa uciążliwe: sprzedawcy często ukrywają kluczowe informacje o kondycji baterii wewnątrz długich opisów (np. *"bateria 84%"*, *"kondycja bdb, wymieniana"*), nie wspominają bezpośrednio o blokadach iCloud lub zalewają kategorię akcesoriami (etui, pudełka, szkła hartowane).

**OLX iPhone Scanner** automatyzuje ten proces od początku do końca: pobiera najnowsze oferty z zachowaniem odcisków przeglądarki TLS, błyskawicznie filtruje śmieci za pomocą heurystyk, a model **DeepSeek AI** precyzyjnie ekstrahuje parametry techniczne, stan i wady do lokalnej bazy SQLite oraz interaktywnego pulpitu w terminalu.

---

## 🌟 Kluczowe Funkcje

- **⚡ Omijanie Cloudflare i Ochrony Botowej:** Zastosowanie biblioteki `tls-client` z profilem Chrome 120, rotacją nagłówków i emulacją TLS pozwala na pobieranie stron OLX bez blokad IP czy zapytań CAPTCHA.
- **🧠 Wycena i Analiza DeepSeek AI:** Precyzyjna analiza nieustrukturyzowanych, polskich opisów:
  - Dokładny model urządzenia oraz pamięć (GB)
  - Kolor obudowy
  - Kondycja baterii w procentach (`battery_health_pct`)
  - Stan wizualny i techniczny
  - Wykrywanie usterek i uszkodzeń (np. zbity tył, pęknięty ekran)
  - Sprawność Face ID oraz status blokady iCloud
  - Zwięzły, 1-zdaniowy werdykt rzeczoznawcy sprzętowego
- **🛡️ Oszczędność Tokenów (Filtr Heurystyczny):** Odrzuca oferty z etui, pudełkami, częściami zamiennymi, ładowarkami i smartfonami innych marek (Samsung, Xiaomi, Pixel) za pomocą wyrażeń regularnych **przed** wysłaniem zapytania do API.
- **🔄 Zaawansowane Zarządzanie Proxy i Rotatorami:**
  - Tryb bezpośredni (Direct TLS z Twojego łącza).
  - Automatyczne wykrywanie lokalnego rotatora (np. wbudowane narzędzie na `http://127.0.0.1:8080`).
  - Asynchroniczne sprawdzanie i rankingowanie tuneli HTTPS do serwerów OLX z własnych list proxy.
- **📊 Interaktywny Pulpit Terminalowy (Rich Live TUI):**
  - Karty wskaźników KPI (Wszystkie w bazie, Zbadane przez AI, Sprawne, Uszkodzone, Pominięte duplikaty).
  - Tabela na żywo z ostatnio przeanalizowanymi iPhone'ami.
  - Pasek postępu i odliczanie do kolejnego cyklu w trybie ciągłym (`watch`).
  - Dziennik zdarzeń w czasie rzeczywistym.
- **⚡ Wykrywanie Duplikatów i Early Stopping:** Oblicza skróty MD5 każdej przeskanowanej strony. Jeśli na danej podstronie 100% ofert znajduje się już w bazie, skaner przerywa dalsze odpytywanie kolejnych stron, oszczędzając czas i transfer.
- **🌐 Wielojęzyczność (i18n):** Pełne wsparcie dla 5 języków interfejsu oraz promptów AI: angielski (`en`), polski (`pl`), ukraiński (`uk`), niemiecki (`de`), białoruski (`be`).
- **💾 Baza Danych SQLite z Trybem WAL:** Bezpieczny, wielowątkowy zapis ofert i wyników AI w bazie `olx_iphones.db` z włączonym dziennikiem Write-Ahead Logging.

---

## 🏗️ Architektura Systemu

```text
  [ Strumień ogłoszeń OLX.pl ]
                 │
                 ▼ (Klient TLS - Odcisk Chrome 120 / Pula Proxy)
  [ Pobieranie i Parser HTML ]
                 │
                 ▼ (Suma kontrolna MD5 strony / Baza danych)
  [ Weryfikacja Duplikatów ] ────► (Oferta już zbadana? -> Pomiń)
                 │
                 ▼
  [ Filtr Heurystyczny ] ────► (Wykryto etui / pudełko / inną markę? -> Odrzuć)
                 │
                 ▼ (Wielowątkowa kolejka AI)
  [ Analizator DeepSeek API ]
                 │
                 ├─► Automatyczna naprawa JSON i walidacja Pydantic
                 ├─► Zapis w bazie SQLite (`olx_iphones.db`)
                 └─► Aktualizacja pulpitu Rich TUI i pliku logów
```

---

## 📦 Instalacja

### 1. Wymagania wstępne
- Python w wersji **3.10** lub nowszej.
- Klucz API DeepSeek (dostępny na [platform.deepseek.com](https://platform.deepseek.com/)).

### 2. Klonowanie repozytorium i środowisko wirtualne

```bash
git clone https://github.com/k4rror/olx-iphone-scanner.git
cd olx-iphone-scanner

# Utworzenie i aktywacja środowiska wirtualnego
python -m venv .venv

# Linux / macOS:
source .venv/bin/activate

# Windows (PowerShell):
.venv\Scripts\Activate.ps1
```

### 3. Instalacja zależności

W trybie deweloperskim (edytowalnym):
```bash
pip install -e .
```

---

## 🚀 Szybki Start

### Kreator Pierwszego Uruchomienia

Wpisz w terminalu polecenie:
```bash
olx-scanner
```

Przy pierwszym starcie automatycznie uruchomi się interaktywny kreator konfiguracji:
1. Wybór preferowanego języka (`pl`, `en`, `uk`, `de`, `be`).
2. Podanie klucza API DeepSeek.
3. Wybór trybu sieciowego (Direct TLS, lokalny rotator `127.0.0.1:8080` lub plik z proxy).
4. Określenie domyślnej liczby stron oraz ustawień trybu monitorowania (`watch mode`).

Konfiguracja zostanie zapisana w pliku `scanner_config.json`. Kreator można uruchomić ponownie w każdej chwili:
```bash
olx-scanner --setup
```

---

## ⚙️ Konfiguracja

### Plik zmiennych środowiskowych (`.env`)
Możesz przechowywać swój klucz API w pliku `.env` w katalogu głównym projektu:
```env
DEEPSEEK_API_KEY=twoj_klucz_api_deepseek
```

### Plik konfiguracyjny `scanner_config.json`
Przykładowa zawartość wygenerowana przez instalator:
```json
{
  "language": "pl",
  "api_key": "twoj_klucz_api_deepseek",
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

## 💻 Przykłady Użycia CLI

### Standardowy skan
Skanuje 3 pierwsze strony najnowszych ogłoszeń i kończy pracę:
```bash
olx-scanner --pages 3
```

### Tryb ciągłego monitorowania (Watch Mode)
Skanuje 5 stron, analizuje nowe oferty i ponawia cykl co 60 sekund:
```bash
olx-scanner --pages 5 --watch --interval 60
```

### Zmiana języka z poziomu polecenia
Wymuszenie uruchomienia programu i promptów w języku polskim lub angielskim:
```bash
olx-scanner --lang pl
olx-scanner --lang en
```

### Konfiguracja Proxy
Użycie dedykowanego serwera proxy lub pliku z listą serwerów:
```bash
# Pojedyncze proxy:
olx-scanner --proxy http://user:pass@127.0.0.1:8080

# Lista serwerów proxy (testowana asynchronicznie przed skanem):
olx-scanner --proxy-file proxy.txt --min-proxies 20
```

### Tryb jednoliniowy / przewijany (Inline)
Przydatny dla środowisk CI/CD lub terminali bez obsługi bufora pełnoekranowego:
```bash
olx-scanner --inline
```

---

## 📋 Zestawienie Opcji CLI

| Opcja | Flaga | Opis | Domyślnie |
| :--- | :--- | :--- | :--- |
| **Kreator** | `--setup`, `--reconfigure` | Uruchomienie kreatora pierwszej konfiguracji | `False` |
| **Język** | `--lang` | Wybór języka interfejsu i AI (`pl`, `en`, `uk`, `de`, `be`)| `en` |
| **Klucz API** | `--api-key` | Nadpisanie klucza API DeepSeek | Plik config / `.env` |
| **Model** | `--model` | Identyfikator modelu DeepSeek | `deepseek-v4-flash-vision-exp` |
| **Liczba stron** | `--pages` | Liczba stron OLX do zbadania w cyklu | `3` |
| **Wątki AI** | `--threads` | Liczba równoległych wątków analizy sztucznej inteligencji | `8` |
| **Tryb ciągły** | `--watch` | Włączenie ciągłego monitorowania w pętli | `False` |
| **Interwał** | `--interval` | Liczba sekund przerwy między cyklami w trybie watch | `120` |
| **Proxy** | `--proxy` | Adres statycznego proxy (`http://host:port`) | `None` |
| **Plik Proxy** | `--proxy-file`, `-pf` | Ścieżka do pliku z listą proxy (`.txt` lub `.json`) | `None` |
| **Min. Proxy** | `--min-proxies` | Minimalna liczba sprawnych proxy w puli | `15` |
| **Workerzy Proxy**| `--proxy-workers` | Liczba równoległych zadań testujących proxy | `150` |
| **Tryb Inline** | `--inline` | Wyświetlanie bez czyszczenia ekranu terminala | `False` |
| **Plik Logu** | `--log-file` | Ścieżka do pliku rejestrującego wszystkie zdarzenia | `olx_scanner.log` |

---

## 🗄️ Struktura Bazy Danych (`olx_iphones.db`)

- **`iphone_offers`**:
  - `olx_id`: Unikalny identyfikator ogłoszenia OLX.
  - `title`, `price`, `location`, `posted_at`, `description`, `url`.
  - `ai_analyzed`: Flaga stanu analizy (`0` = oczekuje, `1` = przeanalizowano).
  - `model_name`: Rozpoznany model (np. `iPhone 13 Pro`).
  - `storage_gb`: Pojemność pamięci (np. `128`).
  - `battery_health_pct`: Kondycja baterii w % (lub `NULL`, jeśli brak w opisie).
  - `condition_state`: Opis stanu wizualnego i technicznego.
  - `is_damaged`: Wartość logiczna (1 = telefon uszkodzony, 0 = sprawny).
  - `damage_details`: Wyszczególnione wady i uszkodzenia.
  - `face_id_working`: Sprawność Face ID (1 / 0 / NULL).
  - `icloud_clean`: Brak blokady iCloud (1 / 0 / NULL).
  - `ai_summary`: Zwięzłe, jednozdaniowe podsumowanie rzeczoznawcy.
  - `ai_raw_json`: Pełny, surowy obiekt JSON zwrócony przez DeepSeek.
- **`scanned_pages`**: Historia skanowania podstron z sumami kontrolnymi MD5 dla mechanizmu *early stopping*.

---

## 🧪 Testy Jednostkowe

Uruchomienie zestawu testów przy użyciu `pytest`:
```bash
pytest tests/unit -v
```

---

## 📄 Licencja

Projekt objęty licencją **MIT**. Szczegółowe informacje znajdują się w pliku `LICENSE`.

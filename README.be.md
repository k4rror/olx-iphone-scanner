# olx-iphone-scanner

[![CI](https://github.com/k4rror/olx-iphone-scanner/actions/workflows/ci.yml/badge.svg)](https://github.com/k4rror/olx-iphone-scanner/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![Ліцэнзія: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

[English](README.md) | [Polski](README.pl.md) | [Deutsch](README.de.md) | [Українська](README.uk.md) | **Беларуская**

Скануе аб'явы iPhone на OLX Poland (`olx.pl`) і захоўвае структураваныя ацэнкі ў лакальнай базе SQLite. Старонкі пошуку загружаюцца з TLS-адбіткам Chrome 120, аксэсуары і аб'явы не ад Apple адсяваюцца рэгулярнымі выразамі, а астатнія прапановы адпраўляюцца ў DeepSeek для вымання мадэлі, памяці, стану батарэі, пашкоджанняў і статусу блакіроўкі.

Два інтэрфейсы працуюць з адной базай даных: тэрмінальны інтэрфейс Rich (`olx-scanner`) і вэб-панэль FastAPI/Jinja2 (`olx-dashboard`).

## Хуткі старт

```bash
git clone https://github.com/k4rror/olx-iphone-scanner.git
cd olx-iphone-scanner
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\Activate.ps1
pip install -e .
olx-scanner
```

Пры першым запуску адкрываецца інтэрактыўны майстар (мова, ключ DeepSeek API, рэжым проксі, колькасць старонак), які запісвае `scanner_config.json`. Ключ DeepSeek API абавязковы.

## Магчымасці

- **Адбітак TLS:** `tls-client` наладжаны з профілем Chrome 120 і эмуляванымі загалоўкамі, таму запыты выглядаюць як ад звычайнага браўзера, без сэрвісу рашэння CAPTCHA.
- **Пул проксі:** спісы проксі асінхронна правяраюцца на OLX праз HTTPS-тунэлі і ранжыруюцца перад пачаткам сканавання. Падтрымліваюцца статычны проксі, лакальны рататар або прамое TLS-падключэнне.
- **Эўрыстычны прэ-фільтр:** правілы regex адхіляюць чахлы, скрынкі, зарадныя прылады, запчасткі і іншыя маркі (Samsung, Xiaomi, Pixel) да звароту да DeepSeek, што зніжае выкарыстанне токенаў.
- **Выманне даных DeepSeek:** кожная аб'ява разбіраецца на тыпізаваныя палі (мадэль, памяць у ГБ, колер, стан батарэі ў працэнтах, стан, дэталі пашкоджанняў, Face ID, блакіроўка iCloud) плюс вердыкт у адзін сказ. Няправільныя адказы JSON выпраўляюцца і валідуюцца праз Pydantic.
- **Дэдублікацыя і ранняе спыненне:** адбіткі старонак вылічваюцца з MD5-хэша ідэнтыфікатараў аб'яў на гэтай старонцы. Калі старонка 1 не змянілася з папярэдняга цыклу або наступная старонка не дадала ніводнай новай прапановы, сканаванне спыняецца датэрмінова.
- **Тэрмінальная панэль:** прагляд Rich Live з лічыльнікамі KPI, табліцай нядаўна прааналізаваных прапаноў, прагрэсам і журналам падзей. `--inline` адключае альтэрнатыўны экранны буфер для CI або неінтэрактыўных абалонкаў.
- **Вэб-панэль:** старонкі FastAPI і Jinja2 для кіравання сканэрам, табліца прапаноў (фільтры, сартаванне, абранае, нататкі), аналітыка і экспарт CSV.
- **Захаванне:** SQLite у рэжыме WAL з індэксаванымі калонкамі, бяспечная для адначасовых запісаў.
- **Шматмоўнасць:** радкі інтэрфейсу і промпты ШІ на англійскай, польскай, украінскай, нямецкай і беларускай мовах.

## Усталёўка

### Патрабаванні

- Python 3.10 або навейшы.
- Ключ DeepSeek API з [platform.deepseek.com](https://platform.deepseek.com/).
- Сеткавы доступ да `olx.pl`.

### Усталёўка

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

Базавая ўсталёўка ўключае залежнасці вэб-панэлі (`fastapi`, `uvicorn`, `jinja2`). Каб таксама запусціць тэсты і лінтар:

```bash
pip install -e ".[dev]"
```

## Выкарыстанне

### Тэрмінальны сканэр

```bash
# Майстар наладкі (першы запуск або пасля выдалення scanner_config.json)
olx-scanner

# Паўторны запуск майстра ў любы момант
olx-scanner --setup

# Адзін цыкл па 3 старонках у выбраным рэгіёне, без пытанняў
olx-scanner --non-interactive --pages 3 --region mazowieckie

# Бесперапынны маніторынг: 5 старонак, потым 60 секунд чакання і паўтор
olx-scanner --pages 5 --watch --interval 60

# Прымусовая мова інтэрфейсу і промптаў ШІ
olx-scanner --lang pl

# Проксі: адзін адрас або правераны спіс з файла
olx-scanner --proxy http://user:pass@127.0.0.1:8080
olx-scanner --proxy-file proxies.txt --min-proxies 20

# Неінтэрактыўны вывад для CI або лагавання
olx-scanner --inline
```

Рэгіён можна таксама перадаць як `--wojewodztwo`. Прымальныя значэнні: слагі ваяводстваў, напрыклад `mazowieckie`, `slaskie`, `malopolskie`; прапусціце яго, каб сканаваць усю OLX Poland.

### Параметры CLI

| Сцяг | Апісанне | Па змаўчанні |
| :--- | :--- | :--- |
| `--setup`, `--reconfigure` | Запусціць інтэрактыўны майстар наладкі | `False` |
| `--non-interactive`, `-y` | Прапусціць запыты перад запускам і выкарыстаць захаваны канфіг | `False` |
| `--lang` | Мова інтэрфейсу і промптаў (`en`, `pl`, `uk`, `de`, `be`) | канфіг, інакш `pl` |
| `--region`, `--wojewodztwo` | Слаг ваяводства, напрыклад `mazowieckie` | усе рэгіёны |
| `--api-key` | Перавызначэнне ключа DeepSeek API | канфіг / `.env` |
| `--model` | Ідэнтыфікатар мадэлі DeepSeek | `deepseek-v4-flash-vision-exp` |
| `--proxy` | Адзіночны статычны проксі (`http://host:port`) | `None` |
| `--proxy-file`, `-pf` | Файл са спісам проксі (`.txt` або `.json`) | `None` |
| `--min-proxies` | Мінімальная колькасць сапраўдных проксі ў пуле | `15` |
| `--proxy-workers` | Патокі для праверкі проксі | `150` |
| `--pages` | Старонкі пошуку, якія скануюцца за цыкл | `3` |
| `--threads` | Адначасовыя патокі для аналізу ШІ | `8` |
| `--watch` | Паўтараць сканаванне ў цыкле | `False` |
| `--interval` | Секунды паміж цыкламі ў рэжыме watch | `120` |
| `--inline` | Пракруткавы вывад замест поўнаэкраннага TUI | `False` |
| `--log-file` | Шлях да журнала выканання | `olx_scanner.log` |

### Вэб-панэль

```bash
olx-dashboard
```

Панэль даступная на `http://127.0.0.1:8000` і адкрываецца ў браўзеры па змаўчанні. Кропка ўваходу прымае:

| Сцяг | Апісанне | Па змаўчанні |
| :--- | :--- | :--- |
| `--host` | Адрас прывязкі | `127.0.0.1` |
| `--port` | Порт праслухоўвання | `8000` |
| `--db` | Шлях да файла базы даных SQLite | `olx_iphones.db` |
| `--no-browser` | Не адкрываць браўзер пры запуску | `False` |

Старонкі: `/scanner` (запуск/спыненне сканавання), `/offers` (фільтр, сартаванне, абранае, нататкі, выдаленне, экспарт CSV), `/analytics` (статыстыка цэн па мадэлях і маржа адносна сярэдняй рынкавай цаны).

Панэль дае JSON API над тымі ж данымі. Асноўныя маршруты:

| Метад | Маршрут | Прызначэнне |
| :--- | :--- | :--- |
| `GET` | `/api/stats` | KPI базы даных і зводка аналітыкі |
| `GET` | `/api/offers` | Спіс прапаноў з падзелам на старонкі і фільтрамі |
| `GET` | `/api/offers/{olx_id}` | Дэталі адной прапановы |
| `POST` | `/api/offers/{olx_id}/favorite` | Пераключыць сцяг абранага |
| `PATCH` | `/api/offers/{olx_id}/notes` | Захаваць нататкі карыстальніка |
| `DELETE` | `/api/offers/{olx_id}` | Выдаліць прапанову |
| `GET` | `/api/export` | Экспарт CSV бягучага фільтра |
| `GET` | `/api/models/stats` | Статыстыка цэн і батарэі для мадэлі |
| `GET` | `/api/scanner/status` | Бягучае становішча сканэра |
| `POST` | `/api/scanner/start` | Запусціць цыкл сканавання |
| `POST` | `/api/scanner/stop` | Спыніць бягучае сканаванне |
| `GET` | `/api/scanner/probe` | Колькасць аб'яў і старонак для рэгіёна |

### Канфігурацыя

`.env` у корані праекта:

```env
DEEPSEEK_API_KEY=your_deepseek_api_key_here
OLX_PROXY=
```

`scanner_config.json`, які стварае майстар і можна рэдагаваць уручную:

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

Сцягі каманднага радка маюць прыярытэт над файлам канфігурацыі, а той над `.env`.

## Схема базы даных

SQLite, рэжым WAL, ствараецца аўтаматычна ў `olx_iphones.db`.

`iphone_offers`:

| Калонка | Заўвагі |
| :--- | :--- |
| `id` | Першасны ключ |
| `olx_id` | Ідэнтыфікатар аб'явы OLX, індэксаваны |
| `url`, `title`, `price`, `currency`, `location`, `posted_at`, `description`, `scraped_at` | Зыходныя даныя аб'явы |
| `ai_analyzed` | `0` = у чарзе, `1` = прааналізавана, індэксавана |
| `model_name`, `storage_gb`, `color` | Нармалізаваныя даныя прылады |
| `battery_health_pct` | Цэлае, `NULL`, калі прадавец не пазначыў |
| `condition_state`, `is_damaged`, `damage_details` | Стан і дэфекты, індэксавана па `is_damaged` |
| `face_id_working`, `icloud_clean` | `1` / `0` / `NULL` |
| `ai_summary` | Вердыкт у адзін сказ |
| `ai_raw_json` | Зыходны адказ DeepSeek |
| `is_favorite`, `user_notes` | Дададзены вэб-панэллю |

`scanned_pages`: `page_number`, `scanned_at`, `offers_total`, `new_offers`, `fingerprint` (MD5), `duration_s`. Выкарыстоўваецца для праверкі датэрміновага спынення.

## Тэставанне

```bash
pip install -e ".[dev]"
ruff check .
pytest tests/unit -v
```

Юніт-тэсты працуюць на фікстурах і не патрабуюць сеткавага доступу або ключа API. CI запускае `ruff check .` і `pytest tests/unit/ -v` на Python 3.10, 3.11 і 3.12.

## Абмежаванні

- Вэб-панэль выконвае адзін цыкл сканавання. Бесперапынны рэжым watch адключаны ў вэб-інтэрфейсе (`WATCH_MODE_ENABLED = False` у `src/olx_scanner/web/app.py`); выкарыстоўвайце сцяг CLI `--watch`.
- Стан захоўваецца ў адным лакальным файле SQLite. Няма сервернага разгортвання, аўтэнтыфікацыі і падтрымкі некалькіх карыстальнікаў; панэль па змаўчанні прывязваецца да `127.0.0.1`.
- Скрапер залежыць ад HTML-структуры OLX і зламаецца пры змене разметкі. Няма афлайн-рэжыму або ўбудаванага набору даных.
- Для аналізу патрабуецца платны ключ DeepSeek API. Без яго аб'явы ўсё адно захоўваюцца, але застаюцца неапрацаванымі.
- Гэты праект не звязаны з OLX. Пры зборы даных выконвайце ўмовы абслугоўвання OLX і мясцовае заканадаўства.

## Удзел

Зрабіце форк рэпазіторыя, стварыце тэматычную галіну і ўпэўніцеся, што `ruff check .` і `pytest tests/unit -v` праходзяць, перад стварэннем pull request.

## Ліцэнзія

MIT. Гл. [LICENSE](LICENSE).

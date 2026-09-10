from olx_scanner.i18n.translations import (
    DEFAULT_LANG,
    LANGUAGES,
    TRANSLATIONS,
    get_language,
    set_language,
    t,
    tl,
)
from olx_scanner.i18n.web_translations import WEB_TRANSLATIONS

# Scal tłumaczenia panelu web z bazowym słownikiem (raz, przy imporcie pakietu)
for _lang, _table in WEB_TRANSLATIONS.items():
    TRANSLATIONS.setdefault(_lang, {}).update(_table)

__all__ = ["DEFAULT_LANG", "LANGUAGES", "TRANSLATIONS", "get_language", "set_language", "t", "tl"]
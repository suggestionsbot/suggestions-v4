import json
from pathlib import Path

import hikari
import logoo
from lightbulb import DictLocalizationProvider

from bot.exceptions import MissingTranslation

logger = logoo.Logger(__name__)


class Localisation:
    def __init__(self):
        self._file_to_locale: dict[Path, hikari.Locale] = {
            Path("locales/da.json"): hikari.Locale.DA,
            Path("locales/de.json"): hikari.Locale.DE,
            Path("locales/en_GB.json"): hikari.Locale.EN_GB,
            Path("locales/en_US.json"): hikari.Locale.EN_US,
            Path("locales/fr.json"): hikari.Locale.FR,
            Path("locales/pt_BR.json"): hikari.Locale.PT_BR,
            Path("locales/tr.json"): hikari.Locale.TR,
        }
        data: dict[hikari.Locale, dict[str, str]] = {}
        for k, v in self._file_to_locale.items():
            with open(k, "r", encoding="utf-8") as f:
                as_dict = json.loads(f.read())
                data[v] = as_dict

        self.lightbulb_provider = DictLocalizationProvider(data)

    def get_locale(self, key: str, locale: hikari.Locale) -> str:
        try:
            return self.lightbulb_provider.localizations[locale][key]
        except KeyError:
            fallback_value = self.lightbulb_provider.localizations[locale].get(key)
            if fallback_value is None:
                logger.critical(f"Could not find base translation for {key}")
                raise MissingTranslation  # TODO Handle this on the bots error handler

            return fallback_value

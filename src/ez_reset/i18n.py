from __future__ import annotations

import locale
import os
from dataclasses import dataclass


def language_from_tag(tag: str | None) -> str:
    """Map a locale tag to a supported language code."""
    if not tag:
        return "en"
    normalized = tag.replace("-", "_").split(".")[0].strip().lower()
    if normalized == "es" or normalized.startswith(("es_", "spanish")):
        return "es"
    return "en"


def current_language() -> str:
    override = os.environ.get("EZ_RESET_LANG", "").strip().lower()
    if override in {"en", "es"}:
        return override

    try:
        locale_name = locale.getlocale()[0]
    except ValueError:
        locale_name = None

    if locale_name:
        return language_from_tag(locale_name)

    for key in ("LC_ALL", "LC_MESSAGES", "LANG"):
        if language_from_tag(os.environ.get(key)) == "es":
            return "es"
    return "en"


@dataclass(frozen=True, slots=True)
class Strings:
    app_title: str
    ink_levels: str
    waste_levels: str
    reset_all: str
    refresh: str
    waste_counter: str
    restart_title: str
    restart_body: str
    exception_title: str

    def waste_counter_label(self, index: int) -> str:
        return self.waste_counter.format(index=index)


EN = Strings(
    app_title="ez-reset",
    ink_levels="Ink Levels",
    waste_levels="Waste Levels",
    reset_all="Reset All",
    refresh="Refresh",
    waste_counter="Waste ink counter {index}",
    restart_title="Restart printer",
    restart_body="Waste ink counters have been reset. You must now restart the printer.",
    exception_title="Exception",
)

ES = Strings(
    app_title="ez-reset",
    ink_levels="Niveles de tinta",
    waste_levels="Tinta residual",
    reset_all="Reiniciar todos",
    refresh="Actualizar",
    waste_counter="Contador de tinta residual {index}",
    restart_title="Reinicia la impresora",
    restart_body="Se reiniciaron los contadores de tinta residual. Ahora tienes que reiniciar la impresora.",
    exception_title="Error",
)


def strings_for(language: str | None = None) -> Strings:
    code = language if language in {"en", "es"} else current_language()
    return ES if code == "es" else EN

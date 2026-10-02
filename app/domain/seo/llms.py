"""`/llms.txt` — карта сайта для языковых моделей (формат llmstxt.org).

Sitemap перечисляет URL для краулера, а llms.txt объясняет модели, ЧТО это за сайт и куда
смотреть в первую очередь: заголовок H1, короткая выжимка в цитате и разделы со списками
ссылок. Модели читают его как Markdown, поэтому формат строгий: без H1 и без ссылок файл
считается невалидным (так его и отбраковывает Lighthouse).

Раздел с заголовком `Optional` в формате особый: модель может его пропустить, если ей не
хватает контекста. Туда уходит второстепенное — карта сайта и бот.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

OPTIONAL_SECTION = "Optional"


@dataclass(frozen=True, slots=True)
class LlmsLink:
    title: str
    url: str
    note: str = ""


@dataclass(frozen=True, slots=True)
class LlmsSection:
    title: str
    links: Sequence[LlmsLink] = field(default_factory=tuple)


def _md_text(text: str) -> str:
    """Убрать из подписи то, что ломает разметку ссылки `[...](...)` и строку списка."""
    return " ".join(text.replace("[", "(").replace("]", ")").split())


def _link_line(link: LlmsLink) -> str:
    line = f"- [{_md_text(link.title)}]({link.url})"
    return f"{line}: {_md_text(link.note)}" if link.note else line


def render_llms_txt(
    *, title: str, summary: str, details: Sequence[str], sections: Sequence[LlmsSection]
) -> str:
    """Собрать файл. Пустые разделы пропускаются: заголовок без ссылок модели ничего не даёт."""
    parts = [f"# {_md_text(title)}", f"> {_md_text(summary)}", *details]
    for section in sections:
        if section.links:
            lines = "\n".join(_link_line(link) for link in section.links)
            parts.append(f"## {section.title}\n\n{lines}")
    return "\n\n".join(parts) + "\n"

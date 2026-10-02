"""Тесты рендера `/llms.txt` (`domain/seo/llms`): формат, который требуют модели и Lighthouse."""

from __future__ import annotations

from app.domain.seo.llms import OPTIONAL_SECTION, LlmsLink, LlmsSection, render_llms_txt


def _render(*sections: LlmsSection) -> str:
    return render_llms_txt(title="QazaqCinema", summary="Кино", details=[], sections=sections)


def test_file_starts_with_h1_and_summary_quote() -> None:
    """⚠️ Без H1 в первой строке файл считается невалидным — именно это ловил Lighthouse."""
    lines = _render().splitlines()

    assert lines[0] == "# QazaqCinema"
    assert lines[2] == "> Кино"


def test_links_render_as_markdown_list_with_note() -> None:
    body = _render(
        LlmsSection("Каталог", [LlmsLink("Весь каталог", "https://x.kz/catalog", "поиск")])
    )

    assert "## Каталог\n\n- [Весь каталог](https://x.kz/catalog): поиск" in body


def test_empty_section_is_skipped() -> None:
    """Заголовок без ссылок модели ничего не даёт (например, ни один год не набрал порога)."""
    body = _render(LlmsSection("По годам", []), LlmsSection(OPTIONAL_SECTION, [LlmsLink("a", "u")]))

    assert "По годам" not in body
    assert "## Optional" in body


def test_brackets_in_titles_do_not_break_link_syntax() -> None:
    """Название фильма со скобками `[...]` иначе закрыло бы подпись ссылки раньше времени."""
    body = _render(LlmsSection("Фильмы", [LlmsLink("Шрек [2001]", "https://x.kz/m/1")]))

    assert "- [Шрек (2001)](https://x.kz/m/1)" in body

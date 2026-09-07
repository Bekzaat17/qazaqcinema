"""Квиз — домен: нормализация, чекеры, рендереры, текст разбора. Без БД и Telegram."""

from __future__ import annotations

from app.domain.channel.content.answers.checkers import ChoiceChecker, OpenChecker
from app.domain.channel.content.answers.normalize import fold, levenshtein
from app.domain.channel.content.answers.result import QuizStats, render_result
from app.domain.channel.content.item import CHOICE_LETTERS, ContentItem, QuizChoice, QuizOpen
from app.domain.channel.content.kinds import ContentKind
from app.domain.channel.content.render import RENDERERS
from app.domain.channel.content.render.quiz import (
    QuizChoiceRenderer,
    QuizOpenRenderer,
    callback_data,
    parse_callback,
)

# ── нормализация ─────────────────────────────────────────────────────────────


def test_fold_unifies_layout_and_scripts() -> None:
    """Русская раскладка, латиница-2021 и казахская кириллица — одна форма."""
    assert fold("Құлын") == fold("кулын") == fold("qulyn") == fold("Qūlyn")
    assert fold("  Түйе!  ") == fold("tuie") == "туие"
    assert fold("Жетіқарақшы") == fold("Zhetiqaraqshy")


def test_fold_strips_punctuation_and_collapses_spaces() -> None:
    assert fold("«Тай», деп ойлаймын.") == "таи деп оилаимин"


def test_levenshtein_basic() -> None:
    assert levenshtein("кулын", "кулин") == 1
    assert levenshtein("кой", "той") == 1
    assert levenshtein("", "абв") == 3


# ── чекеры ───────────────────────────────────────────────────────────────────


def test_choice_checker_compares_index() -> None:
    checker = ChoiceChecker(QuizChoice("q", ("а", "б", "в"), answer=1))
    assert checker.is_correct("1")
    assert not checker.is_correct("0") and not checker.is_correct("x")


def test_open_checker_accepts_variants_layouts_and_typos() -> None:
    checker = OpenChecker(QuizOpen("Жұмбақ", ("құлын", "жылқының баласы")))
    assert checker.is_correct("Құлын")
    assert checker.is_correct("кулын")          # русская раскладка
    assert checker.is_correct("qulyn")          # латиница
    assert checker.is_correct("кулин")          # одна опечатка в слове ≥5 букв
    assert checker.is_correct("Менің ойымша, құлын!")   # ответ внутри фразы
    assert checker.is_correct("жылкынын баласы")


def test_open_checker_rejects_wrong_and_short_typos() -> None:
    checker = OpenChecker(QuizOpen("Жұмбақ", ("қой",)))
    assert checker.is_correct("қой") and checker.is_correct("koi")
    assert not checker.is_correct("той")        # короткое слово — опечатки не прощаем
    assert not checker.is_correct("")
    assert not checker.is_correct("түйе")


# ── рендереры ────────────────────────────────────────────────────────────────


def _choice_item() -> ContentItem:
    return ContentItem(
        id=7, slug="maqal-01", kind=ContentKind.QUIZ_CHOICE, topic="maqal",
        title_kk="Мақалды жалғастыр", body_kk="",
        payload=QuizChoice(
            "Еңбек етсең ерінбей…",
            ("тояды қарның тіленбей", "жетер бақыт үйіңе", "дау артынан дау"),
            answer=0,
        ),
    )


def _open_item() -> ContentItem:
    return ContentItem(
        id=9, slug="zhumbaq-01", kind=ContentKind.QUIZ_OPEN, topic="zhumbaq",
        title_kk="Жұмбақ", body_kk="",
        payload=QuizOpen("Аяғы жоқ, қолы жоқ, <есік> ашады", ("жел", "самал")),
    )


def test_both_quiz_forms_are_registered() -> None:
    assert RENDERERS.get(ContentKind.QUIZ_CHOICE.value) is QuizChoiceRenderer
    assert RENDERERS.get(ContentKind.QUIZ_OPEN.value) is QuizOpenRenderer


def test_choice_post_lists_options_and_has_matching_buttons() -> None:
    post = QuizChoiceRenderer().render(_choice_item())
    assert "🗣 <b>Мақал-мәтел</b>" in post.head
    assert "А) тояды қарның тіленбей" in post.head and "Б) дау артынан дау" in post.head
    assert [b.text for b in post.buttons] == list(CHOICE_LETTERS[:3])
    assert [b.data for b in post.buttons] == ["qz:7:0", "qz:7:1", "qz:7:2"]
    assert post.head.endswith("#МақалМәтел #ҚазақшаҮйренеміз")


def test_open_post_invites_to_comments_and_escapes_question() -> None:
    post = QuizOpenRenderer().render(_open_item())
    assert post.buttons == ()
    assert "комментарийге" in post.head
    assert "&lt;есік&gt;" in post.head and "#Жұмбақ" in post.head


def test_callback_data_roundtrip_and_garbage() -> None:
    assert parse_callback(callback_data(7, 2)) == (7, 2)
    assert parse_callback("qz:x:1") is None
    assert parse_callback("pay:7:2") is None
    assert parse_callback("qz:7") is None


# ── разбор ───────────────────────────────────────────────────────────────────


def test_result_names_answer_counts_and_podium() -> None:
    text = render_result(_choice_item(), QuizStats(47, 31, ("Айгүл", "Ерлан", "Дана")))
    assert "А) тояды қарның тіленбей" in text
    assert "47 адам жауап берді, 31 дұрыс тапты" in text
    assert "🥇 Айгүл · 🥈 Ерлан · 🥉 Дана" in text
    assert text.endswith("#МақалМәтел #ҚазақшаҮйренеміз")


def test_result_with_no_answers_is_friendly() -> None:
    text = render_result(_open_item(), QuizStats(0, 0, ()))
    assert "Жауабы: <b>жел</b>" in text
    assert "жауап берген болмады" in text

from __future__ import annotations

import json
import re
from unittest.mock import AsyncMock

import httpx
from app.api.app import create_app
from app.application.services.catalog_service import CatalogService
from app.application.services.seo_service import SeoBuilder
from app.config.settings import AppConfig
from app.domain.seo.games import GAMES_DESCRIPTION, GAMES_TITLE
from dishka import Provider, Scope, make_async_container, provide


async def test_games_page_is_indexable_without_auth_or_javascript_and_has_both_play_links() -> None:
    class TestProvider(Provider):
        scope = Scope.APP

        @provide
        def config(self) -> AppConfig:
            return AppConfig(public_origin="https://play.example")

        @provide
        def seo(self) -> SeoBuilder:
            return SeoBuilder("https://play.example", "our_bot")

        @provide
        def catalog(self) -> CatalogService:
            fake = AsyncMock(spec=CatalogService)
            fake.all_movies.return_value = []
            fake.category_counts.return_value = []
            fake.year_counts.return_value = {}
            return fake

    container = make_async_container(TestProvider())
    app = create_app(container)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/games")
        assert response.status_code == 200
        html = response.text
        assert f"<title>{GAMES_TITLE}</title>" in html
        assert len(GAMES_DESCRIPTION) <= 160
        assert 'rel="canonical" href="https://play.example/games"' in html
        assert 'content="index,follow,max-image-preview:large"' in html
        assert 'href="https://t.me/our_bot?startapp=quest"' in html
        assert 'href="/quest"' in html
        assert "Қалай ойнауға болады?" in html and "Алматы" in html and "Түркістан" in html
        assert "Жиі қойылатын сұрақтар" in html and "Арнаға" not in GAMES_TITLE
        script = re.search(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)
        assert script
        data = json.loads(script.group(1))
        assert data["@type"] == "VideoGame" and data["inLanguage"] == "kk"
        assert data["potentialAction"]["target"] == "https://t.me/our_bot?startapp=quest"
        sitemap = (await client.get("/sitemap.xml")).text
        assert "https://play.example/games" in sitemap
        assert "Disallow: /games" not in (await client.get("/robots.txt")).text
    await container.close()

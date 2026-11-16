import pytest
from unittest.mock import AsyncMock, patch
from bson import ObjectId
from app.services.competitor_service import CompetitorService


@pytest.mark.asyncio
async def test_competitor_crud():
    mock_db = AsyncMock()

    # Mock insert
    fake_id = ObjectId()
    mock_db.competitors.find_one = AsyncMock(return_value=None)
    mock_db.competitors.insert_one = AsyncMock(return_value=AsyncMock(inserted_id=fake_id))

    service = CompetitorService(mock_db)
    created = await service.create_competitor({
        "name": "Competitor Agency",
        "website": "https://competitoragency.com",
        "business_category": "SEO Agency",
    })

    assert created["name"] == "Competitor Agency"
    assert created["domain"] == "competitoragency.com"
    assert created["business_category"] == "SEO Agency"


@pytest.mark.asyncio
async def test_competitor_discovery():
    mock_db = AsyncMock()
    mock_db.competitors.find_one = AsyncMock(return_value=None)
    service = CompetitorService(mock_db)

    mock_search_results = [
        {
            "title": "Agency Alpha - Digital Branding",
            "url": "https://agencyalpha.com",
            "snippet": "Leading personal branding and reputation management firm.",
        },
        {
            "title": "Agency Beta - PR & Authority",
            "url": "https://agencybeta.io",
            "snippet": "Executive branding and knowledge panel experts.",
        },
    ]

    with patch("app.services.competitor_service.is_safe_url", return_value=(True, "")):
        with patch.object(service.ddgs, "search", return_value=mock_search_results):
            discovered = await service.discover_competitors(seed_terms="Personal branding agency", category="Agency")
            assert len(discovered) == 2
            assert discovered[0]["domain"] == "agencyalpha.com"
            assert discovered[1]["domain"] == "agencybeta.io"
            assert discovered[0]["already_saved"] is False

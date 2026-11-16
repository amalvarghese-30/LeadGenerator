import pytest
from unittest.mock import patch
from app.services.profile_creator_service import AutoProfileCreatorService


@pytest.mark.asyncio
async def test_auto_profile_creator_discovery():
    service = AutoProfileCreatorService(db=None)

    mock_results = [
        {
            "title": "Jane Doe - Chief Technology Officer - Acme Tech | LinkedIn",
            "url": "https://linkedin.com/in/janedoe-tech",
            "snippet": "Jane Doe is the CTO at Acme Tech leading distributed systems engineering.",
        },
        {
            "title": "Jane Doe (janedoe) · GitHub",
            "url": "https://github.com/janedoe",
            "snippet": "Jane Doe - Open source developer at Acme Tech. Python, Rust, Go.",
        },
        {
            "title": "Jane Doe (@janedoe) / X",
            "url": "https://twitter.com/janedoe",
            "snippet": "CTO @ Acme Tech. Tech enthusiast and conference speaker.",
        },
    ]

    with patch.object(service.ddgs, "search", return_value=mock_results):
        candidate = await service.discover_profile(
            full_name="Jane Doe",
            company="Acme Tech",
            designation="Chief Technology Officer",
        )

        assert candidate["full_name"] == "Jane Doe"
        assert candidate["platform_profiles"].get("linkedin") == "https://linkedin.com/in/janedoe-tech"
        assert candidate["platform_profiles"].get("github") == "https://github.com/janedoe"
        assert candidate["platform_profiles"].get("twitter") == "https://twitter.com/janedoe"
        assert candidate["confidence_score"] >= 0.8
        assert candidate["confidence_level"] == "high"
        assert len(candidate["evidence_items"]) > 0


@pytest.mark.asyncio
async def test_auto_profile_creator_mismatch_penalty():
    service = AutoProfileCreatorService(db=None)

    # Search results that do not mention the requested company
    mock_results = [
        {
            "title": "Jane Doe - Chef at Paris Bistro | LinkedIn",
            "url": "https://linkedin.com/in/janedoe-chef",
            "snippet": "Jane Doe is a culinary artist in Paris with experience in French cuisine.",
        }
    ]

    with patch.object(service.ddgs, "search", return_value=mock_results):
        candidate = await service.discover_profile(
            full_name="Jane Doe",
            company="Google DeepMind",  # Deliberate mismatch
            designation="AI Research Scientist",
        )

        # Confidence should be low because company and title were not found
        assert candidate["confidence_score"] < 0.6
        assert candidate["confidence_level"] == "low"

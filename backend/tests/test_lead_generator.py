import pytest
from unittest.mock import MagicMock, patch
from app.services.lead_generator_service import (
    EntityClassifier,
    SearchOrchestrator,
    LeadGeneratorService,
)


def test_entity_classification():
    # Individual with personal profile URL
    indiv_url = EntityClassifier.classify(
        "John Doe", "Founder and CEO at TechCorp", "https://linkedin.com/in/johndoe"
    )
    assert indiv_url["entity_type"] == "individual"
    assert indiv_url["confidence"] >= 0.8

    # Company with directory URL
    comp_url = EntityClassifier.classify(
        "Acme Corp", "Leading provider of cloud infrastructure", "https://linkedin.com/company/acmeproducts"
    )
    assert comp_url["entity_type"] == "company"
    assert comp_url["confidence"] >= 0.8

    # Organisation based on keywords
    org = EntityClassifier.classify(
        "Global Climate Initiative", "A charity foundation promoting green energy", "https://climateinitiative.org/about"
    )
    assert org["entity_type"] == "organisation"

    # Business based on corporate keywords
    biz = EntityClassifier.classify(
        "Apex Digital Solutions Ltd", "Enterprise software solutions and consulting group", "https://apexsolutions.io"
    )
    assert biz["entity_type"] == "company"

    # Unknown
    unk = EntityClassifier.classify(
        "Random Page 123", "Some generic notes without clear entity markers", "https://example.com/page123"
    )
    assert unk["entity_type"] == "unknown"
    assert unk["needs_review"] is True


def test_search_provider_failure_graceful():
    orchestrator = SearchOrchestrator()
    with patch.object(orchestrator.ddgs, "search", side_effect=Exception("DDGS network connection timeout")):
        res = orchestrator.execute_search("test query")
        assert res["results"] == []
        assert "failed" in res["source_status"]["ddgs"]


@pytest.mark.asyncio
async def test_company_search_mode():
    service = LeadGeneratorService(db=None)
    mock_results = [
        {
            "title": "Stripe: Financial Infrastructure for the Internet",
            "url": "https://stripe.com",
            "snippet": "Stripe is a suite of APIs powering online payment processing.",
        },
        {
            "title": "Stripe - LinkedIn",
            "url": "https://linkedin.com/company/stripe",
            "snippet": "Stripe is a technology company building infrastructure for commerce.",
        },
    ]

    with patch.object(service.orchestrator, "execute_search", return_value={"results": mock_results, "source_status": {"ddgs": "success"}}):
        out = await service.search_company(
            company_name="Stripe",
            website="https://stripe.com",
            industry="Fintech",
        )
        assert out["mode"] == "company"
        assert len(out["results"]) == 2
        assert out["results"][0]["is_official_website"] is True
        assert out["results"][1]["social_platform"] == "linkedin"


@pytest.mark.asyncio
async def test_individual_search_mode_and_matching():
    service = LeadGeneratorService(db=None)
    mock_results = [
        {
            "title": "Patrick Collison - CEO & Co-Founder @ Stripe | LinkedIn",
            "url": "https://linkedin.com/in/patrickcollison",
            "snippet": "Patrick Collison is the CEO and Co-Founder of Stripe based in San Francisco.",
        },
        {
            "title": "Patrick Collison - High School Teacher in Texas",
            "url": "https://randomnews.com/patrick-collison-texas",
            "snippet": "Patrick Collison is a high school physics instructor.",
        },
    ]

    with patch.object(service.orchestrator, "execute_search", return_value={"results": mock_results, "source_status": {"ddgs": "success"}}):
        out = await service.search_individual(
            full_name="Patrick Collison",
            company="Stripe",
            job_title="CEO",
        )
        assert out["mode"] == "individual"
        assert len(out["results"]) == 2
        # First one corroborated company & title -> high confidence
        assert out["results"][0]["confidence"] > out["results"][1]["confidence"]
        assert out["results"][0]["corroborated_company"] is True
        assert out["results"][1]["corroborated_company"] is False

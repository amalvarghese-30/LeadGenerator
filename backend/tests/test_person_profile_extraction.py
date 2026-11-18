"""
Regression tests for Person Profile Extraction, Social Discovery & Contact Enrichment (Workflow B).
Ensures individual profile pages (e.g. wikipoint.org/wiki/Beenu_Kumar_Taneja) are successfully
extracted, verified, and enriched independently of B2B client reference classification.
"""
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from app.crawler.content_extractor import ContentExtractor
from app.discovery.social_discovery import SocialDiscovery
from app.extraction.person_profile_extractor import PersonProfileExtractor
from app.enrichment.public_email_extractor import PublicEmailExtractor
from app.enrichment.contact_enrichment_service import ContactEnrichmentService
from app.workers.job_processor import JobProcessor


@pytest.fixture
def beenu_taneja_html() -> str:
    fixture_path = Path(__file__).parent / "fixtures" / "wikipoint_beenu_taneja.html"
    return fixture_path.read_text(encoding="utf-8")


def test_social_discovery_extended_platforms():
    """Verify social discovery recognizes all extended platforms and extracts clean handles."""
    sd = SocialDiscovery()

    test_cases = [
        ("https://www.linkedin.com/in/beenukumartaneja?utm_source=share", "linkedin", "beenukumartaneja"),
        ("https://x.com/beenutaneja", "twitter", "beenutaneja"),
        ("https://twitter.com/beenutaneja", "twitter", "beenutaneja"),
        ("https://www.instagram.com/beenu_taneja/", "instagram", "beenu_taneja"),
        ("https://www.youtube.com/@beenutaneja", "youtube", "beenutaneja"),
        ("https://github.com/beenutaneja", "github", "beenutaneja"),
        ("https://www.threads.net/@beenutaneja", "threads", "beenutaneja"),
        ("https://t.me/beenutaneja", "telegram", "beenutaneja"),
        ("https://medium.com/@beenutaneja", "medium", "beenutaneja"),
        ("https://beenutaneja.substack.com", "substack", "beenutaneja"),
    ]

    for url, expected_plat, expected_handle in test_cases:
        res = sd._classify_url(url)
        assert res is not None, f"Failed to classify {url}"
        assert res["platform"] == expected_plat, f"Expected {expected_plat} for {url}, got {res['platform']}"
        assert res["handle"] == expected_handle, f"Expected {expected_handle} for {url}, got {res['handle']}"


def test_obfuscated_email_extraction(beenu_taneja_html):
    """Verify obfuscated email 'beenu [at] beenutaneja [dot] com' is cleanly de-obfuscated."""
    emails = PublicEmailExtractor.extract_from_html(
        beenu_taneja_html,
        source_url="https://wikipoint.org/wiki/Beenu_Kumar_Taneja",
        target_person_name="Beenu Kumar Taneja"
    )
    email_values = [e.value for e in emails]
    assert "beenu@beenutaneja.com" in email_values
    extracted = next(e for e in emails if e.value == "beenu@beenutaneja.com")
    assert extracted.scope == "person_direct_work"


def test_beenu_kumar_taneja_profile_extraction(beenu_taneja_html):
    """Verify full person profile extraction on WikiPoint Beenu Kumar Taneja fixture."""
    extractor = ContentExtractor()
    page_data = extractor.extract(beenu_taneja_html, "https://wikipoint.org/wiki/Beenu_Kumar_Taneja")

    person_extractor = PersonProfileExtractor()
    is_person, conf, reason = person_extractor.is_person_profile_page(page_data)
    assert is_person is True
    assert conf >= 0.50

    profile = person_extractor.extract_profile(page_data, beenu_taneja_html)
    assert profile is not None
    assert profile["person_name"] == "Beenu Kumar Taneja"
    assert "Taneja Enterprises" in (profile.get("company_name") or "")
    assert any(term in (profile.get("designation") or "").lower() for term in ["author", "entrepreneur", "consultant"])
    assert "New Delhi" in (profile.get("location") or "")

    # Bio summary should not contain wiki reference footnotes [1] or [2]
    bio = profile.get("bio_summary", "")
    assert "Beenu Kumar Taneja" in bio
    assert "[1]" not in bio
    assert "[2]" not in bio

    # Social channels
    social_urls = {s["platform"]: s["url"] for s in profile.get("social_profiles", [])}
    assert "linkedin" in social_urls
    assert "twitter" in social_urls
    assert "instagram" in social_urls
    assert "youtube" in social_urls
    assert "github" in social_urls

    # Confidence score should be high
    assert profile["confidence_score"] >= 0.80
    assert len(profile["confidence_reasons"]) >= 3


@pytest.mark.asyncio
async def test_crawler_merges_rendered_dom_contacts():
    """Verify that when Playwright/Selenium renders a page, newly discovered contacts in the DOM are preserved."""
    from app.crawler.crawler_manager import CrawlerManager
    cm = CrawlerManager(max_pages=5)

    # Initial thin HTML
    thin_html = "<html><head><title>Dynamic Bio</title></head><body>Loading profile...</body></html>"

    # Rendered DOM containing contacts
    rendered_dom = """
    <html>
      <head><title>Full Bio - John Doe</title></head>
      <body>
        <h1>John Doe</h1>
        <p>Executive Director at TechCorp. Contact at john@techcorp.com or +91 98765 43210.</p>
        <a href="https://linkedin.com/in/johndoe">LinkedIn</a>
      </body>
    </html>
    """

    with patch.object(cm, "_playwright_render", new_callable=AsyncMock) as mock_render:
        extractor = ContentExtractor()
        content = extractor.extract(rendered_dom, "https://example.com/profile")
        mock_render.return_value = {
            **content,
            "title": "Full Bio - John Doe",
        }

        with patch("httpx.AsyncClient.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.headers = {"content-type": "text/html"}
            mock_resp.url = "https://example.com/profile"
            mock_resp.text = thin_html
            mock_get.return_value = mock_resp

            res = await cm.crawl_url("https://example.com/profile")
            assert res["status"] == "success"
            assert res["javascript_rendered"] is True
            assert "john@techcorp.com" in res["public_emails"]
            assert any(s["platform"] == "linkedin" for s in res["social_profiles"])


@pytest.mark.asyncio
async def test_pipeline_b_creates_contact_and_lead_with_zero_client_references(beenu_taneja_html):
    """
    Critical requirement: When crawling an individual profile where ClientClassifier returns
    0 client references, Pipeline B MUST extract the person profile, create CRM contact,
    create CRM lead, and generate a Report Mode B (Person Intelligence Report).
    """
    db = MagicMock()
    db.crawl_jobs = MagicMock()
    db.crawl_jobs.update_one = AsyncMock()
    db.crawl_jobs.find_one = AsyncMock(return_value={"status": "running"})
    db.research_reports = MagicMock()
    db.research_reports.replace_one = AsyncMock()
    db.job_events = MagicMock()
    db.job_events.insert_one = AsyncMock()
    db.contacts = MagicMock()
    db.contacts.find_one = AsyncMock(return_value=None)
    db.companies = MagicMock()
    db.companies.find_one = AsyncMock(return_value=None)

    processor = JobProcessor()

    # Page data simulated from Wikipoint fixture
    extractor = ContentExtractor()
    page_data = extractor.extract(beenu_taneja_html, "https://wikipoint.org/wiki/Beenu_Kumar_Taneja")
    page_data["status"] = "success"

    # Mock crawler to return this single page
    processor.crawler_manager.crawl_urls = AsyncMock(return_value=[page_data])
    processor.discovery_manager.discover_all_urls = AsyncMock(return_value={
        "discovered_urls": [{"url": "https://wikipoint.org/wiki/Beenu_Kumar_Taneja"}],
        "sources_breakdown": {}
    })

    # Mock client_classifier to return 0 client references (Workflow A finds nothing)
    processor.client_classifier.process_page_detailed = AsyncMock(return_value=([], [], {}))

    # Mock CRM services
    with patch("app.workers.job_processor.ContactService") as MockContactService, \
         patch("app.workers.job_processor.LeadService") as MockLeadService, \
         patch("app.workers.job_processor.CompanyService") as MockCompanyService, \
         patch("app.workers.job_processor.ReferenceService"):

        mock_c_inst = MagicMock()
        mock_c_inst.create = AsyncMock(return_value=({"id": "contact_123", "full_name": "Beenu Kumar Taneja"}, True))
        MockContactService.return_value = mock_c_inst

        mock_l_inst = MagicMock()
        mock_l_inst.create = AsyncMock(return_value=({"id": "lead_123", "created": True}))
        MockLeadService.return_value = mock_l_inst

        mock_comp_inst = MagicMock()
        mock_comp_inst.create = AsyncMock(return_value=({"id": "comp_123", "created": True}))
        MockCompanyService.return_value = mock_comp_inst

        # Process the job
        job_doc = {
            "_id": "64f1a2b3c4d5e6f7a8b9c0d1",
            "provider_id": "test_provider",
            "starting_url": "https://wikipoint.org/wiki/Beenu_Kumar_Taneja",
            "job_type": "person_profile",
            "max_pages": 10,
        }

        await processor.process_job(job_doc, db)

        # Assert contact was created
        mock_c_inst.create.assert_called_once()
        created_contact_arg = mock_c_inst.create.call_args[0][0]
        assert created_contact_arg["full_name"] == "Beenu Kumar Taneja"
        assert created_contact_arg["linkedin_url"] == "https://www.linkedin.com/in/beenukumartaneja"

        # Assert lead was generated
        mock_l_inst.create.assert_called_once()

        # Assert report was stored with report_mode = 'person'
        db.research_reports.replace_one.assert_called_once()
        report_saved = db.research_reports.replace_one.call_args[0][1]
        assert report_saved["report_mode"] == "person"
        assert report_saved["person_profile"]["person_name"] == "Beenu Kumar Taneja"
        assert report_saved["references_found"] == 0  # 0 client references preserved honestly

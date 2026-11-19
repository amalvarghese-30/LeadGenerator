import pytest
import gzip
from app.config import settings
from app.discovery.url_normalizer import is_crawlable_content_url
from app.discovery.internal_links import InternalLinkCrawler
from app.crawler.crawler_manager import CrawlerManager
from app.extraction.person_profile_extractor import PersonProfileExtractor
from unittest.mock import MagicMock


def test_default_page_limit_config():
    """Verify crawler defaults to 50 pages with safety max 500."""
    assert settings.CRAWLER_MAX_PAGES_PER_JOB == 50
    assert settings.CRAWLER_SAFETY_MAX_PAGES == 500


def test_is_crawlable_content_url_rejects_assets():
    """Verify static assets, binaries, fonts, media, and CMS system files are rejected."""
    rejected_urls = [
        "https://example.com/style.css",
        "https://example.com/bundle.js?v=123",
        "https://example.com/app.js.map",
        "https://example.com/logo.png",
        "https://example.com/photo.jpeg",
        "https://example.com/banner.webp",
        "https://example.com/icon.svg",
        "https://example.com/font.woff2",
        "https://example.com/document.pdf",
        "https://example.com/archive.zip",
        "https://example.com/wp-content/plugins/slider/style.css",
        "https://example.com/wp-admin/login.php",
    ]
    for url in rejected_urls:
        assert not is_crawlable_content_url(url), f"Expected {url} to be rejected"


def test_is_crawlable_content_url_accepts_content():
    """Verify legitimate HTML content pages are accepted."""
    accepted_urls = [
        "https://example.com/portfolio",
        "https://example.com/portfolio/project-1",
        "https://example.com/case-studies/client-a",
        "https://example.com/about-us",
        "https://example.com/work?category=web",
        "https://example.com/services/consulting",
    ]
    for url in accepted_urls:
        assert is_crawlable_content_url(url), f"Expected {url} to be accepted"


def test_internal_crawler_respects_max_pages():
    """Verify InternalLinkCrawler enforces max_pages parameter."""
    crawler = InternalLinkCrawler(max_pages=15)
    assert crawler.max_pages == 15
    # Default without explicit max_pages falls back to 50
    default_crawler = InternalLinkCrawler()
    assert default_crawler.max_pages == 50


def test_safe_decode_response_gzip():
    """Verify gzip compressed content is decompressed to UTF-8 text."""
    sample_html = "<html><head><title>Portfolio</title></head><body>Projects</body></html>"
    compressed_bytes = gzip.compress(sample_html.encode("utf-8"))

    mock_resp = MagicMock()
    mock_resp.headers = {"content-encoding": "gzip"}
    mock_resp.content = compressed_bytes
    mock_resp.text = compressed_bytes.decode("latin-1")  # raw corrupted text

    decoded = CrawlerManager._safe_decode_response(mock_resp)
    assert decoded == sample_html
    assert "Portfolio" in decoded


def test_error_page_rejected_from_person_extraction():
    """Verify 'Page Not Found', '404', and error titles are rejected as person candidates."""
    extractor = PersonProfileExtractor()

    error_page = {
        "url": "https://example.com/author/admin",
        "title": "Page Not Found - Example Site",
        "h1": "Page Not Found",
        "main_text": "The page you were looking for doesn't exist or may have been moved. Let's get you back on track.",
        "word_count": 25,
        "public_emails": ["info@example.com"],
        "social_profiles": [],
    }

    is_person, confidence, reason = extractor.is_person_profile_page(error_page)
    assert not is_person, f"Error page was incorrectly detected as a person: reason={reason}"

    profile = extractor.extract_profile(error_page)
    # Profile must be None or reject the error name
    if profile:
        name = profile.get("person_name", "").lower()
        assert "not found" not in name
        assert "error" not in name
        assert "page" not in name


def test_person_extractor_validates_real_person():
    """Verify legitimate person profiles are properly identified."""
    extractor = PersonProfileExtractor()

    real_person_page = {
        "url": "https://theperson.in/p/adv-ramesh-sharma/",
        "title": "Adv. Ramesh Sharma - Senior Advocate",
        "h1": "Adv. Ramesh Sharma",
        "main_text": "Adv. Ramesh Sharma is an advocate based in Mumbai with over 35 years of standing at the Bar. He practices in real estate law, property conveyancing, society deemed conveyance, and civil matters.",
        "word_count": 150,
        "public_emails": [],
        "social_profiles": [{"platform": "linkedin", "url": "https://linkedin.com/in/ramesh-sharma"}],
    }

    is_person, confidence, reason = extractor.is_person_profile_page(real_person_page)
    assert is_person
    assert confidence > 0.4
    profile = extractor.extract_profile(real_person_page)
    assert profile is not None
    assert "Ramesh Sharma" in profile["person_name"]

import pytest
from app.utils.ssrf_guard import is_safe_url
from app.discovery.url_normalizer import URLNormalizer
from app.discovery.ddgs_search import DDGSSearch
from app.discovery.google_dorking import GoogleDorkingHelper

def test_ssrf_guard_blocks_private_and_localhost():
    # Localhost tests
    assert is_safe_url("http://localhost")[0] is False
    assert is_safe_url("http://127.0.0.1")[0] is False
    assert is_safe_url("http://localhost:8080/admin")[0] is False

    # Cloud metadata endpoint
    assert is_safe_url("http://169.254.169.254/latest/meta-data")[0] is False

    # Private IP ranges
    assert is_safe_url("http://192.168.1.1/router")[0] is False
    assert is_safe_url("http://10.0.0.1/internal")[0] is False

    # Non-HTTP protocols
    assert is_safe_url("file:///etc/passwd")[0] is False
    assert is_safe_url("gopher://127.0.0.1:70")[0] is False

    # Public URLs (safe)
    assert is_safe_url("https://theperson.in/")[0] is True
    assert is_safe_url("https://www.google.com")[0] is True

def test_url_normalizer():
    normalizer = URLNormalizer()

    # Normalization: lowercases scheme and host, removes fragments, strips trailing slashes
    url1 = "HTTPS://ThePerson.IN/services/#pricing"
    url2 = "https://theperson.in/services"
    assert normalizer.normalize(url1) == normalizer.normalize(url2)

    # Domain extraction
    assert normalizer.extract_domain("https://blog.theperson.in/about") == "theperson.in"
    assert normalizer.is_same_domain("https://theperson.in/case-studies", "https://theperson.in/contact") is True
    assert normalizer.is_same_domain("https://theperson.in/", "https://competitor.com/") is False

def test_google_dorking_query_generation():
    helper = GoogleDorkingHelper()
    queries = helper.generate_queries("theperson.in", "The Person")
    assert len(queries) >= 8
    assert any("case study" in q["query"] for q in queries)
    assert any("testimonials" in q["query"] for q in queries)
    assert any("linkedin.com" in q["query"] for q in queries)

def test_ddgs_search_graceful_failure():
    searcher = DDGSSearch(max_results=5)
    # Search should return a list and never crash/raise unhandled exception even if network blocked
    results = searcher.search("The Person brand personal branding")
    assert isinstance(results, list)

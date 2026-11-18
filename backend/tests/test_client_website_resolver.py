import pytest
from app.discovery.client_website_resolver import ClientWebsiteResolver
from app.utils.ssrf_guard import is_safe_url

def test_ssrf_prevention():
    # Loopback & private IPs
    safe, _ = is_safe_url("http://127.0.0.1:8000")
    assert safe is False
    safe, _ = is_safe_url("http://localhost:3000")
    assert safe is False
    safe, _ = is_safe_url("http://192.168.1.1/admin")
    assert safe is False
    safe, _ = is_safe_url("http://10.0.0.1/")
    assert safe is False
    safe, _ = is_safe_url("http://172.16.0.1/")
    assert safe is False
    safe, _ = is_safe_url("http://169.254.169.254/latest/meta-data/")
    assert safe is False
    
    # Safe public domains
    safe, _ = is_safe_url("https://mahavirbuilders.com/")
    assert safe is True
    safe, _ = is_safe_url("https://delightjet.com/")
    assert safe is True
    safe, _ = is_safe_url("https://thermalprojects.com/")
    assert safe is True

@pytest.mark.asyncio
async def test_priority_resolution_direct_url():
    resolver = ClientWebsiteResolver()
    
    res = await resolver.resolve_client_website(
        company_name="Mahavir Builders",
        portfolio_url="https://mahavirbuilders.com/",
        provider_domain="akham.in"
    )
    assert res["official_website"].startswith("https://mahavirbuilders.com")
    assert res["resolution_source"] in ("portfolio_card", "portfolio_outbound_link")
    assert res["confidence"] >= 0.85

@pytest.mark.asyncio
async def test_block_social_and_platform_domains():
    resolver = ClientWebsiteResolver()
    
    # When portfolio_url points to a social network
    res = await resolver.resolve_client_website(
        company_name="Some Agency Client",
        portfolio_url="https://facebook.com/someagencyclient",
        provider_domain="akham.in"
    )
    # Social URL must NOT be accepted as official website
    assert res["official_website"] != "https://facebook.com/someagencyclient"

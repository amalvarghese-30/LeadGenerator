import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from bson import ObjectId
import httpx
from app.enrichment.company_enrichment_service import CompanyEnrichmentService

@pytest.mark.asyncio
async def test_enrich_company_extracts_channels_without_person():
    service = CompanyEnrichmentService()
    
    mock_homepage_html = """
    <html>
      <head><title>Delight Jet | Private Charter</title></head>
      <body>
        <a href="https://delightjet.com/contact-us">Contact Us</a>
        <a href="https://linkedin.com/company/delightjet">LinkedIn</a>
        <a href="https://twitter.com/delightjet">Twitter</a>
        <p>Email: charter@delightjet.com</p>
      </body>
    </html>
    """
    
    mock_contact_html = """
    <html>
      <head><title>Contact Delight Jet</title></head>
      <body>
        <h1>Get in touch</h1>
        <p>Headquarters: Mumbai, India</p>
        <p>Call our 24/7 flight desk: +91 98200 12345</p>
        <p>Sales: sales@delightjet.com</p>
        <form action="/api/enquiry" method="POST">
          <input type="text" name="name" />
          <input type="email" name="email" />
          <button type="submit">Send Enquiry</button>
        </form>
      </body>
    </html>
    """

    mock_db = AsyncMock()
    fake_company_id = str(ObjectId())
    fake_company = {
        "_id": ObjectId(fake_company_id),
        "name": "Delight Jet",
        "website": "https://delightjet.com",
        "public_contact_channels": [],
        "enrichment_status": "pending",
    }
    
    mock_db.companies.find_one = AsyncMock(return_value=fake_company)
    mock_db.companies.update_one = AsyncMock()

    # Mock httpx responses
    async def mock_get(self, url, *args, **kwargs):
        resp = MagicMock(spec=httpx.Response)
        resp.status_code = 200
        resp.url = httpx.URL(str(url))
        if "contact" in str(url):
            resp.text = mock_contact_html
        else:
            resp.text = mock_homepage_html
        return resp

    with patch("httpx.AsyncClient.get", new=mock_get):
        res = await service.enrich_company(mock_db, fake_company_id)
        assert res is not None
        assert res["enrichment_status"] == "enriched"
        
        # Check channels extracted
        channels = res.get("public_contact_channels", [])
        channel_types = [c["type"] for c in channels]
        channel_values = [c["value"] for c in channels]
        
        assert "email" in channel_types
        assert any("charter@delightjet.com" in v or "sales@delightjet.com" in v for v in channel_values)
        assert "phone" in channel_types
        assert any("+919820012345" in v for v in channel_values)
        assert "contact_form" in channel_types
        
        # Social profiles
        socials = res.get("social_profiles", {})
        assert "linkedin" in socials or any(c["type"] == "social" and "linkedin" in c["value"] for c in channels)
        
        # Ensure company was updated in DB
        assert mock_db.companies.update_one.called

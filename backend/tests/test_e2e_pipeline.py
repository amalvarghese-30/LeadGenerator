import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from bson import ObjectId
from app.workers.job_processor import JobProcessor
from app.crm.reference_service import ReferenceService

@pytest.mark.asyncio
async def test_full_e2e_portfolio_discovery_pipeline():
    processor = JobProcessor()
    
    mock_portfolio_html = """
    <!DOCTYPE html>
    <html>
      <head><title>Agency Portfolio - Selected Client Works</title></head>
      <body>
        <nav><a href="/">Home</a><a href="/portfolio">Our Work</a></nav>
        <section class="portfolio-section">
          <h2>Featured Client Projects</h2>
          <div class="clients-grid">
            <div class="client-card">
              <h3>Mahavir Builders</h3>
              <span class="tag-pill">Real Estate</span>
              <p>Corporate real estate brand identity and portal.</p>
              <a class="visit-link" href="https://mahavirbuilders.com/">Visit Client Website</a>
            </div>
            <div class="client-card">
              <h3>Delight Jet</h3>
              <span class="tag-pill">Aviation</span>
              <p>Private luxury jet charter platform.</p>
              <a class="visit-link" href="https://delightjet.com/">Live Site</a>
            </div>
          </div>
        </section>
      </body>
    </html>
    """

    job_id = str(ObjectId())
    provider_id = str(ObjectId())
    
    mock_db = MagicMock()
    mock_job = {
        "_id": ObjectId(job_id),
        "provider_id": provider_id,
        "starting_url": "https://agency.com/portfolio",
        "status": "pending",
        "pages_crawled": 0,
        "references_found": 0,
        "companies_created": 0,
        "contacts_created": 0,
        "leads_created": 0,
    }
    mock_provider = {
        "_id": ObjectId(provider_id),
        "name": "Creative Agency",
        "website": "https://agency.com",
    }
    
    mock_db.crawl_jobs.find_one = AsyncMock(return_value=mock_job)
    mock_db.providers.find_one = AsyncMock(return_value=mock_provider)
    mock_db.crawl_jobs.update_one = AsyncMock()
    mock_db.crawl_pages.insert_one = AsyncMock(return_value=MagicMock(inserted_id=ObjectId()))
    mock_db.companies.find_one = AsyncMock(return_value=None)
    mock_db.companies.insert_one = AsyncMock(side_effect=lambda doc: MagicMock(inserted_id=ObjectId()))
    mock_db.companies.update_one = AsyncMock()
    mock_db.provider_client_references.find_one = AsyncMock(return_value=None)
    mock_db.provider_client_references.insert_one = AsyncMock(side_effect=lambda doc: MagicMock(inserted_id=ObjectId()))
    mock_db.research_reports.update_one = AsyncMock()
    mock_db.research_reports.replace_one = AsyncMock()
    mock_db.research_reports.find_one = AsyncMock(return_value=None)
    mock_db.job_events.insert_one = AsyncMock()

    # Mock discovery & crawling
    processor.discovery_manager.discover_all_urls = AsyncMock(return_value={
        "discovered_urls": [{"url": "https://agency.com/portfolio"}],
        "sources_breakdown": {}
    })
    
    processor.crawler_manager.crawl_urls = AsyncMock(return_value=[
        {
            "url": "https://agency.com/portfolio",
            "html": mock_portfolio_html,
            "raw_html": mock_portfolio_html,
            "main_text": "Featured Client Projects Mahavir Builders Real Estate Delight Jet Aviation",
            "text": "Featured Client Projects Mahavir Builders Real Estate Delight Jet Aviation",
            "status": "success",
            "status_code": 200,
            "page_title": "Agency Portfolio",
            "links": ["https://mahavirbuilders.com/", "https://delightjet.com/"]
        }
    ])

    with (
        patch.object(
            processor.company_enricher, "enrich_company"
        ) as mock_enrich,
        patch.object(
            ReferenceService,
            "create",
            new=AsyncMock(
                side_effect=lambda *args, **kwargs: {
                    "id": str(ObjectId()),
                    "created": True,
                }
            ),
        ) as mock_reference_create,
    ):
        mock_enrich.return_value = {
            "name": "Mahavir Builders",
            "enrichment_status": "enriched",
            "public_contact_channels": [{"type": "email", "value": "contact@mahavirbuilders.com", "scope": "company_general"}]
        }

        job_doc = {
            "_id": job_id,
            "provider_id": provider_id,
            "starting_url": "https://agency.com/portfolio",
            "max_pages": 5,
        }

        await processor.process_job(job_doc, mock_db)

        # Check that companies were inserted
        assert mock_db.companies.insert_one.called
        assert mock_reference_create.await_count >= 1
        assert mock_enrich.called

        # Verify job was marked completed
        update_calls = mock_db.crawl_jobs.update_one.call_args_list
        terminal_update = [c for c in update_calls if "$set" in c[0][1] and c[0][1]["$set"].get("status") in ("completed", "completed_with_warnings")]
        assert len(terminal_update) > 0

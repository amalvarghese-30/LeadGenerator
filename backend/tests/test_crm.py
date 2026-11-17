import pytest
from app.crm.provider_service import create_provider, get_provider, list_providers, delete_provider
from app.crm.company_service import create_company, get_company
from app.crm.contact_service import create_contact, get_contact, suppress_contact
from app.crm.lead_service import create_lead, get_lead, transition_stage, qualify_lead, delete_lead
from app.services.scoring_service import calculate_lead_score
from app.services.export_service import _sanitize_val

@pytest.mark.asyncio
async def test_provider_crud(test_db):
    data = {
        "name": "Test Agency Ltd",
        "website": "https://testagency.com",
        "category": "direct_competitor",
        "services": ["Knowledge Panel", "Entity SEO"],
    }
    created = await create_provider(test_db, data)
    assert created["name"] == "Test Agency Ltd"
    assert created["domain"] == "testagency.com"
    provider_id = created["id"]

    fetched = await get_provider(test_db, provider_id)
    assert fetched is not None
    assert fetched["name"] == "Test Agency Ltd"

    providers, total = await list_providers(test_db, limit=10)
    assert total >= 1

    deleted = await delete_provider(test_db, provider_id)
    assert deleted is True

@pytest.mark.asyncio
async def test_company_and_contact_dedup(test_db):
    comp = await create_company(test_db, {
        "name": "Alpha Technologies Inc",
        "website": "https://alphatech.com",
        "industry": "Software"
    })
    comp_id = comp["id"]

    # Deduplicated company creation
    comp_dup = await create_company(test_db, {
        "name": "Alpha Technologies Inc",
        "website": "https://alphatech.com",
    })
    assert comp_dup["id"] == comp_id

    # Contact creation
    contact, was_created = await create_contact(test_db, {
        "full_name": "Rohan Sharma",
        "designation": "Chief Executive Officer",
        "company_id": comp_id,
        "business_contacts": {"email": "rohan@alphatech.com"},
    })
    assert was_created is True
    assert contact["full_name"] == "Rohan Sharma"

    # Contact suppression (Do-Not-Contact)
    suppressed = await suppress_contact(test_db, contact["id"], "User Opt-Out")
    assert suppressed["is_suppressed"] is True
    assert suppressed["do_not_contact"] is True

@pytest.mark.asyncio
async def test_lead_scoring_and_pipeline(test_db):
    comp = await create_company(test_db, {"name": "Beta Labs", "industry": "AI"})
    contact, _ = await create_contact(test_db, {
        "full_name": "Dr. Sarah Jenkins",
        "designation": "Founder & Managing Director",
        "company_id": comp["id"],
        "business_contacts": {"email": "sarah@betalabs.com"},
    })

    lead = await create_lead(test_db, {
        "contact_id": contact["id"],
        "company_id": comp["id"],
        "lead_source": "test_provider",
    })
    assert lead["crm_stage"] == "discovered"

    # Stage transitions
    verified_lead = await transition_stage(test_db, lead["id"], "verified")
    assert verified_lead["crm_stage"] == "verified"

    qualified_lead = await qualify_lead(test_db, lead["id"], "qualified")
    assert qualified_lead["crm_stage"] == "qualified"

    # Scoring algorithm test
    score, breakdown = calculate_lead_score(qualified_lead, contact)
    assert score > 30
    assert "designation_relevance" in breakdown
    assert "business_presence" in breakdown

@pytest.mark.asyncio
async def test_lead_deletion_and_stage_contract(test_db):
    lead = await create_lead(test_db, {
        "contact_id": "c_mock_1",
        "company_id": "co_mock_1",
        "lead_source": "test",
    })
    lead_id = lead["id"]

    # Verify stage transition
    updated = await transition_stage(test_db, lead_id, "contacted", user_id="u_test", reason="First outreach email sent")
    assert updated["crm_stage"] == "contacted"

    # Verify deletion
    deleted = await delete_lead(test_db, lead_id, user_id="u_test")
    assert deleted is True

    # Ensure it no longer exists
    not_found = await get_lead(test_db, lead_id)
    assert not_found is None

def test_export_formula_injection_defense():
    assert _sanitize_val("=SUM(A1:A10)") == "'=SUM(A1:A10)"
    assert _sanitize_val("+cmd|' /C calc'!A0") == "'+cmd|' /C calc'!A0"
    assert _sanitize_val("-10+20") == "'-10+20"
    assert _sanitize_val("@SUM(1,2)") == "'@SUM(1,2)"
    assert _sanitize_val("Regular Professional Name") == "Regular Professional Name"

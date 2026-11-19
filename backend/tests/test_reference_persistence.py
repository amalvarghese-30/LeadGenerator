from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from bson import ObjectId

from app.crm.reference_service import create_reference
from app.schemas.reference import ReferenceCreate


@pytest.mark.asyncio
async def test_person_only_reference_does_not_create_unknown_company():
    record_id = ObjectId()
    stored = {
        "_id": record_id,
        "provider_id": "provider-1",
        "person_name": "Jane Doe",
        "company_name": None,
        "client_name": None,
        "source_url": "https://example.com/team/jane",
        "verification_status": "pending_review",
    }
    collection = SimpleNamespace(
        find_one=AsyncMock(side_effect=[None, None, stored]),
        update_one=AsyncMock(
            return_value=SimpleNamespace(upserted_id=record_id)
        ),
        insert_one=AsyncMock(),
    )
    db = SimpleNamespace(provider_client_references=collection)

    result = await create_reference(
        db,
        {
            "provider_id": "provider-1",
            "person_name": "Jane Doe",
            "source_url": "https://example.com/team/jane",
            "evidence_quote": "Jane Doe is featured on this page.",
            "relationship_type": "published_customer_profile",
        },
    )

    assert result["person_name"] == "Jane Doe"
    assert result["company_name"] is None
    assert result["client_name"] is None
    assert result["created"] is True
    collection.update_one.assert_awaited_once()
    collection.insert_one.assert_not_awaited()


@pytest.mark.asyncio
async def test_repeated_reference_reuses_existing_record():
    existing_id = ObjectId()
    existing = {
        "_id": existing_id,
        "provider_id": "provider-1",
        "person_name": "Jane Doe",
        "company_name": "Acme Technologies",
        "source_url": "https://example.com/clients",
        "verification_status": "verified",
        "confidence": 0.8,
    }

    collection = SimpleNamespace(
        find_one=AsyncMock(return_value=existing),
        update_one=AsyncMock(),
        insert_one=AsyncMock(),
    )
    db = SimpleNamespace(provider_client_references=collection)

    result = await create_reference(
        db,
        {
            "provider_id": "provider-1",
            "person_name": "Jane Doe",
            "company_name": "Acme Technologies",
            "source_url": "https://example.com/clients",
            "evidence_quote": "Jane Doe, CEO of Acme Technologies.",
            "relationship_type": "client_portfolio_reference",
        },
    )

    assert result["created"] is False
    assert result["id"] == str(existing_id)
    assert result["verification_status"] == "verified"
    collection.insert_one.assert_not_awaited()
    collection.update_one.assert_awaited_once()


@pytest.mark.asyncio
async def test_different_source_pages_remain_separate_references():
    first_id = ObjectId()
    second_id = ObjectId()

    first_stored = {
        "_id": first_id,
        "provider_id": "provider-1",
        "company_name": "Acme Technologies",
        "client_name": "Acme Technologies",
        "source_url": "https://example.com/clients",
    }
    second_stored = {
        "_id": second_id,
        "provider_id": "provider-1",
        "company_name": "Acme Technologies",
        "client_name": "Acme Technologies",
        "source_url": "https://example.com/case-study",
    }

    collection = SimpleNamespace(
        find_one=AsyncMock(
            side_effect=[
                None, None, first_stored,
                None, None, second_stored,
            ]
        ),
        update_one=AsyncMock(
            side_effect=[
                SimpleNamespace(upserted_id=first_id),
                SimpleNamespace(upserted_id=second_id),
            ]
        ),
        insert_one=AsyncMock(),
    )
    db = SimpleNamespace(provider_client_references=collection)

    base = {
        "provider_id": "provider-1",
        "company_name": "Acme Technologies",
        "relationship_type": "client_portfolio_reference",
    }

    first = await create_reference(
        db, {**base, "source_url": "https://example.com/clients"}
    )
    second = await create_reference(
        db, {**base, "source_url": "https://example.com/case-study"}
    )

    assert first["id"] != second["id"]
    assert first["created"] is True
    assert second["created"] is True
    assert collection.update_one.await_count == 2
    collection.insert_one.assert_not_awaited()


def test_reference_api_schema_accepts_person_details():
    reference = ReferenceCreate(
        provider_id="provider-1",
        person_name="Jane Doe",
        designation="Founder",
    )

    assert reference.person_name == "Jane Doe"
    assert reference.designation == "Founder"

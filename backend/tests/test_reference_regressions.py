from types import SimpleNamespace

import pytest
from bson import ObjectId

from app.crm.reference_service import create_reference


class FakeReferenceCollection:
    async def insert_one(self, document):
        self.document = document
        self.inserted_id = ObjectId()
        return SimpleNamespace(inserted_id=self.inserted_id)


@pytest.mark.asyncio
async def test_zero_confidence_is_preserved_and_id_is_returned():
    collection = FakeReferenceCollection()
    db = SimpleNamespace(provider_client_references=collection)

    result = await create_reference(
        db,
        {
            "provider_id": "regression-test-provider",
            "person_name": "Regression Test Person",
            "confidence": 0,
        },
    )

    assert collection.document["confidence"] == 0.0
    assert collection.document["confidence_score"] == 0.0
    assert result["id"] == str(collection.inserted_id)
    assert result["created"] is True

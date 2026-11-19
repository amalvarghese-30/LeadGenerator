import json

from app.ai.output_validator import OutputValidator


def test_valid_entity_is_preserved():
    validator = OutputValidator()

    raw = json.dumps({
        "entities": [{
            "person_name": "Robert Mathew",
            "designation": "Director",
            "company_name": "Bright Solutions",
            "relationship_type": "client_testimonial",
            "confidence": 0.9,
            "verification_status": "verified",
        }]
    })

    result = validator.validate_extraction_output(
        raw, "https://example.com/testimonial"
    )

    assert result is not None
    assert result[0]["person_name"] == "Robert Mathew"
    assert result[0]["company_name"] == "Bright Solutions"
    assert result[0]["verification_status"] == "pending"


def test_null_like_values_are_normalized():
    validator = OutputValidator()

    raw = json.dumps({
        "entities": [{
            "person_name": "null",
            "company_name": "Bright Solutions",
            "designation": "None",
            "industry": "",
            "relationship_type": "client_portfolio_reference",
            "confidence": 0.8,
        }]
    })

    result = validator.validate_extraction_output(raw, "https://example.com")

    assert result is not None
    assert result[0]["person_name"] is None
    assert result[0]["designation"] is None
    assert result[0]["industry"] is None


def test_malformed_keys_are_not_interpreted_as_person_names():
    validator = OutputValidator()

    raw = json.dumps({
        "entities": [{
            "": "null",
            ":": "Robert Mathew",
            "company_name": "Bright Solutions",
            "relationship_type": "client_testimonial",
            "confidence": 0.8,
        }]
    })

    result = validator.validate_extraction_output(raw, "https://example.com")

    assert result is not None
    assert result[0]["company_name"] == "Bright Solutions"
    assert result[0]["person_name"] is None
    assert "" not in result[0]
    assert ":" not in result[0]


def test_malformed_entity_without_valid_identity_is_rejected():
    validator = OutputValidator()

    raw = json.dumps({
        "entities": [{
            "": "null",
            ":": "Robert Mathew",
            "confidence": 0.9,
        }]
    })

    assert validator.validate_extraction_output(
        raw, "https://example.com"
    ) is None


def test_generated_contact_details_are_removed():
    validator = OutputValidator()

    raw = json.dumps({
        "entities": [{
            "person_name": "Alex Mercer",
            "company_name": "Nexus Corp",
            "email": "guessed@nexus.com",
            "phone": "1234567890",
            "relationship_type": "client_testimonial",
            "confidence": 0.9,
        }]
    })

    result = validator.validate_extraction_output(raw, "https://example.com")

    assert result is not None
    assert "email" not in result[0]
    assert "phone" not in result[0]


def test_confidence_is_bounded():
    validator = OutputValidator()

    raw = json.dumps({
        "entities": [{
            "company_name": "Example Technologies",
            "confidence": 5,
        }]
    })

    result = validator.validate_extraction_output(raw, "https://example.com")

    assert result[0]["confidence"] == 1.0

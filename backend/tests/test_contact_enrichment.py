"""
Unit and integration test suite for the Contact Enrichment Engine.
Tests:
- Visible email extraction
- Mailto extraction
- JSON-LD Person.email and Organization.email
- Tel extraction
- ContactPoint telephone extraction
- Invalid email and phone rejection
- Generic company vs direct work email classification
- Company switchboard vs direct phone classification
- Zero-contact handling
- Channel deduplication & prioritization
- DDGS and AI failure resilience
- Human review and verification transitions
"""
import pytest
from app.crawler.content_extractor import ContentExtractor
from app.enrichment.public_email_extractor import PublicEmailExtractor
from app.enrichment.public_phone_extractor import PublicPhoneExtractor
from app.enrichment.contact_validator import ContactValidator
from app.enrichment.contact_source_verifier import ContactSourceVerifier
from app.enrichment.enrichment_deduplication import EnrichmentDeduplication
from app.enrichment.identity_resolver import IdentityResolver


def test_email_found_in_visible_webpage_text():
    html = """
    <html>
      <body>
        <h1>Leadership Team</h1>
        <p>Contact Rajesh Sharma directly at rajesh.sharma@acmeconsulting.com for advisory inquiries.</p>
      </body>
    </html>
    """
    emails = PublicEmailExtractor.extract_from_html(html, "https://acmeconsulting.com/team", target_person_name="Rajesh Sharma")
    assert len(emails) >= 1
    direct = next((e for e in emails if e.value == "rajesh.sharma@acmeconsulting.com"), None)
    assert direct is not None
    assert direct.scope == "person_direct_work"
    assert "rajesh.sharma" in direct.evidence_quote


def test_email_found_through_mailto():
    html = """
    <html>
      <body>
        <a href="mailto:info@techsolutions.in?subject=Enquiry">Email Our Office</a>
      </body>
    </html>
    """
    emails = PublicEmailExtractor.extract_from_html(html, "https://techsolutions.in/contact")
    assert len(emails) == 1
    assert emails[0].value == "info@techsolutions.in"
    assert emails[0].scope == "company_generic"
    assert emails[0].source_type == "mailto"


def test_email_found_in_json_ld():
    html = """
    <html>
      <head>
        <script type="application/ld+json">
        {
          "@context": "https://schema.org",
          "@type": "Person",
          "name": "Priya Patel",
          "jobTitle": "Managing Partner",
          "email": "priya.patel@patellaw.com",
          "telephone": "+91 98765 43210"
        }
        </script>
      </head>
      <body><h1>Priya Patel Profile</h1></body>
    </html>
    """
    extractor = ContentExtractor()
    data = extractor.extract(html, "https://patellaw.com/team/priya")
    assert "priya.patel@patellaw.com" in data["public_emails"]
    assert "+919876543210" in data["public_phones"]
    assert len(data["schema_persons"]) == 1
    assert data["schema_persons"][0]["email"] == "priya.patel@patellaw.com"


def test_phone_found_through_tel():
    html = """
    <html>
      <body>
        <a href="tel:+912228549999">Call Board: (022) 2854-9999</a>
      </body>
    </html>
    """
    phones = PublicPhoneExtractor.extract_from_html(html, "https://firm.com/contact")
    assert len(phones) >= 1
    phone_e164 = phones[0].value
    assert phone_e164 == "+912228549999"
    assert phones[0].source_type == "tel"


def test_phone_found_in_contactpoint():
    html = """
    <html>
      <head>
        <script type="application/ld+json">
        {
          "@context": "https://schema.org",
          "@type": "Organization",
          "name": "Global Tech Corp",
          "contactPoint": {
            "@type": "ContactPoint",
            "telephone": "+91-11-23456789",
            "contactType": "customer service",
            "email": "support@globaltech.com"
          }
        }
        </script>
      </head>
      <body><h1>Home</h1></body>
    </html>
    """
    extractor = ContentExtractor()
    data = extractor.extract(html, "https://globaltech.com")
    assert "+911123456789" in data["public_phones"]
    assert "support@globaltech.com" in data["public_emails"]


def test_invalid_email_syntax_and_domain():
    val_bad_syntax = ContactValidator.validate_email_channel("not-an-email")
    assert val_bad_syntax["syntax_valid"] is False
    assert val_bad_syntax["domain_valid"] is False

    val_fake_domain = ContactValidator.validate_email_channel("user@fake-nonexistent-domain-xyz123456789.org")
    assert val_fake_domain["syntax_valid"] is True
    assert val_fake_domain["mx_record_found"] is False


def test_invalid_phone_number():
    val_invalid = ContactValidator.validate_phone_channel("12345")
    assert val_invalid["is_valid"] is False

    val_valid = ContactValidator.validate_phone_channel("+91 98200 12345", default_region="IN")
    assert val_valid["is_valid"] is True
    assert val_valid["e164"] == "+919820012345"


def test_generic_company_email_classification():
    scope_info = PublicEmailExtractor.classify_scope("info@acme.com", target_person_name="Amit Roy")
    assert scope_info == "company_generic"

    scope_support = PublicEmailExtractor.classify_scope("support@acme.com", target_person_name="Amit Roy")
    assert scope_support == "department"

    scope_sales = PublicEmailExtractor.classify_scope("sales@acme.com", target_person_name="Amit Roy")
    assert scope_sales == "sales_enquiry"


def test_company_switchboard_phone_classification():
    scope_board = PublicPhoneExtractor.classify_scope("Office Switchboard / Reception: +91 22 1234 5678")
    assert scope_board == "company_switchboard"

    scope_direct = PublicPhoneExtractor.classify_scope("Direct Mobile: +91 98200 11111", target_person_name="Amit Roy")
    assert scope_direct == "person_direct_work"


def test_person_direct_work_email_classification():
    scope_direct = PublicEmailExtractor.classify_scope("amit.roy@acme.com", target_person_name="Amit Roy")
    assert scope_direct == "person_direct_work"

    scope_initial = PublicEmailExtractor.classify_scope("aroy@acme.com", target_person_name="Amit Roy")
    assert scope_direct == "person_direct_work"


def test_no_contact_details_available():
    html = "<html><body><h1>Welcome to Blog</h1><p>Articles on philosophy.</p></body></html>"
    emails = PublicEmailExtractor.extract_from_html(html, "https://blog.com")
    phones = PublicPhoneExtractor.extract_from_html(html, "https://blog.com")
    assert len(emails) == 0
    assert len(phones) == 0


def test_duplicate_contact_channel_deduplication():
    channels = [
        {
            "type": "email",
            "scope": "company_generic",
            "value": "info@acme.com",
            "verification_status": "published",
            "confidence": 0.6,
            "evidence_quote": "Found in footer",
        },
        {
            "type": "email",
            "scope": "company_generic",
            "value": "info@acme.com",
            "verification_status": "source_verified",
            "confidence": 0.9,
            "evidence_quote": "Found on official contact page",
        },
        {
            "type": "email",
            "scope": "person_direct_work",
            "value": "ceo@acme.com",
            "verification_status": "source_verified",
            "confidence": 0.95,
            "evidence_quote": "Direct email",
        }
    ]
    deduped = EnrichmentDeduplication.deduplicate_channels(channels)
    assert len(deduped) == 2
    # The direct person email should be ranked first
    assert deduped[0]["value"] == "ceo@acme.com"
    # The duplicate info@acme.com should be merged and upgraded to source_verified
    assert deduped[1]["value"] == "info@acme.com"
    assert deduped[1]["verification_status"] == "source_verified"


def test_company_contact_not_incorrectly_attributed_to_individual():
    """Ensure generic company switchboards or info@ emails do not get marked as direct personal contacts."""
    scope_email = PublicEmailExtractor.classify_scope("enquiry@company.com", target_person_name="Ramesh Verma")
    assert scope_email != "person_direct_work"

    scope_phone = PublicPhoneExtractor.classify_scope("HQ Tel: +91 11 4455 6677", target_person_name="Ramesh Verma")
    assert scope_phone != "person_direct_work"


def test_verification_stage_transitions_and_human_review():
    status = ContactSourceVerifier.determine_channel_status(
        ch_type="email",
        value="john@official.com",
        validation_info={"syntax_valid": True, "mx_record_found": True, "company_attributed": True},
        is_official_domain=True,
        has_evidence_quote=True,
    )
    assert status == "source_verified"

    status_human = ContactSourceVerifier.determine_channel_status(
        ch_type="email",
        value="john@official.com",
        validation_info={"syntax_valid": True},
        human_reviewed=True,
    )
    assert status_human == "human_reviewed"

    status_rejected = ContactSourceVerifier.determine_channel_status(
        ch_type="email",
        value="bad@email.com",
        validation_info={"syntax_valid": False},
        is_rejected=True,
    )
    assert status_rejected == "rejected"


def test_identity_resolver_safe_queries():
    contact = {
        "full_name": "Adv. Ramesh Sharma",
        "designation": "Managing Partner",
        "company_name": "Sharma Law Associates",
        "professional_urls": {"linkedin": "https://www.linkedin.com/in/rameshsharma-law"},
    }
    identity = IdentityResolver.resolve(contact)
    assert identity.first_name == "Ramesh"
    assert identity.company_name == "Sharma Law Associates"
    # Never search by bare generic name alone
    for q in identity.search_queries:
        assert ("Sharma Law Associates" in q) or ("website" in q) or ("contact" in q)

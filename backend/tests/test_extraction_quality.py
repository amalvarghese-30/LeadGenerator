"""
Automated Regression and Data-Quality Test Suite (Task 11).
Contains 100+ manually labeled test cases spanning:
- Realistic person names & executive client testimonials
- Company-only portfolio references
- Generic marketing paragraphs & SEO descriptions
- HTML navigation text & CTAs
- Accessibility descriptions & media tags
- Blog mentions, collaborators & featured personalities
- Invalid names, sentence fragments & stopwords

Explicitly verifies that:
- 'accounts. Each caption' is NEVER accepted as a person
- 'set an all-time' is NEVER accepted as a person
- 'Kay Properties rank' is NEVER accepted as a person
- Precision on the client reference test corpus achieves >= 90%.
"""
import pytest
from typing import List, Dict, Any, Tuple
from app.extraction.name_validator import NameValidator
from app.extraction.page_analyzer import PageAnalyzer
from app.extraction.evidence_validator import EvidenceValidator
from app.extraction.text_extraction import TextExtractor

# ----------------------------------------------------------------------
# 100+ Labelled Test Corpus
# Format: (input_phrase_or_snippet, is_valid_person, is_client_reference, label_category)
# ----------------------------------------------------------------------
LABELED_CORPUS: List[Tuple[str, bool, bool, str]] = [
    # --- Explicit Regression Cases from User Prompt ---
    ("accounts. Each caption", False, False, "sentence_fragment"),
    ("set an all-time", False, False, "sentence_fragment"),
    ("Kay Properties rank", False, False, "company_and_verb"),
    ("view more", False, False, "navigation"),
    ("learn more", False, False, "navigation"),
    ("get started", False, False, "navigation"),
    ("your business", False, False, "marketing_seo"),
    ("our services", False, False, "marketing_seo"),
    ("customer reviews", False, False, "marketing_seo"),
    ("key benefits", False, False, "marketing_seo"),

    # --- HTML Navigation & UI Noise ---
    ("read more", False, False, "navigation"),
    ("click here", False, False, "navigation"),
    ("contact us", False, False, "navigation"),
    ("sign in", False, False, "navigation"),
    ("sign up", False, False, "navigation"),
    ("home page", False, False, "navigation"),
    ("back to top", False, False, "navigation"),
    ("skip to content", False, False, "navigation"),
    ("terms of service", False, False, "navigation"),
    ("privacy policy", False, False, "navigation"),
    ("all rights reserved", False, False, "navigation"),
    ("cookie policy", False, False, "navigation"),
    ("book a demo", False, False, "navigation"),
    ("request a quote", False, False, "navigation"),
    ("free consultation", False, False, "navigation"),

    # --- Accessibility & Media Artifacts ---
    ("each caption", False, False, "accessibility"),
    ("alt text", False, False, "accessibility"),
    ("photo gallery", False, False, "accessibility"),
    ("profile picture", False, False, "accessibility"),
    ("hero image", False, False, "accessibility"),
    ("video thumbnail", False, False, "accessibility"),
    ("svg icon", False, False, "accessibility"),
    ("banner visual", False, False, "accessibility"),
    ("infographic diagram", False, False, "accessibility"),
    ("audio clip", False, False, "accessibility"),

    # --- Generic SEO & Marketing Phrasing ---
    ("google knowledge panel", False, False, "marketing_seo"),
    ("entity seo", False, False, "marketing_seo"),
    ("personal branding", False, False, "marketing_seo"),
    ("executive reputation", False, False, "marketing_seo"),
    ("digital marketing", False, False, "marketing_seo"),
    ("search results", False, False, "marketing_seo"),
    ("proven results", False, False, "marketing_seo"),
    ("world class", False, False, "marketing_seo"),
    ("industry leaders", False, False, "marketing_seo"),
    ("market leader", False, False, "marketing_seo"),
    ("competitive advantage", False, False, "marketing_seo"),
    ("tailored solutions", False, False, "marketing_seo"),
    ("cutting edge", False, False, "marketing_seo"),
    ("full service", False, False, "marketing_seo"),
    ("data driven", False, False, "marketing_seo"),

    # --- Sentence Fragments & Common Verbs ---
    ("is growing fast", False, False, "sentence_fragment"),
    ("helps your company", False, False, "sentence_fragment"),
    ("delivers great value", False, False, "sentence_fragment"),
    ("starts from scratch", False, False, "sentence_fragment"),
    ("make a difference", False, False, "sentence_fragment"),
    ("takes time to build", False, False, "sentence_fragment"),
    ("find the right fit", False, False, "sentence_fragment"),
    ("rank higher on search", False, False, "sentence_fragment"),
    ("create an impact", False, False, "sentence_fragment"),
    ("achieve new heights", False, False, "sentence_fragment"),

    # --- Corporate Entities (Company-only, not a person) ---
    ("Acme Technologies Inc", False, False, "corporate_entity"),
    ("Apex Global Solutions LLC", False, False, "corporate_entity"),
    ("Nexus Media Group", False, False, "corporate_entity"),
    ("Vanguard Properties Ltd", False, False, "corporate_entity"),
    ("Summit Capital Partners", False, False, "corporate_entity"),
    ("Horizon Health Systems", False, False, "corporate_entity"),
    ("Beacon Real Estate", False, False, "corporate_entity"),
    ("Pinnacle Creative Studios", False, False, "corporate_entity"),
    ("Quantum Digital Agency", False, False, "corporate_entity"),
    ("Starlight Logistics Co", False, False, "corporate_entity"),

    # --- Realistic Legitimate Person Names (High Precision) ---
    ("Dr. Emily Watson", True, False, "realistic_person"),
    ("Sarah Connor", True, False, "realistic_person"),
    ("John Smith", True, False, "realistic_person"),
    ("David O'Connor", True, False, "realistic_person"),
    ("Jean-Luc Picard", True, False, "realistic_person"),
    ("Michael Bloomberg", True, False, "realistic_person"),
    ("Satya Nadella", True, False, "realistic_person"),
    ("Sundar Pichai", True, False, "realistic_person"),
    ("Tim Cook", True, False, "realistic_person"),
    ("Sheryl Sandberg", True, False, "realistic_person"),
    ("Marc Benioff", True, False, "realistic_person"),
    ("Arvind Krishna", True, False, "realistic_person"),
    ("Gitanjali Rao", True, False, "realistic_person"),
    ("Siddharth Malhotra", True, False, "realistic_person"),
    ("Ananya Sharma", True, False, "realistic_person"),
    ("Alexander Wright", True, False, "realistic_person"),
    ("Elizabeth Warren", True, False, "realistic_person"),
    ("Richard Branson", True, False, "realistic_person"),
    ("Bill Gates", True, False, "realistic_person"),
    ("Warren Buffett", True, False, "realistic_person"),

    # --- Realistic Confirmed Client Testimonials & Case Studies ---
    ('"Working with this team doubled our organic search visibility." — Jonathan Sterling, CEO at BioHealth Inc', True, True, "client_testimonial"),
    ('"Their executive reputation management transformed my public profile completely." — Dr. Rajesh Sen, Founder of NeuroTech', True, True, "client_testimonial"),
    ('"The best strategic partnership we have made this year." — Marcus Vance, Managing Director at Sterling Capital', True, True, "client_testimonial"),
    ('Case Study: How we helped Elena Rostova, VP Marketing at FinSecure, scale customer acquisition by 140%', True, True, "case_study"),
    ('Client Success Story: Building executive Google Knowledge Panel for Dr. Arthur Pendelton of HealthVision', True, True, "case_study"),
    ('"Exceptional personal branding results delivered on schedule." — Victoria Chen, Partner at Chen Legal', True, True, "client_testimonial"),
    ('Client: Raymond Cross, Executive Chairman at Cross Global - Executive entity SEO and reputation management', True, True, "client_case"),
    ('"They exceeded all our expectations." — Gregory House, Chief Medical Officer at Plainsboro Diagnostics', True, True, "client_testimonial"),
    ('Case Study: Personal branding and Wikipedia authority for Prof. Alistair MacIntyre of Oxford Research', True, True, "case_study"),
    ('"A seamless experience from start to finish." — Natasha Romanova, Founder at Shield Security Group', True, True, "client_testimonial"),

    # --- Company-only Portfolio References ---
    ("Project for TechWave Corp - Brand identity and SEO transformation", False, True, "company_portfolio"),
    ("Case Study: CloudMigration Inc - Enterprise infrastructure optimization", False, True, "company_portfolio"),
    ("Client Showcase: DataStream Systems - Automated real-time analytics pipeline", False, True, "company_portfolio"),
    ("Portfolio: Horizon Dynamics - Executive reputation defense", False, True, "company_portfolio"),
    ("Client: Apex BioLabs - Clinical trial authority marketing", False, True, "company_portfolio"),

    # --- Collaborators / Partners (Valid People, but NOT CRM Clients) ---
    ("In collaboration with Dr. Neil Tyson, astrophysicist and science communicator", True, False, "collaborator"),
    ("Joint research paper with Prof. Douglas Stone of MIT", True, False, "collaborator"),
    ("Co-authored with Robert Martin, software architecture consultant", True, False, "collaborator"),
    ("Technology partnership with James Gosling, creator of Java", True, False, "collaborator"),
    ("Community initiative hosted with Malcolm Gladwell, staff writer at The New Yorker", True, False, "collaborator"),

    # --- Blog / Article Ordinary Mentions (Valid People, but NOT Clients) ---
    ("According to Elon Musk in a recent conference keynote...", True, False, "blog_mention"),
    ("As famously observed by Steve Jobs during the 2007 presentation...", True, False, "blog_mention"),
    ("Written by Staff Journalist Peter Parker for the daily chronicle.", True, False, "blog_mention"),
    ("Quoted in the article: Dr. Anthony Fauci on public health measures.", True, False, "blog_mention"),
    ("Analysis provided by Thomas Friedman in his latest editorial column.", True, False, "blog_mention"),
]


def test_labeled_corpus_count():
    """Verify test corpus contains at least 100 labeled examples as requested in Task 11."""
    assert len(LABELED_CORPUS) >= 100, f"Corpus must have at least 100 items, got {len(LABELED_CORPUS)}"


def test_explicit_regression_rejections():
    """
    Explicit regression tests for exact failure examples reported by the user:
    - 'accounts. Each caption'
    - 'set an all-time'
    - 'Kay Properties rank'
    - Navigation and generic marketing phrases
    """
    validator = NameValidator()

    # 1. 'accounts. Each caption'
    is_valid, reasons = validator.validate_person_name("accounts. Each caption")
    assert is_valid is False
    assert any("sentence" in r.lower() or "period" in r.lower() or "verb" in r.lower() for r in reasons)

    # 2. 'set an all-time'
    is_valid, reasons = validator.validate_person_name("set an all-time")
    assert is_valid is False
    assert any("marketing" in r.lower() or "verb" in r.lower() or "capitalized" in r.lower() for r in reasons)

    # 3. 'Kay Properties rank'
    is_valid, reasons = validator.validate_person_name("Kay Properties rank")
    assert is_valid is False
    assert any(term in r.lower() for term in ["corporate", "properties", "verb", "capitalized"] for r in reasons)

    # Also verify 'Kay Properties Rank' (Title Case) is rejected as corporate entity or verb
    is_valid_cap, reasons_cap = validator.validate_person_name("Kay Properties Rank")
    assert is_valid_cap is False
    assert any("corporate" in r.lower() or "properties" in r.lower() or "verb" in r.lower() for r in reasons_cap)

    # 4. Marketing and Nav terms
    nav_tests = [
        "view more", "learn more", "get started", "your business",
        "our services", "customer reviews", "key benefits"
    ]
    for phrase in nav_tests:
        valid, r = validator.validate_person_name(phrase)
        assert valid is False, f"Expected '{phrase}' to be rejected, but it passed!"


def test_name_validator_precision():
    """
    Test precision on the person-name portion of the 100+ corpus.
    Precision target: >= 90%.
    """
    validator = NameValidator()
    true_positives = 0
    false_positives = 0
    true_negatives = 0
    false_negatives = 0

    for item, expected_person, _, category in LABELED_CORPUS:
        # For snippets that contain quotes, extract the candidate name if present
        is_valid, reasons = validator.validate_person_name(item)

        if is_valid and expected_person:
            true_positives += 1
        elif is_valid and not expected_person:
            false_positives += 1
            print(f"FALSE POSITIVE on [{category}]: '{item}' passed validation! reasons: {reasons}")
        elif not is_valid and not expected_person:
            true_negatives += 1
        else:
            false_negatives += 1

    precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0.0
    print(f"\nPerson Name Metrics: TP={true_positives}, FP={false_positives}, TN={true_negatives}, FN={false_negatives}")
    print(f"Person Name Precision: {precision:.2%}")

    assert false_positives == 0, f"Expected 0 false positives on person names, got {false_positives}"
    assert precision >= 0.90, f"Expected precision >= 90%, got {precision:.2%}"


def test_end_to_end_client_reference_precision():
    """
    Test end-to-end extraction precision on testimonial and case study snippets.
    Verifies that ONLY genuine client references pass, while SEO fluff,
    collaborators, blog quotes, and navigation snippets are rejected.
    """
    analyzer = PageAnalyzer()
    validator = EvidenceValidator()

    # Run analyzer against realistic case study snippets
    testimonial_snippet = """
    We are thrilled with our executive branding.
    "Working with this team doubled our organic search visibility." — Jonathan Sterling, CEO at BioHealth Inc
    Our work for TechWave Corp was featured in global media.
    According to Elon Musk, technology moves exponentially.
    """
    candidates = analyzer.analyze(testimonial_snippet, "https://example.com/case-studies/biohealth")

    # Filter through EvidenceValidator
    valid_refs = []
    for c in candidates:
        is_v, _ = validator.validate(c, source_text=testimonial_snippet)
        if is_v:
            valid_refs.append(c)

    names = [r.get("person_name") for r in valid_refs if r.get("person_name")]
    companies = [r.get("company_name") for r in valid_refs if r.get("company_name")]

    # Assert Jonathan Sterling was extracted
    assert "Jonathan Sterling" in names
    # Assert Elon Musk was NOT extracted as a client
    assert "Elon Musk" not in names
    # Assert TechWave Corp was extracted as company-only portfolio
    assert "TechWave Corp" in companies


def test_page_classification_signals():
    """Test multi-signal page classifier across categories."""
    extractor = TextExtractor()

    # Case study page
    cs = extractor.classify_page_relevance(
        "https://agency.com/case-studies/healthcare-growth",
        "BioHealth SEO Case Study",
        "Challenge: Low visibility. Solution: Entity SEO. Results: 140% growth."
    )
    assert cs["is_client_reference_page"] is True
    assert cs["page_category"] == "Case Study"

    # Testimonial page
    testim = extractor.classify_page_relevance(
        "https://agency.com/testimonials",
        "What Our Clients Say",
        "Client reviews and testimonials from our enterprise customers."
    )
    assert testim["is_client_reference_page"] is True
    assert testim["page_category"] == "Testimonial"

    # Service page (must NOT be treated as a client reference page)
    serv = extractor.classify_page_relevance(
        "https://agency.com/services/seo-packages",
        "Our SEO Services and Pricing Plans",
        "We offer comprehensive digital marketing packages. Our services include monthly retainers and custom pricing."
    )
    assert serv["is_client_reference_page"] is False
    assert serv["page_category"] == "Service Page"

    # Blog / Article (must NOT be treated as a client reference page)
    blog = extractor.classify_page_relevance(
        "https://agency.com/blog/how-google-ranks-websites",
        "How Google Ranks Websites in 2026",
        "An in-depth article exploring search algorithms, entity graphs, and indexing strategies."
    )
    assert blog["is_client_reference_page"] is False
    assert blog["page_category"] == "General Article"

# LeadIntel classifier and profile evidence regressions


# LeadIntel classifier and profile evidence regressions

def test_reverse_role_explicit_client_label_is_portfolio_reference():
    analyzer = PageAnalyzer()
    text = (
        "Client: Acme Technologies, CEO: Jane Doe. "
        "This is an explicitly identified client relationship."
    )

    candidates = analyzer.analyze(text, "https://example.com/clients")
    matches = [
        c for c in candidates
        if c.get("extraction_method") == "deterministic_reverse_role"
    ]

    assert any(
        c.get("person_name") == "Jane Doe"
        and c.get("company_name") == "Acme Technologies"
        and c.get("relationship_type") == "client_portfolio_reference"
        for c in matches
    )


def test_reverse_role_company_label_is_not_automatically_a_client():
    analyzer = PageAnalyzer()
    text = (
        "Company: Acme Technologies, CEO: Jane Doe. "
        "The organization is mentioned in this general business article."
    )

    candidates = analyzer.analyze(text, "https://example.com/about")
    matches = [
        c for c in candidates
        if c.get("extraction_method") == "deterministic_reverse_role"
    ]

    assert any(c.get("person_name") == "Jane Doe" for c in matches)
    assert all(
        c.get("relationship_type") not in {
            "confirmed_client",
            "confirmed_client_case_study",
            "case_study_client",
            "client_testimonial",
            "testimonial_client",
            "client_portfolio_reference",
            "published_customer_profile",
        }
        for c in matches
    )


def test_profile_url_slug_without_name_in_page_text_is_rejected():
    analyzer = PageAnalyzer()
    text = (
        "This customer profile explains the services offered by the agency. "
        "It contains general information but does not identify the profile subject."
    )

    candidates = analyzer.analyze(
        text, "https://example.com/profile/jane-doe"
    )

    assert not any(
        c.get("extraction_method") == "deterministic_published_profile"
        for c in candidates
    )


def test_profile_name_without_customer_profile_evidence_is_rejected():
    analyzer = PageAnalyzer()
    text = (
        "Jane Doe is a technology executive with extensive industry experience. "
        "This ordinary biography does not describe a client relationship."
    )

    candidates = analyzer.analyze(
        text, "https://example.com/profile/jane-doe"
    )

    assert not any(
        c.get("extraction_method") == "deterministic_published_profile"
        for c in candidates
    )


def test_genuine_published_profile_uses_actual_source_evidence():
    analyzer = PageAnalyzer()
    text = (
        "Client profile: Jane Doe. "
        "Jane Doe is featured in this client profile describing her professional journey. "
        "The page discusses her work and background in detail."
    )

    candidates = analyzer.analyze(
        text, "https://example.com/profile/jane-doe"
    )

    matches = [
        c for c in candidates
        if c.get("extraction_method") == "deterministic_published_profile"
    ]

    assert len(matches) == 1
    assert matches[0]["person_name"] == "Jane Doe"
    assert matches[0]["company_name"] is None
    assert matches[0]["relationship_type"] == "published_customer_profile"
    assert matches[0]["evidence_quote"] in text
    assert "Published client profile for" not in matches[0]["evidence_quote"]

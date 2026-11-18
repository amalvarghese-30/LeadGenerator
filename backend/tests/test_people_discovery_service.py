import pytest
from app.discovery.people_discovery_service import PeopleDiscoveryService

def test_people_discovery_from_json_ld():
    service = PeopleDiscoveryService()
    html = """
    <html>
      <head>
        <script type="application/ld+json">
        {
          "@context": "https://schema.org",
          "@type": "Organization",
          "name": "Acme Global",
          "founder": {
            "@type": "Person",
            "name": "Jane Smith",
            "jobTitle": "Founder & CEO",
            "sameAs": "https://www.linkedin.com/in/janesmith-ceo"
          }
        }
        </script>
      </head>
      <body>
        <h1>Welcome to Acme Global</h1>
      </body>
    </html>
    """
    people = service.discover_from_html(html, "https://acmeglobal.com", "Acme Global")
    assert len(people) >= 1
    p = people[0]
    assert p["full_name"] == "Jane Smith"
    assert "CEO" in p["designation"] or "Founder" in p["designation"]
    assert p["linkedin_url"] == "https://www.linkedin.com/in/janesmith-ceo"
    assert p["confidence"] >= 0.85

def test_people_discovery_from_dom_cards():
    service = PeopleDiscoveryService()
    html = """
    <html>
      <body>
        <div class="team-member">
          <h3 class="name">David Warner</h3>
          <p class="role">Managing Director</p>
          <a href="https://linkedin.com/in/david-warner-md">LinkedIn Profile</a>
        </div>
        <div class="leadership-card">
          <h4>Sarah Connor</h4>
          <span class="designation">Chief Technology Officer</span>
        </div>
        <!-- Bogus card that should be filtered out -->
        <div class="team-member">
          <h3>Contact Us</h3>
          <p>Support</p>
        </div>
      </body>
    </html>
    """
    people = service.discover_from_html(html, "https://acme.com/team", "Acme")
    names = [p["full_name"] for p in people]
    assert "David Warner" in names
    assert "Sarah Connor" in names
    assert "Contact Us" not in names

    david = next(p for p in people if p["full_name"] == "David Warner")
    assert david["designation"] == "Managing Director"
    assert david["linkedin_url"] == "https://linkedin.com/in/david-warner-md"

def test_people_discovery_heading_vicinity():
    service = PeopleDiscoveryService()
    html = """
    <html>
      <body>
        <div class="exec-section">
          <h3>Rajesh Sharma</h3>
          <p>Co-Founder & VP Engineering</p>
        </div>
      </body>
    </html>
    """
    people = service.discover_from_html(html, "https://techcorp.in/about", "TechCorp")
    assert any(p["full_name"] == "Rajesh Sharma" for p in people)

def test_name_validator_filters_false_names():
    service = PeopleDiscoveryService()
    assert service._is_valid_person_name("Jane Doe") is True
    assert service._is_valid_person_name("Vikram R. Patel") is True
    assert service._is_valid_person_name("About Us") is False
    assert service._is_valid_person_name("Privacy Policy") is False
    assert service._is_valid_person_name("CEO") is False
    assert service._is_valid_person_name("Acme") is False

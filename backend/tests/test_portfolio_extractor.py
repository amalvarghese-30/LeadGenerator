import pytest
from app.extraction.portfolio_extractor import PortfolioExtractor

def test_extract_cards_client_grid():
    html = """
    <html>
      <body>
        <div class="clients-grid">
          <div class="client-card">
            <h3>Mahavir Builders</h3>
            <span class="tag-pill">Real Estate</span>
            <p>Complete corporate website redesign and branding for leading property group.</p>
            <a class="visit-link" href="https://mahavirbuilders.com/">Visit Website</a>
          </div>
          <div class="client-card">
            <h3>Delight Jet</h3>
            <span class="tag-pill">Aviation & Luxury Charter</span>
            <p>Private jet charter booking portal and aircraft fleet showcase.</p>
            <a class="visit-link" href="https://delightjet.com/">Live Site</a>
          </div>
        </div>
      </body>
    </html>
    """
    extractor = PortfolioExtractor()
    cards = extractor.extract_portfolio_candidates(html, "https://example.com/portfolio")
    assert len(cards) == 2
    
    c1 = cards[0]
    assert c1["company_name"] == "Mahavir Builders"
    assert c1["external_url"] == "https://mahavirbuilders.com/"
    assert "Real Estate" in c1.get("tags", []) or "Real Estate" in c1.get("evidence_quote", "")
    assert c1["confidence"] >= 0.8

    c2 = cards[1]
    assert c2["company_name"] == "Delight Jet"
    assert c2["external_url"] == "https://delightjet.com/"
    assert "Aviation & Luxury Charter" in c2.get("tags", []) or "Aviation" in c2.get("evidence_quote", "")

def test_extract_cards_logo_grid():
    html = """
    <html>
      <body>
        <section class="partners-clients">
          <h2>Our Esteemed Clients</h2>
          <div class="logo-grid">
            <div class="logo-item">
              <a href="https://acmecorp.io">
                <img src="/logos/acme.png" alt="Acme Corporation Logo" />
              </a>
            </div>
            <div class="logo-item">
              <a href="https://globex.org">
                <img src="/logos/globex.png" alt="Globex Dynamics" />
              </a>
            </div>
          </div>
        </section>
      </body>
    </html>
    """
    extractor = PortfolioExtractor()
    cards = extractor.extract_portfolio_candidates(html, "https://example.com/clients")
    assert len(cards) == 2
    names = [c["company_name"] for c in cards]
    assert "Acme Corporation" in names
    assert "Globex Dynamics" in names

def test_filter_false_matches():
    html = """
    <html>
      <body>
        <div class="portfolio-grid">
          <div class="portfolio-item">
            <h3>WordPress</h3>
            <p>We build our websites using the WordPress CMS platform.</p>
            <a href="https://wordpress.org">Powered by WordPress</a>
          </div>
          <div class="portfolio-item">
            <h3>Facebook</h3>
            <p>Follow our agency on our Facebook social page.</p>
            <a href="https://facebook.com/myagency">Follow us</a>
          </div>
          <div class="portfolio-item">
            <h3>Valid Client Co</h3>
            <p>E-commerce redesign for retail distribution chain.</p>
            <a href="https://validclientco.in">View Project</a>
          </div>
        </div>
      </body>
    </html>
    """
    extractor = PortfolioExtractor()
    cards = extractor.extract_portfolio_candidates(html, "https://example.com/work")
    client_names = [c["company_name"] for c in cards]
    assert "Valid Client Co" in client_names
    # Excluded platform domains should not be accepted
    assert "WordPress" not in client_names
    assert "Facebook" not in client_names

def test_extract_card_with_generic_cta_and_section_context():
    html = """
    <html>
      <body>
        <section class="portfolio-section">
          <h2>Maintain</h2>
          <p>Every site below is live, built in-house, and actively maintained by our dedicated web team.</p>
          <div class="projects-grid">
            <div class="project-card">
              <h3>Mahavir Builders</h3>
              <p>Luxury residential and commercial developments across Gujarat and Maharashtra.</p>
              <a href="https://mahavirbuilders.com" target="_blank">Visit Site →</a>
            </div>
          </div>
        </section>
      </body>
    </html>
    """
    extractor = PortfolioExtractor()
    cards = extractor.extract_portfolio_candidates(html, "https://akham.in/portfolio")
    assert len(cards) >= 1

    card = next(c for c in cards if c["company_name"] == "Mahavir Builders")
    assert card["client_website_url"] == "https://mahavirbuilders.com"
    assert card["verified_website"] == "https://mahavirbuilders.com"
    assert card["website"] == "https://mahavirbuilders.com"
    assert "[Maintain]" in card["evidence_snippet"]
    assert "actively maintained" in card["evidence_snippet"]


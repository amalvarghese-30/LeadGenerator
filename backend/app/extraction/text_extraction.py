"""
Multi-signal page classification and client-reference signal detection.
Replaces simplistic keyword counters with structured multi-signal analysis across:
- URL path structure
- Page title & meta description
- H1 / H2 headings
- Content sections (case study sections, testimonial quotes, client grids)
- Schema.org markup (Review, CaseStudy, ProfilePage, Service, Article)
- Negative service / sales / article pitch detection
"""
import re
from typing import Dict, List, Any, Optional
from urllib.parse import urlparse


class TextExtractor:
    """Multi-signal page relevance and category classifier."""

    # Explicit URL path patterns
    CASE_STUDY_URL_PATTERNS = [r'/case-stud', r'/client-stor', r'/success-stor', r'/results/']
    PORTFOLIO_URL_PATTERNS = [r'/portfolio', r'/our-work', r'/work/', r'/projects/', r'/showcase']
    TESTIMONIAL_URL_PATTERNS = [r'/testimonial', r'/reviews?/', r'/client-feedback', r'/what-clients-say']
    CUSTOMER_STORY_URL_PATTERNS = [r'/customer-stor', r'/clients?/', r'/who-we-help']
    CLIENT_PROFILE_URL_PATTERNS = [
        r'/client-profile', r'/featured-client', r'/spotlight',
        r'/p/[a-z0-9_\-]+', r'/profile/[a-z0-9_\-]+', r'/person/[a-z0-9_\-]+', r'/people/[a-z0-9_\-]+'
    ]

    SERVICE_URL_PATTERNS = [
        r'/services?', r'/what-we-do', r'/solutions?', r'/offerings?', r'/packages?',
        r'/pricing', r'/features?', r'/plans?', r'/consulting-services'
    ]
    ARTICLE_URL_PATTERNS = [
        r'/blog', r'/news', r'/articles?', r'/posts?', r'/insights?', r'/press-release',
        r'/category/', r'/tag/', r'/author/'
    ]
    ABOUT_URL_PATTERNS = [
        r'/about', r'/team', r'/leadership', r'/company', r'/our-story', r'/careers',
        r'/contact', r'/jobs'
    ]
    IRRELEVANT_URL_PATTERNS = [
        r'/privacy', r'/terms', r'/cookie', r'/legal', r'/sitemap', r'/login',
        r'/signup', r'/cart', r'/checkout', r'/account'
    ]

    # Strong in-content and heading indicators
    CASE_STUDY_HEADINGS = [
        "case study", "client case study", "success story", "client results",
        "transformation story", "how we helped", "the challenge", "the solution"
    ]
    TESTIMONIAL_HEADINGS = [
        "client testimonial", "what our clients say", "what clients say", "client reviews",
        "testimonials", "words from our clients", "feedback from clients", "client praise"
    ]
    PORTFOLIO_HEADINGS = [
        "our work", "selected work", "featured projects", "recent work", "client portfolio",
        "featured clients", "brands we have worked with", "our portfolio"
    ]
    CUSTOMER_STORY_HEADINGS = [
        "customer story", "customer stories", "client spotlight", "client success stories"
    ]
    CLIENT_PROFILE_HEADINGS = [
        "client profile", "published profile", "executive profile", "knowledge panel for"
    ]

    # Negative service pitch phrases (indicate Service Page, not a client evidence page)
    SERVICE_PITCH_PHRASES = [
        "our services include", "we offer comprehensive", "our pricing plans", "request a quote",
        "book a free consultation", "choose the right plan", "what our service provides",
        "services we provide", "contact our sales team", "explore our packages",
        "monthly retainer", "custom pricing", "hire our team", "core capabilities"
    ]

    def classify_page_relevance(
        self,
        url: str,
        title: str = "",
        text: str = "",
        h1: str = "",
        h2s: Optional[List[str]] = None,
        schema_types: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Classify page relevance for client reference discovery using multi-signal analysis.
        Returns:
            is_client_reference_page: bool (True only for verified client evidence pages)
            relevance_score: int (0 to 100)
            page_category: str
            indicators_found: List[str]
            rejection_reasons: List[str]
        """
        parsed = urlparse(url)
        path = parsed.path.lower()
        title_lower = title.lower()
        h1_lower = (h1 or "").lower()
        h2_list = [h.lower() for h in (h2s or [])]
        combined_headings = f"{h1_lower} {' '.join(h2_list)}"
        sample_text = (text or "")[:8000].lower()
        schema_set = {s.lower() for s in (schema_types or [])}

        indicators_found: List[str] = []
        negative_signals: List[str] = []

        # 1. Immediate Irrelevant check
        if any(re.search(pat, path) for pat in self.IRRELEVANT_URL_PATTERNS):
            return {
                "is_client_reference_page": False,
                "relevance_score": 0,
                "page_category": "Irrelevant",
                "indicators_found": [],
                "rejection_reasons": ["URL path matches excluded system/legal/auth pattern"],
            }

        # 2. Check Service Pitch & Service Page patterns
        service_url_match = any(re.search(pat, path) for pat in self.SERVICE_URL_PATTERNS)
        service_pitch_count = sum(1 for p in self.SERVICE_PITCH_PHRASES if p in sample_text)
        service_heading_match = any(term in combined_headings for term in ["our services", "services", "pricing", "packages", "what we offer"])

        # 3. Check Article / Blog patterns
        article_url_match = any(re.search(pat, path) for pat in self.ARTICLE_URL_PATTERNS)
        article_schema = any("article" in s or "blogposting" in s or "newsarticle" in s for s in schema_set)

        # 4. Check About / Team patterns
        about_url_match = any(re.search(pat, path) for pat in self.ABOUT_URL_PATTERNS)
        about_heading_match = any(term in combined_headings for term in ["about us", "our team", "meet the team", "leadership", "our story"])

        # 5. Check Client Evidence signals (Case study, Testimonial, Portfolio, etc.)
        case_study_url = any(re.search(pat, path) for pat in self.CASE_STUDY_URL_PATTERNS)
        case_study_heading = any(term in combined_headings for term in self.CASE_STUDY_HEADINGS)
        has_challenge_solution = ("challenge" in sample_text and "solution" in sample_text and "results" in sample_text)

        portfolio_url = any(re.search(pat, path) for pat in self.PORTFOLIO_URL_PATTERNS)
        portfolio_heading = any(term in combined_headings for term in self.PORTFOLIO_HEADINGS)

        testimonial_url = any(re.search(pat, path) for pat in self.TESTIMONIAL_URL_PATTERNS)
        testimonial_heading = any(term in combined_headings for term in self.TESTIMONIAL_HEADINGS)
        has_review_schema = any("review" in s or "aggregaterating" in s for s in schema_set)

        customer_story_url = any(re.search(pat, path) for pat in self.CUSTOMER_STORY_URL_PATTERNS)
        customer_story_heading = any(term in combined_headings for term in self.CUSTOMER_STORY_HEADINGS)

        profile_url = any(re.search(pat, path) for pat in self.CLIENT_PROFILE_URL_PATTERNS)
        profile_heading = any(term in combined_headings for term in self.CLIENT_PROFILE_HEADINGS)

        # Calculate evidence scoring
        evidence_score = 0
        if case_study_url:
            evidence_score += 45
            indicators_found.append("case_study_url")
        if case_study_heading:
            evidence_score += 35
            indicators_found.append("case_study_heading")
        if has_challenge_solution:
            evidence_score += 20
            indicators_found.append("challenge_solution_structure")

        if testimonial_url:
            evidence_score += 45
            indicators_found.append("testimonial_url")
        if testimonial_heading:
            evidence_score += 35
            indicators_found.append("testimonial_heading")
        if has_review_schema:
            evidence_score += 30
            indicators_found.append("review_schema_markup")

        if portfolio_url:
            evidence_score += 40
            indicators_found.append("portfolio_url")
        if portfolio_heading:
            evidence_score += 30
            indicators_found.append("portfolio_heading")

        if customer_story_url:
            evidence_score += 40
            indicators_found.append("customer_story_url")
        if customer_story_heading:
            evidence_score += 30
            indicators_found.append("customer_story_heading")

        if profile_url:
            evidence_score += 35
            indicators_found.append("client_profile_url")
        if profile_heading:
            evidence_score += 30
            indicators_found.append("client_profile_heading")

        # Penalize if page is primarily a service pitch or marketing article
        penalty = 0
        if service_url_match:
            penalty += 40
            negative_signals.append("service_url")
        if service_heading_match:
            penalty += 25
            negative_signals.append("service_heading")
        if service_pitch_count >= 2:
            penalty += 30
            negative_signals.append(f"service_pitch_phrases_found_{service_pitch_count}")

        if article_url_match:
            penalty += 40
            negative_signals.append("article_url")
        if article_schema:
            penalty += 25
            negative_signals.append("article_schema")

        if about_url_match:
            penalty += 40
            negative_signals.append("about_url")
        if about_heading_match:
            penalty += 25
            negative_signals.append("about_heading")

        # Determine Category
        final_score = max(0, min(100, evidence_score - (penalty if evidence_score < 70 else penalty // 2)))

        if case_study_url or (case_study_heading and evidence_score >= 40):
            category = "Case Study"
        elif testimonial_url or (testimonial_heading and evidence_score >= 40) or has_review_schema:
            category = "Testimonial"
        elif customer_story_url or customer_story_heading:
            category = "Customer Story"
        elif portfolio_url or (portfolio_heading and evidence_score >= 35):
            category = "Client Portfolio"
        elif profile_url or profile_heading:
            category = "Published Client Profile"
        elif service_url_match or service_heading_match or service_pitch_count >= 2:
            category = "Service Page"
        elif article_url_match or article_schema:
            category = "General Article"
        elif about_url_match or about_heading_match:
            category = "About Page"
        elif evidence_score >= 35:
            category = "Customer Story"
        else:
            category = "Irrelevant"

        # Determine if this page should be processed for client references
        valid_client_categories = {
            "Case Study", "Client Portfolio", "Testimonial", "Customer Story", "Published Client Profile"
        }
        is_client_page = (category in valid_client_categories) and (final_score >= 35)

        reasons = []
        if not is_client_page:
            if category in ["Service Page", "General Article", "About Page"]:
                reasons.append(f"Page classified as {category}; generic services/articles are excluded from client extraction")
            else:
                reasons.append("Insufficient client evidence signals (score below threshold)")

        return {
            "is_client_reference_page": is_client_page,
            "relevance_score": final_score,
            "page_category": category,
            "indicators_found": indicators_found,
            "negative_signals": negative_signals,
            "rejection_reasons": reasons,
        }

    def extract_emails(self, text: str, url: str) -> List[Dict[str, Any]]:
        """Extract ONLY explicitly published emails with source page attribution."""
        pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b'
        matches = list(set(re.findall(pattern, text or "")))
        valid = []
        for email in matches:
            if not email.lower().endswith((".png", ".jpg", ".jpeg", ".webp", ".svg", ".gif", ".js", ".css")):
                is_generic = any(
                    email.lower().startswith(p)
                    for p in ["info@", "contact@", "hello@", "support@", "enquiry@", "team@"]
                )
                valid.append({
                    "email": email,
                    "source_url": url,
                    "is_generic": is_generic,
                    "verified": False,
                    "attribution": "explicitly_published"
                })
        return valid

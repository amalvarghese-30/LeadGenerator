"""
Page classification and client-reference signal detection.
Analyzes page content, headings, and URL paths to identify client case studies,
testimonials, reviews, and portfolio mentions.
"""
import re
from typing import Dict, List, Any

CLIENT_PAGE_INDICATORS = [
    "case study", "case-study", "our clients", "client success",
    "success story", "testimonial", "testimonials", "portfolio",
    "our work", "featured clients", "customer story", "transformation",
    "who we helped", "our customers", "client showcase", "worked with",
    "google knowledge panel for", "personal brand for", "client review"
]

class TextExtractor:
    def classify_page_relevance(self, url: str, title: str, text: str) -> Dict[str, Any]:
        """
        Classify page relevance for client reference discovery.
        Returns:
            is_client_reference_page: bool
            relevance_score: 0-100
            page_category: str
            indicators_found: list of matched keywords
        """
        content_lower = f"{url.lower()} {title.lower()} {text[:5000].lower()}"
        indicators_found = [ind for ind in CLIENT_PAGE_INDICATORS if ind in content_lower]

        score = min(100, len(indicators_found) * 20)
        is_client_page = len(indicators_found) > 0 and score >= 20

        # Determine category
        url_lower = url.lower()
        if "case-stud" in url_lower or "case study" in content_lower:
            category = "case_study"
        elif "testimonial" in url_lower or "testimonial" in content_lower or "review" in url_lower:
            category = "testimonial"
        elif "portfolio" in url_lower or "our work" in content_lower:
            category = "portfolio"
        elif "client" in url_lower or "our clients" in content_lower or "customers" in url_lower:
            category = "client_list"
        elif "about" in url_lower or "team" in url_lower:
            category = "about"
        else:
            category = "general"

        return {
            "is_client_reference_page": is_client_page,
            "relevance_score": score,
            "page_category": category,
            "indicators_found": indicators_found,
        }

    def extract_emails(self, text: str, url: str) -> List[Dict[str, Any]]:
        """Extract ONLY explicitly published emails with source page attribution."""
        pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b'
        matches = list(set(re.findall(pattern, text)))
        valid = []
        for email in matches:
            if not email.lower().endswith((".png", ".jpg", ".jpeg", ".webp", ".svg", ".gif", ".js", ".css")):
                is_generic = any(email.lower().startswith(p) for p in ["info@", "contact@", "hello@", "support@", "enquiry@", "team@"])
                valid.append({
                    "email": email,
                    "source_url": url,
                    "is_generic": is_generic,
                    "verified": False,
                    "attribution": "explicitly_published"
                })
        return valid

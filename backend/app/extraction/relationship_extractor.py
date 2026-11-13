"""
Relationship classifier.
Classifies the relationship type between a discovered provider and a mentioned entity or individual.
"""
from typing import Optional

RELATIONSHIP_KEYWORDS = {
    "client_testimonial": [
        "testimonial", "says", "review", "feedback", "highly recommend", "worked wonders",
        "client feedback", "star review", "delighted with"
    ],
    "confirmed_client_case_study": [
        "case study", "worked with", "helped", "our client", "success story",
        "transformed", "built google knowledge panel for", "established authority for",
        "results achieved", "growth story", "client results"
    ],
    "client_portfolio_reference": [
        "portfolio", "our work", "project for", "work delivered", "featured in portfolio",
        "delivered for"
    ],
    "published_customer_profile": [
        "profile of", "spotlight on", "customer profile", "client spotlight"
    ],
    "featured_personality": [
        "interview with", "featured on", "guest podcast", "speaker at", "in conversation with"
    ],
    "collaborator": [
        "partnered with", "in collaboration with", "co-authored", "joint venture"
    ],
}

class RelationshipExtractor:
    def classify(self, context_text: str, page_category: str = "general") -> str:
        """
        Classify reference relationship.
        Returns:
            confirmed_client_case_study | client_testimonial | client_portfolio_reference |
            published_customer_profile | featured_personality | collaborator |
            ordinary_mention | unclear_relationship
        """
        lower = context_text.lower()

        for rel_type, keywords in RELATIONSHIP_KEYWORDS.items():
            if any(k in lower for k in keywords):
                return rel_type

        # Use page category as fallback
        if page_category == "case_study":
            return "confirmed_client_case_study"
        elif page_category == "testimonial":
            return "client_testimonial"
        elif page_category == "portfolio":
            return "client_portfolio_reference"
        elif page_category == "client_list":
            return "client_portfolio_reference"

        return "unclear_relationship"

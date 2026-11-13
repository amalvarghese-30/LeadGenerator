"""
Name Validator - Multi-stage Person Name & Entity Validation Pipeline.
Strictly eliminates false-positive person references (navigation labels, sentence fragments,
SEO text, accessibility captions, generic headings, company names, verbs).
"""
import re
import unicodedata
from typing import Tuple, List, Optional, Set

# Generic UI, Navigation & CTA phrases
NAV_AND_UI_TERMS: Set[str] = {
    "view more", "learn more", "read more", "get started", "contact us", "click here",
    "sign in", "sign up", "log in", "home page", "back to top", "menu", "skip to content",
    "load more", "see all", "previous", "next", "close", "search", "subscribe", "submit",
    "download", "share", "follow", "like", "tweet", "pin", "privacy policy", "terms of service",
    "terms of use", "all rights reserved", "cookie policy", "site map", "navigation",
    "header", "footer", "join now", "book now", "request demo", "free consultation",
    "call today", "find out more", "check out", "explore more", "view all", "show more",
    "continue reading", "table of contents", "read time", "min read",
}

# Accessibility & Media / UI artifacts
ACCESSIBILITY_AND_MEDIA_TERMS: Set[str] = {
    "caption", "each caption", "alt text", "photo", "image", "graphic", "icon", "logo",
    "banner", "screenshot", "video", "thumbnail", "placeholder", "svg", "figure",
    "diagram", "avatar", "profile picture", "illustration", "visual", "badge",
    "button", "link", "carousel", "slider", "modal", "lightbox", "gallery",
    "audio clip", "infographic", "embedded media",
}

# Generic Marketing, SEO & Fluff Phrases
MARKETING_AND_SEO_TERMS: Set[str] = {
    "your business", "our services", "our work", "our clients", "our team", "our mission",
    "about us", "who we are", "what we do", "how it works", "customer reviews", "client reviews",
    "client testimonials", "key benefits", "case study", "case studies", "success stories",
    "recent projects", "featured work", "featured clients", "search results",
    "google knowledge panel", "entity seo", "personal branding", "executive reputation",
    "digital marketing", "seo optimization", "web design", "social media", "content marketing",
    "press release", "news article", "blog post", "latest news", "trending topics",
    "growth strategy", "all time", "all-time", "set an all-time", "industry leaders",
    "trusted by", "world class", "proven results", "verified results", "highest rating",
    "five star", "5 star", "market leader", "competitive advantage", "tailored solutions",
    "cutting edge", "innovative solutions", "high performance", "best practices",
    "end to end", "seamless integration", "roi driven", "data driven", "full service",
}

# English closed-class words & common non-name tokens (lowercase)
NON_NAME_WORDS: Set[str] = {
    # Pronouns & determiners
    "a", "an", "the", "this", "that", "these", "those", "each", "every", "all",
    "both", "neither", "either", "some", "any", "no", "none", "my", "your", "his",
    "her", "its", "our", "their", "mine", "yours", "hers", "ours", "theirs", "what",
    "which", "who", "whom", "whose", "whatever", "whichever", "whoever", "whomever",
    "we", "you", "they", "them", "us", "he", "she", "it", "one", "ones",
    # Prepositions & conjunctions
    "in", "on", "at", "to", "for", "with", "from", "by", "about", "into", "through",
    "after", "over", "between", "out", "against", "during", "without", "before",
    "under", "around", "among", "and", "but", "or", "nor", "so", "yet", "if",
    "because", "as", "until", "while", "of", "off", "up", "down", "than", "then",
    # Common verbs & auxiliary verbs
    "is", "are", "was", "were", "be", "been", "being", "have", "has", "had",
    "do", "does", "did", "can", "could", "will", "would", "shall", "should",
    "may", "might", "must", "set", "rank", "ranks", "ranked", "ranking",
    "get", "gets", "got", "make", "makes", "made", "take", "takes", "took",
    "see", "sees", "saw", "know", "knows", "knew", "think", "thinks", "thought",
    "look", "looks", "looked", "use", "uses", "used", "find", "finds", "found",
    "give", "gives", "gave", "tell", "tells", "told", "work", "works", "worked",
    "call", "calls", "called", "try", "tries", "tried", "ask", "asks", "asked",
    "need", "needs", "needed", "feel", "feels", "felt", "become", "becomes", "became",
    "help", "helps", "helped", "start", "starts", "started", "show", "shows", "showed",
    "run", "runs", "ran", "move", "moves", "moved", "live", "lives", "lived",
    "believe", "believes", "believed", "bring", "brings", "brought", "write", "writes",
    "provide", "provides", "provided", "learn", "learns", "learned", "change", "changes",
    "lead", "leads", "led", "create", "creates", "created", "grow", "grows", "grew",
    "offer", "offers", "offered", "build", "builds", "built", "boost", "boosts",
    "drive", "drives", "driven", "achieve", "achieves", "achieved", "deliver", "delivers",
    # Generic plural nouns frequently capitalized in headings
    "accounts", "users", "clients", "customers", "people", "things", "ways",
    "times", "years", "days", "months", "items", "results", "details", "steps",
    "facts", "tips", "services", "solutions", "features", "benefits", "industries",
    "reviews", "testimonials", "stories", "projects", "companies", "brands",
    "experts", "professionals", "leaders", "specialists", "consultants",
}

# Company suffix words - when present in a name, it's a corporate entity, not an individual
COMPANY_INDICATORS: Set[str] = {
    "inc", "inc.", "llc", "l.l.c.", "ltd", "ltd.", "corp", "corp.", "corporation",
    "company", "co", "co.", "group", "holdings", "properties", "real estate", "estate",
    "realty", "capital", "partners", "ventures", "investments", "associates", "consulting",
    "solutions", "technologies", "tech", "systems", "studios", "agency", "labs",
    "media", "digital", "enterprises", "global", "international", "services",
    "foundation", "association", "institute", "organization", "network", "fund",
    "advisors", "management", "logistics", "industries", "communications",
}

# Recognized honorary titles/prefixes
HONORIFIC_PREFIXES: Set[str] = {
    "mr", "mr.", "mrs", "mrs.", "ms", "ms.", "dr", "dr.", "prof", "prof.",
    "sir", "madam", "adv", "adv.", "counsel",
}


class NameValidator:
    """Multi-stage validation pipeline for candidate person names."""

    @classmethod
    def validate_person_name(cls, candidate: str, context: Optional[str] = None) -> Tuple[bool, List[str]]:
        """
        Validate whether a candidate string is a plausible, real person name.
        Returns: (is_valid, rejection_reasons)
        """
        rejection_reasons: List[str] = []

        if not candidate or not isinstance(candidate, str):
            return False, ["Candidate name is empty or not a string"]

        raw = candidate.strip()
        lower = raw.lower()

        # 1. Length bounds
        if len(raw) < 3:
            return False, ["Candidate name is too short (less than 3 characters)"]
        if len(raw) > 50:
            return False, ["Candidate name exceeds reasonable person name length (> 50 chars)"]

        # 2. Reject internal sentence terminators or multiple sentences (e.g. "accounts. Each caption")
        # Allow trailing period only for honorifics or middle initials (e.g., "Dr.", "John F. Kennedy")
        if re.search(r'[!?;:\n\r\t]', raw):
            return False, ["Contains punctuation or newline breaking sentence boundary"]

        # Check for periods: if a period occurs, it must only follow a single initial (e.g., " A. ") or title ("Dr.")
        periods = [m.start() for m in re.finditer(r'\.', raw)]
        for p in periods:
            # Word preceding the period
            preceding = raw[:p].split()[-1] if raw[:p].split() else ""
            if len(preceding) > 1 and preceding.lower() not in HONORIFIC_PREFIXES:
                return False, [f"Candidate contains mid-sentence period after '{preceding}' indicating sentence fragment"]

        # 3. Reject numbers, symbols, web URLs or emails
        if re.search(r'[\d@#\$%\^&\*\+=\[\]\{\}\|\\<>/_~`]', raw):
            return False, ["Contains numbers, symbols, or code artifacts"]

        # 4. Check negative phrases (Exact or substring matches)
        # Check against Nav, Accessibility, Marketing
        for term in NAV_AND_UI_TERMS:
            if lower == term or f" {term} " in f" {lower} ":
                return False, [f"Matched navigation or UI phrase: '{term}'"]

        for term in ACCESSIBILITY_AND_MEDIA_TERMS:
            if lower == term or f" {term} " in f" {lower} ":
                return False, [f"Matched accessibility or media phrase: '{term}'"]

        for term in MARKETING_AND_SEO_TERMS:
            if lower == term or f" {term} " in f" {lower} ":
                return False, [f"Matched generic marketing or SEO phrase: '{term}'"]

        # 5. Token analysis
        # Remove honorific prefix if present for component analysis
        tokens = [t.strip(",.") for t in raw.split() if t.strip(",.")]
        if not tokens:
            return False, ["No valid word tokens found"]

        clean_tokens = [t for t in tokens if t.lower() not in HONORIFIC_PREFIXES]
        if len(clean_tokens) < 2:
            return False, ["Must have at least two plausible name components (first and last name)"]
        if len(clean_tokens) > 4:
            return False, ["Too many name components (> 4 words)"]

        # Check capitalization: all name tokens must start with an uppercase letter
        for token in clean_tokens:
            # Support hyphenated names like Smith-Jones
            sub_tokens = token.split("-")
            for st in sub_tokens:
                if not st or not st[0].isupper():
                    return False, [f"Name component '{token}' is not properly capitalized"]
                if not st.isalpha():
                    return False, [f"Name component '{token}' contains invalid characters"]

        # 6. Check against closed-class non-name words and common verbs
        token_lowers = [t.lower() for t in clean_tokens]
        for t_lower in token_lowers:
            if t_lower in NON_NAME_WORDS:
                return False, [f"Name component '{t_lower}' is a common verb, pronoun, or generic term"]

        # 7. Check for Company indicator words or corporate phrases
        for term in COMPANY_INDICATORS:
            if f" {term} " in f" {lower} " or lower.endswith(f" {term}") or lower.startswith(f"{term} "):
                return False, [f"Candidate contains corporate indicator '{term}' (company entity, not person)"]

        for t_lower in token_lowers:
            if t_lower in COMPANY_INDICATORS:
                return False, [f"Candidate contains corporate indicator '{t_lower}' (company entity, not person)"]

        # 8. Check context if provided
        if context:
            ctx_lower = context.lower()
            # If the context is just an isolated navigation bar or cookie message
            if any(term in ctx_lower for term in ["cookie policy", "accept all cookies", "skip to navigation"]):
                rejection_reasons.append("Context indicates header, footer, or navigation noise")

        return True, []

    @classmethod
    def clean_name(cls, raw: str) -> Optional[str]:
        """
        Normalize and clean a candidate name.
        Returns cleaned string if it passes validation, else None.
        """
        if not raw:
            return None
        # Normalize unicode
        clean = unicodedata.normalize("NFKD", raw)
        clean = re.sub(r'\s+', ' ', clean).strip()
        # Strip outer punctuation
        clean = clean.strip(" ,.-–—:;\"'()[]{}")
        is_valid, _ = cls.validate_person_name(clean)
        if is_valid:
            return clean
        return None

    @classmethod
    def is_likely_company_name(cls, raw: str) -> bool:
        """Check if candidate is a business/corporate entity rather than a person."""
        if not raw:
            return False
        lower = raw.lower().strip()
        tokens = [t.strip(",.") for t in lower.split()]
        if any(t in COMPANY_INDICATORS for t in tokens):
            return True
        if any(term in lower for term in ["ltd", "inc.", "llc", "technologies", "studios", "properties", "agency", "solutions"]):
            return True
        return False

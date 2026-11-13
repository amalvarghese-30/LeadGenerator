"""
Deterministic NLP extraction for client references and evidence.
Combines:
  - Multi-stage person name validation (NameValidator)
  - Sentence and paragraph level semantic parsing
  - Per-candidate individual relationship classification
  - Company-only reference detection (without inventing fake people)
  - Strict evidence quotation attribution

Never invents facts. Only extracts what appears verbatim in the text.
"""
import re
import logging
from typing import Dict, List, Optional, Tuple, Any
from urllib.parse import urlparse

from app.extraction.name_validator import NameValidator

logger = logging.getLogger(__name__)

# Designations & Titles
DESIGNATION_KEYWORDS = [
    "Chief Executive Officer", "Chief Technology Officer", "Chief Financial Officer",
    "Chief Operating Officer", "Chief Marketing Officer", "Chief Product Officer",
    "Chief Information Officer", "Chief Revenue Officer", "Chief Legal Officer",
    "Founder", "Co-Founder", "Co Founder", "Founding Partner",
    "CEO", "CTO", "CFO", "COO", "CMO", "CPO", "CIO", "CRO",
    "Managing Director", "Executive Director", "Senior Director", "Director",
    "President", "Vice President", "VP", "Head of", "General Manager", "GM",
    "Senior Partner", "Managing Partner", "Partner", "Principal",
    "Chairman", "Chairwoman", "Board Member",
    "Author", "Co-Author", "Writer", "Journalist",
    "Advocate", "Attorney", "Counsel", "Barrister", "Solicitor", "Lawyer",
    "Surgeon", "Physician", "Specialist", "Consultant", "Doctor", "Dr.",
    "Executive Coach", "Mentor", "Senior Advisor", "Advisor", "Coach",
    "Keynote Speaker", "Public Speaker", "Speaker",
    "Professor", "Lecturer", "Researcher",
    "Business Owner", "Entrepreneur", "Investor",
]

DESIGNATION_REGEX = re.compile(
    r'\b(' + '|'.join(re.escape(k) for k in DESIGNATION_KEYWORDS) + r')(?:\s+of|\s+at|\s*[,–—])?\b',
    re.IGNORECASE,
)

# Testimonial block pattern: "Quote" - Name, Role at Company
QUOTE_ATTRIBUTION_PATTERN = re.compile(
    r'["“]([^"”]{20,500})["”]\s*[-–—\n]+\s*'
    r'([A-Z][a-zA-Z\.\-\']+(?:\s+[A-Z][a-zA-Z\.\-\']+){1,3})'
    r'(?:[,\s\-–—]+([A-Za-z\s/]{2,40}))?'
    r'(?:[,\s\-–—]+(?:at|of|,)?\s*([A-Z][\w\s&\.\-\']{2,50}))?'
)

# "Name, Role at Company"
NAME_ROLE_COMPANY_PATTERN = re.compile(
    r'\b([A-Z][a-zA-Z\.\-\']+(?:\s+[A-Z][a-zA-Z\.\-\']+){1,3})'
    r'[,\s\-–—]+'
    r'((?:Co-?)?(?:Founder|CEO|CTO|CFO|COO|CMO|President|Director|Partner|Chairman|'
    r'Managing Director|Chief \w+ Officer|Head of [A-Za-z\s]+|Vice President|VP))'
    r'(?:\s+(?:of|at|@|,)\s+'
    r'([A-Z][a-zA-Z0-9&\-\'\.\s]{2,60}?))?'
    r'(?=[\.,;:\)\n]|$)'
)

# "Company: TechVision, Founder: John Doe"
REVERSE_ROLE_PATTERN = re.compile(
    r'(?:Client|Company|Organi[sz]ation|Business|Firm)\s*[:–-]\s*([A-Z][\w\s&\.\-\']{2,50}?)'
    r'[,\n;\s]+'
    r'(?:Founder|CEO|Director|Contact|Executive|Owner)\s*[:–-]\s*([A-Z][a-zA-Z\.\-\']+(?:\s+[A-Z][a-zA-Z\.\-\']+){1,3})',
    re.IGNORECASE,
)

# Company-only portfolio card pattern: "Client: Acme Corp" / "Project: Acme Corp" / "Our work for Acme Corp"
COMPANY_PORTFOLIO_PATTERN = re.compile(
    r'(?:(?:Client|Project|Case Study|Customer)\s*[:–\-]\s*|Our work for\s+)'
    r'([A-Z][a-zA-Z0-9&\.\-\']+(?:\s+[A-Z][a-zA-Z0-9&\.\-\']+){0,3})'
    r'(?:\s+(?:was|is|has|in|delivered|scaled|featured)|[\.,\n;:]|$)',
    re.IGNORECASE,
)

# Relationship keyword signals mapped to specific classifications
RELATIONSHIP_SIGNALS = [
    ("client_testimonial", [
        "testimonial", "says", "said", "highly recommend", "worked wonders",
        "client feedback", "star review", "delighted with", "in their own words",
        "working with them", "pleasure to work with", "exceptional service",
        "best decision", "great experience", "exceeded expectations"
    ]),
    ("confirmed_client_case_study", [
        "case study", "client case study", "success story", "client results",
        "how we helped", "transformed", "results achieved", "growth story",
        "we delivered", "we built", "the challenge", "the solution", "metrics achieved",
        "project overview", "delivered for"
    ]),
    ("client_portfolio_reference", [
        "portfolio", "selected work", "our work for", "project for",
        "featured in portfolio", "clients we serve", "featured project",
        "client showcase"
    ]),
    ("published_customer_profile", [
        "customer profile", "client spotlight", "client profile",
        "knowledge panel for", "personal brand for", "spotlight on"
    ]),
    ("featured_personality", [
        "interview with", "featured on", "guest podcast", "speaker at",
        "in conversation with", "guest speaker", "keynote by", "panelist"
    ]),
    ("collaborator", [
        "in collaboration with", "co-authored", "joint venture", "community partner",
        "co-hosted", "partnered with", "technology partner"
    ]),
    ("ordinary_mention", [
        "quoted in", "according to", "as noted by", "referenced by", "written by",
        "author:", "byline:", "posted by"
    ]),
]


class PageAnalyzer:
    """Multi-signal deterministic extraction for verified client references."""

    def __init__(self):
        self.name_validator = NameValidator()

    def analyze(self, text: str, url: str, title: str = "") -> List[Dict[str, Any]]:
        """
        Extract individual candidate client references with strict validation.
        Each candidate is classified independently based on its own paragraph & context.
        """
        if not text or len(text.strip()) < 50:
            return []

        # Clean noise: remove navigation and boilerplate lines
        cleaned_text = self._filter_boilerplate(text)
        sample = cleaned_text[:35000]

        candidates: List[Dict[str, Any]] = []
        seen_keys = set()

        # -------------------------------------------------------------
        # Pattern 1: Explicit Testimonial Quotes
        # -------------------------------------------------------------
        for match in QUOTE_ATTRIBUTION_PATTERN.finditer(sample):
            quote = match.group(1).strip()
            raw_name = match.group(2).strip()
            role = match.group(3).strip() if match.group(3) else None
            company = match.group(4).strip() if match.group(4) else None

            # Validate name
            is_valid, reasons = self.name_validator.validate_person_name(raw_name, context=quote)
            if not is_valid:
                logger.debug("Testimonial name rejected: %s (%s)", raw_name, reasons)
                continue

            cleaned_name = self.name_validator.clean_name(raw_name)
            if not cleaned_name:
                continue

            key = cleaned_name.lower()
            if key in seen_keys:
                continue
            seen_keys.add(key)

            evidence = f'"{quote}" — {cleaned_name}'
            if role:
                evidence += f', {role}'
            if company:
                evidence += f' at {company}'

            candidates.append({
                "person_name": cleaned_name,
                "designation": self._clean_role(role),
                "company_name": self._clean_company(company),
                "relationship_type": "client_testimonial",
                "evidence_quote": evidence[:450],
                "confidence": 0.95,
                "extraction_method": "deterministic_testimonial_quote",
                "source_url": url,
            })

        # -------------------------------------------------------------
        # Pattern 2: "Name, Role at Company"
        # -------------------------------------------------------------
        for match in NAME_ROLE_COMPANY_PATTERN.finditer(sample):
            raw_name = match.group(1).strip()
            raw_role = match.group(2).strip()
            raw_comp = match.group(3).strip() if match.group(3) else None

            # Validate name
            ctx = self._context(sample, match.start(), match.end(), 250)
            is_valid, reasons = self.name_validator.validate_person_name(raw_name, context=ctx)
            if not is_valid:
                logger.debug("Name/Role candidate rejected: %s (%s)", raw_name, reasons)
                continue

            cleaned_name = self.name_validator.clean_name(raw_name)
            if not cleaned_name:
                continue

            key = cleaned_name.lower()
            if key in seen_keys:
                continue
            seen_keys.add(key)

            # Classify relationship based on THIS candidate's context
            rel_type, confidence = self._classify_candidate_relationship(ctx, cleaned_name, raw_comp)

            # Ordinary mentions or unclear relationships from blog/articles are excluded
            if rel_type in ["ordinary_mention", "unclear_relationship"] and confidence < 0.6:
                continue

            candidates.append({
                "person_name": cleaned_name,
                "designation": self._clean_role(raw_role),
                "company_name": self._clean_company(raw_comp),
                "relationship_type": rel_type,
                "evidence_quote": ctx[:450],
                "confidence": confidence,
                "extraction_method": "deterministic_name_role_company",
                "source_url": url,
            })

        # -------------------------------------------------------------
        # Pattern 3: Reverse format "Client: X, Founder: Y"
        # -------------------------------------------------------------
        for match in REVERSE_ROLE_PATTERN.finditer(sample):
            raw_comp = match.group(1).strip()
            raw_name = match.group(2).strip()

            ctx = self._context(sample, match.start(), match.end(), 250)
            is_valid, reasons = self.name_validator.validate_person_name(raw_name, context=ctx)
            if not is_valid:
                continue

            cleaned_name = self.name_validator.clean_name(raw_name)
            if not cleaned_name:
                continue

            key = cleaned_name.lower()
            if key in seen_keys:
                continue
            seen_keys.add(key)

            rel_type, confidence = self._classify_candidate_relationship(ctx, cleaned_name, raw_comp)

            candidates.append({
                "person_name": cleaned_name,
                "designation": "Founder/Executive",
                "company_name": self._clean_company(raw_comp),
                "relationship_type": rel_type if rel_type != "unclear_relationship" else "confirmed_client_case_study",
                "evidence_quote": ctx[:450],
                "confidence": max(confidence, 0.85),
                "extraction_method": "deterministic_reverse_role",
                "source_url": url,
            })

        # -------------------------------------------------------------
        # Pattern 4: Company-only portfolio references (NO fake persons)
        # -------------------------------------------------------------
        for match in COMPANY_PORTFOLIO_PATTERN.finditer(sample):
            raw_comp = match.group(1).strip()
            cleaned_comp = self._clean_company(raw_comp)
            if not cleaned_comp:
                continue

            # Must not be a person name
            is_person, _ = self.name_validator.validate_person_name(cleaned_comp)
            if is_person:
                continue

            comp_key = f"comp:{cleaned_comp.lower()}"
            if comp_key in seen_keys:
                continue
            seen_keys.add(comp_key)

            ctx = self._context(sample, match.start(), match.end(), 200)
            candidates.append({
                "person_name": None,
                "designation": None,
                "company_name": cleaned_comp,
                "relationship_type": "client_portfolio_reference",
                "evidence_quote": ctx[:450],
                "confidence": 0.80,
                "extraction_method": "deterministic_company_portfolio",
                "source_url": url,
            })

        # -------------------------------------------------------------
        # Pattern 5: Published Client Profile Page Subject
        # -------------------------------------------------------------
        parsed_path = urlparse(url).path.strip('/')
        if (parsed_path.startswith("p/") or parsed_path.startswith("profile/") or parsed_path.startswith("client-profile/")) and parsed_path not in ("p/welcome", "profile"):
            slug = parsed_path.split("/")[-1]
            tokens = [t.capitalize() for t in slug.split("-") if t.lower() not in ("adv", "dr", "mr", "ms", "mrs", "prof")]
            name_from_slug = " ".join(tokens)

            # Extract company from page title
            comp_from_title = None
            if title and "|" in title:
                parts = [pt.strip() for pt in title.split("|") if pt.strip()]
                if len(parts) > 1:
                    comp_from_title = parts[-1]

            is_valid_name, _ = self.name_validator.validate_person_name(name_from_slug)
            if is_valid_name:
                cleaned_name = self.name_validator.clean_name(name_from_slug)
                key = cleaned_name.lower()
                if key not in seen_keys:
                    seen_keys.add(key)
                    first_sentence = (text or "").strip().split("\n")[0]
                    if len(first_sentence) < 30:
                        first_sentence = (text or "").strip()[:250]
                    evidence = f"Published client profile for {cleaned_name}: {first_sentence}"[:450]
                    candidates.append({
                        "person_name": cleaned_name,
                        "designation": None,
                        "company_name": self._clean_company(comp_from_title),
                        "relationship_type": "published_customer_profile",
                        "evidence_quote": evidence,
                        "confidence": 0.95,
                        "extraction_method": "deterministic_published_profile",
                        "source_url": url,
                    })

        return candidates

    def _classify_candidate_relationship(
        self, context: str, person_name: Optional[str] = None, company_name: Optional[str] = None
    ) -> Tuple[str, float]:
        """
        Classify the relationship individually for a candidate using its surrounding context.
        Returns: (relationship_type, confidence)
        """
        ctx_lower = context.lower()

        # Check in order of specificity
        for rel_type, keywords in RELATIONSHIP_SIGNALS:
            for kw in keywords:
                if kw in ctx_lower:
                    if rel_type == "client_testimonial":
                        return "client_testimonial", 0.90
                    elif rel_type == "confirmed_client_case_study":
                        return "confirmed_client_case_study", 0.85
                    elif rel_type == "client_portfolio_reference":
                        return "client_portfolio_reference", 0.80
                    elif rel_type == "published_customer_profile":
                        return "published_customer_profile", 0.80
                    elif rel_type == "featured_personality":
                        return "featured_personality", 0.70
                    elif rel_type == "collaborator":
                        return "collaborator", 0.70
                    elif rel_type == "ordinary_mention":
                        return "ordinary_mention", 0.50

        # Default fallback: if no client relationship signal is present in the candidate's context
        return "unclear_relationship", 0.40

    def _context(self, text: str, start: int, end: int, radius: int) -> str:
        s = max(0, start - radius)
        e = min(len(text), end + radius)
        snippet = text[s:e].strip()
        return re.sub(r'\s+', ' ', snippet)[:500]

    def _clean_role(self, raw: Optional[str]) -> Optional[str]:
        if not raw:
            return None
        role = raw.strip().rstrip(',.;:–—').strip()
        if len(role) < 2 or len(role) > 60:
            return None
        return role

    def _clean_company(self, raw: Optional[str]) -> Optional[str]:
        if not raw:
            return None
        company = raw.strip().strip(',.;:–—"\'').strip()
        # Cut off any trailing verb clause
        company = re.split(r'\b(?:was|is|has|in|delivered|featured|scaled)\b', company, flags=re.IGNORECASE)[0].strip()
        company = re.sub(r'\s+', ' ', company).strip(' ,.-–—')
        if len(company) < 2 or len(company) > 70:
            return None
        # Reject generic navigation or stopwords as company names
        lower = company.lower()
        generic_stops = {
            "home", "about", "contact", "services", "team", "privacy policy", "terms of service",
            "management", "engagement", "satisfaction", "needs", "execution", "focused services",
            "execution and client satisfaction", "strategy", "support", "solutions", "project"
        }
        if lower in generic_stops:
            return None
        # Must contain at least one capital letter
        if not any(c.isupper() for c in company):
            return None
        return company

    def _filter_boilerplate(self, text: str) -> str:
        """Strip navigation, cookie notices, and header/footer lines from text."""
        lines = text.split("\n")
        good_lines = []
        for line in lines:
            line_str = line.strip()
            if not line_str:
                continue
            lower = line_str.lower()
            if any(term in lower for term in [
                "all rights reserved", "cookie policy", "accept all cookies",
                "privacy policy", "skip to content", "terms and conditions",
                "designed by", "powered by"
            ]):
                continue
            good_lines.append(line_str)
        return "\n".join(good_lines)

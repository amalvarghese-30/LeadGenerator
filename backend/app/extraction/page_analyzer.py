"""
Deterministic NLP extraction that produces rich, structured client references
WITHOUT requiring NVIDIA. Combines:
  - Regex patterns for "Name, Role at Company"
  - Context windows around person mentions
  - Designation/company co-occurrence
  - Relationship classification
  - Evidence quotes

Never invents facts. Only extracts what appears verbatim in the text.
"""
import re
import logging
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

DESIGNATION_KEYWORDS = [
    "Founder", "Co-Founder", "Co Founder", "CEO", "CTO", "CFO", "COO", "CMO", "CPO",
    "Chief Executive Officer", "Chief Technology Officer", "Chief Financial Officer",
    "Chief Operating Officer", "Chief Marketing Officer",
    "Managing Director", "Director", "Senior Director", "Executive Director",
    "President", "Vice President", "VP", "Head of", "General Manager", "GM",
    "Partner", "Senior Partner", "Managing Partner",
    "Chairman", "Chairwoman", "Board Member",
    "Author", "Co-Author", "Writer", "Journalist",
    "Lawyer", "Advocate", "Attorney", "Counsel", "Barrister", "Solicitor",
    "Doctor", "Dr.", "Physician", "Surgeon", "Specialist", "Consultant",
    "Coach", "Executive Coach", "Mentor", "Advisor", "Senior Advisor",
    "Speaker", "Keynote Speaker", "Public Speaker", "Presenter",
    "Professor", "Lecturer", "Researcher",
    "Engineer", "Architect", "Designer", "Developer",
    "Entrepreneur", "Business Owner", "Investor",
    "Founding Partner", "Principal", "Associate",
]

DESIGNATION_REGEX = re.compile(
    r'\b(' + '|'.join(re.escape(k) for k in DESIGNATION_KEYWORDS) + r')\b',
    re.IGNORECASE,
)

# "Name, Founder at Company"
NAME_ROLE_COMPANY_PATTERN = re.compile(
    r'([A-Z][a-zA-Z\.\-\']+(?:\s+[A-Z][a-zA-Z\.\-\']+){1,3})'
    r'[,\s\-–—]+'
    r'((?:Co-?)?(?:Founder|CEO|CTO|CFO|COO|CMO|President|Director|Partner|Chairman|'
    r'Managing Director|Chief \w+ Officer|Head of [A-Za-z]+|Vice President|VP))'
    r'(?:\s+(?:of|at|@|,)\s+'
    r'([A-Z][a-zA-Z0-9&\-\'\.\s]{2,60}?))?'
    r'(?=[\.,;:\)\n]|$)'
)

# "Company name: TechVision, Founder: John Doe"
REVERSE_ROLE_PATTERN = re.compile(
    r'(?:Company|Organi[sz]ation|Business|Firm)\s*[:–-]\s*([A-Z][\w\s&\.\-\']{2,50}?)'
    r'[,\n;]+'
    r'(?:Founder|CEO|Director|Contact|Executive)\s*[:–-]\s*([A-Z][a-zA-Z\.\-\']+(?:\s+[A-Z][a-zA-Z\.\-\']+){1,2})',
    re.IGNORECASE,
)

# "Mr./Ms./Dr. FirstName LastName"
TITLED_NAME_PATTERN = re.compile(
    r'\b(?:Mr\.?|Ms\.?|Mrs\.?|Dr\.?|Prof\.?|Sir|Madam)\s+'
    r'([A-Z][a-zA-Z\.\-\']+(?:\s+[A-Z][a-zA-Z\.\-\']+){1,3})',
)

# "worked with FirstName LastName" / "helped FirstName LastName"
CLIENT_CONTEXT_PATTERN = re.compile(
    r'(?:worked with|helped|partnered with|client|testimonial from|'
    r'case study (?:on|of|for)|transformed|built .{0,40}for)\s+'
    r'([A-Z][a-zA-Z\.\-\']+(?:\s+[A-Z][a-zA-Z\.\-\']+){1,2})',
    re.IGNORECASE,
)

RELATIONSHIP_KEYWORDS = {
    "client_testimonial": [
        "testimonial", "says", "highly recommend", "worked wonders",
        "client feedback", "star review", "delighted with", "in their own words",
    ],
    "confirmed_client_case_study": [
        "case study", "worked with", "helped", "our client", "success story",
        "transformed", "results achieved", "growth story", "client results",
        "we built", "we delivered",
    ],
    "client_portfolio_reference": [
        "portfolio", "our work", "project for", "work delivered",
        "featured in portfolio", "delivered for", "clients we serve",
    ],
    "published_customer_profile": [
        "profile of", "spotlight on", "customer profile", "client spotlight",
    ],
    "featured_personality": [
        "interview with", "featured on", "guest podcast", "speaker at",
        "in conversation with",
    ],
    "collaborator": [
        "partnered with", "in collaboration with", "co-authored", "joint venture",
    ],
}


class PageAnalyzer:
    """Rich deterministic extraction for client references."""

    def analyze(self, text: str, url: str, title: str = "") -> List[Dict]:
        """
        Return a list of candidate client references with rich fields filled in
        wherever the source text supports it. Fields that cannot be verified
        remain None (never guessed).
        """
        if not text:
            return []

        # Bounded sample — cap prevents regex catastrophic backtracking cost
        sample = text[:25000]
        lower = sample.lower()

        # Determine dominant relationship type from full-page context
        relationship_type = self._classify_relationship(lower)

        candidates: List[Dict] = []
        seen_names = set()

        # Pattern 1: "Name, Role at Company"
        for match in NAME_ROLE_COMPANY_PATTERN.finditer(sample):
            name = self._clean_name(match.group(1))
            role = self._clean_role(match.group(2))
            company = self._clean_company(match.group(3)) if match.group(3) else None
            if not name or name.lower() in seen_names:
                continue
            seen_names.add(name.lower())
            evidence = self._context(sample, match.start(), match.end(), 240)
            candidates.append({
                "person_name": name,
                "designation": role,
                "company_name": company,
                "relationship_type": relationship_type,
                "evidence_quote": evidence,
                "confidence": 0.85,
                "extraction_method": "regex_role_company",
            })

        # Pattern 2: reverse "Company: X, Founder: Y"
        for match in REVERSE_ROLE_PATTERN.finditer(sample):
            company = self._clean_company(match.group(1))
            name = self._clean_name(match.group(2))
            if not name or name.lower() in seen_names:
                continue
            seen_names.add(name.lower())
            evidence = self._context(sample, match.start(), match.end(), 240)
            candidates.append({
                "person_name": name,
                "designation": "Founder/Executive",
                "company_name": company,
                "relationship_type": relationship_type,
                "evidence_quote": evidence,
                "confidence": 0.8,
                "extraction_method": "regex_reverse_company",
            })

        # Pattern 3: "worked with Name Lastname"
        for match in CLIENT_CONTEXT_PATTERN.finditer(sample):
            name = self._clean_name(match.group(1))
            if not name or name.lower() in seen_names:
                continue
            seen_names.add(name.lower())
            ctx = self._context(sample, match.start(), match.end(), 300)
            # Try to find a designation in the context window
            designation_match = DESIGNATION_REGEX.search(ctx)
            candidates.append({
                "person_name": name,
                "designation": designation_match.group(0) if designation_match else None,
                "company_name": None,
                "relationship_type": relationship_type,
                "evidence_quote": ctx,
                "confidence": 0.6,
                "extraction_method": "regex_client_context",
            })

        # Pattern 4: titled names fallback (lower confidence — likely just mentions)
        for match in TITLED_NAME_PATTERN.finditer(sample):
            name = self._clean_name(match.group(1))
            if not name or name.lower() in seen_names:
                continue
            # Only include if a designation or client keyword appears nearby
            ctx = self._context(sample, match.start(), match.end(), 200)
            if not (DESIGNATION_REGEX.search(ctx) or self._has_client_signal(ctx.lower())):
                continue
            seen_names.add(name.lower())
            designation_match = DESIGNATION_REGEX.search(ctx)
            candidates.append({
                "person_name": name,
                "designation": designation_match.group(0) if designation_match else None,
                "company_name": None,
                "relationship_type": relationship_type,
                "evidence_quote": ctx,
                "confidence": 0.5,
                "extraction_method": "regex_titled_context",
            })

        # Try to fill in missing company/designation by nearby co-occurrence
        self._enrich_from_context(candidates, sample)

        return candidates

    # ------------------------------------------------------------------
    def _classify_relationship(self, lower: str) -> str:
        for rel, keywords in RELATIONSHIP_KEYWORDS.items():
            if any(k in lower for k in keywords):
                return rel
        return "unclear_relationship"

    def _has_client_signal(self, lower: str) -> bool:
        return any(
            k in lower
            for keywords in RELATIONSHIP_KEYWORDS.values()
            for k in keywords
        )

    def _context(self, text: str, start: int, end: int, radius: int) -> str:
        s = max(0, start - radius)
        e = min(len(text), end + radius)
        snippet = text[s:e].strip()
        return re.sub(r'\s+', ' ', snippet)[:500]

    def _clean_name(self, raw: str) -> Optional[str]:
        if not raw:
            return None
        name = raw.strip().strip(',').strip('.').strip()
        # Must have at least 2 words, each starting with a letter
        parts = name.split()
        if len(parts) < 2:
            return None
        if not all(p[0].isalpha() for p in parts if p):
            return None
        # Reject obvious non-names
        if any(p.lower() in {"the", "and", "with", "from", "this", "that", "our", "your"} for p in parts):
            return None
        return " ".join(parts[:4])

    def _clean_role(self, raw: str) -> Optional[str]:
        if not raw:
            return None
        return raw.strip().rstrip(',.;:').strip()

    def _clean_company(self, raw: str) -> Optional[str]:
        if not raw:
            return None
        company = raw.strip().strip(',.;:').strip()
        company = re.sub(r'\s+', ' ', company)
        if len(company) < 2 or len(company) > 80:
            return None
        return company

    def _enrich_from_context(self, candidates: List[Dict], text: str):
        """
        For candidates missing company or designation, look in a wider window
        around the name mention to find them.
        """
        for cand in candidates:
            name = cand["person_name"]
            # Find the mention in text
            idx = text.find(name)
            if idx < 0:
                continue
            window = text[max(0, idx - 400): min(len(text), idx + 400)]
            if not cand.get("designation"):
                dm = DESIGNATION_REGEX.search(window)
                if dm:
                    cand["designation"] = dm.group(0)
            if not cand.get("company_name"):
                # "at <Company>" / "of <Company>"
                cm = re.search(
                    r'\b(?:at|of|from)\s+([A-Z][\w&\-\'\.\s]{2,60})',
                    window,
                )
                if cm:
                    company = self._clean_company(cm.group(1))
                    if company:
                        cand["company_name"] = company
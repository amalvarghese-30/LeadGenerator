"""
Person Profile Extractor: Dedicated intelligence extraction pipeline for individual profiles,
biographies, executive bios, and public figures (Workflow B).
Operates independently of B2B client reference classification.
"""
import re
import json
import logging
from typing import Dict, List, Any, Optional, Tuple
from urllib.parse import urlparse
from bs4 import BeautifulSoup

from app.discovery.social_discovery import SocialDiscovery
from app.enrichment.public_email_extractor import PublicEmailExtractor
from app.enrichment.public_phone_extractor import PublicPhoneExtractor

logger = logging.getLogger(__name__)

# Suffixes often present in titles or H1s on wiki or profile sites
TITLE_SUFFIX_REGEX = re.compile(
    r'\s*(?:[-–—|•:]\s*(?:wikipoint|wikipedia|wiki|biography|profile|executive bio|crunchbase|linkedin|speaker|author|about us|official website)).*$',
    re.IGNORECASE
)

# Generic non-person words that should never be accepted as person names
INVALID_NAME_WORDS = {
    "about", "contact", "home", "privacy", "policy", "terms", "service", "services",
    "careers", "company", "team", "features", "pricing", "login", "register",
    "signup", "welcome", "category", "tag", "archive", "blog", "news", "articles",
    "wiki", "wikipoint", "wikipedia", "search", "faq", "help", "support", "dashboard"
}

# Designation extraction patterns from bio sentences
DESIGNATION_PATTERNS = [
    re.compile(r'\b(?:is|serves as|works as)\s+(?:an?|the)\s+([A-Z][a-zA-Z\s&/\-]+?(?:founder|co-founder|ceo|chief executive officer|managing director|director|president|vice president|chairman|chairwoman|partner|principal|investor|author|journalist|editor|consultant|specialist|strategist|engineer|architect|manager|producer|artist|speaker))\b', re.IGNORECASE),
    re.compile(r'\b([A-Z][a-zA-Z\s&/\-]+?(?:Founder|Co-Founder|CEO|Chief Executive Officer|Managing Director|Director|President|Vice President|Chairman|Partner|Author|Strategist|Consultant))\s+(?:at|of|with)\b'),
]

# Company extraction patterns from bio sentences
AFFILIATION_PATTERNS = [
    re.compile(r'\b(?:at|of|with|for)\s+([A-Z][a-zA-Z0-9\s&.,\-]+?)(?:,|\.|\s+in|\s+since|\s+where|\s+based|\s+who)', re.ASCII),
    re.compile(r'\b(?:founded|co-founded|started|leads|heads)\s+([A-Z][a-zA-Z0-9\s&.,\-]+?)(?:,|\.|\s+in|\s+since|\s+to)', re.ASCII),
]


class PersonProfileExtractor:
    def __init__(self):
        self.social_discovery = SocialDiscovery()
        self.email_extractor = PublicEmailExtractor()
        self.phone_extractor = PublicPhoneExtractor()

    def is_person_profile_page(self, page_data: Dict[str, Any]) -> Tuple[bool, float, str]:
        """
        Determines if a page is a Person Profile or Wiki Biography.
        Returns: (is_profile, confidence, detection_reason)
        """
        url = page_data.get("url") or ""
        title = page_data.get("page_title") or page_data.get("title") or ""
        h1 = page_data.get("h1") or ""
        main_text = page_data.get("main_text") or ""
        schema_persons = page_data.get("schema_persons") or []

        score = 0.0
        reasons = []

        # 1. Schema.org Person presence
        if schema_persons and any(p.get("name") for p in schema_persons):
            score += 0.45
            reasons.append("schema_org_person_detected")

        # 2. URL path indicators
        parsed_url = urlparse(url)
        path_lower = parsed_url.path.lower()
        if any(seg in path_lower for seg in ["/wiki/", "/person/", "/profile/", "/people/", "/author/", "/speaker/", "/team/", "/leadership/"]):
            score += 0.35
            reasons.append(f"profile_url_path({parsed_url.path})")

        # 3. Clean Name in Title/H1
        clean_h1 = self._clean_name_candidate(h1)
        if clean_h1 and self._is_likely_person_name(clean_h1):
            score += 0.25
            reasons.append(f"person_name_h1({clean_h1})")
        elif title:
            clean_title = self._clean_name_candidate(title)
            if clean_title and self._is_likely_person_name(clean_title):
                score += 0.20
                reasons.append(f"person_name_title({clean_title})")

        # 4. Biographical opening in text
        first_paragraph = main_text.strip()[:400]
        if re.search(r'\b(?:is an?|was an?|born in|born on|serves as|is known for|is the founder|is a professional)\b', first_paragraph, re.IGNORECASE):
            score += 0.20
            reasons.append("biographical_syntax_opening")

        is_profile = score >= 0.40
        reason_str = ", ".join(reasons) if reasons else "no_strong_person_signals"
        return is_profile, min(1.0, score), reason_str

    def extract_profile(self, page_data: Dict[str, Any], raw_html: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Extracts comprehensive identity, contact, social, and biographical information
        for an individual from the page data and optional raw HTML.
        """
        url = page_data.get("url") or ""
        title = page_data.get("page_title") or page_data.get("title") or ""
        h1 = page_data.get("h1") or ""
        main_text = page_data.get("main_text") or ""
        schema_persons = page_data.get("schema_persons") or []

        soup = BeautifulSoup(raw_html, "html.parser") if raw_html else None

        # 1. Identity Resolution (Name)
        person_name = None
        name_source = None

        # Try Schema.org first
        for sp in schema_persons:
            cand = sp.get("name")
            if cand and self._is_likely_person_name(cand):
                person_name = cand.strip()
                name_source = "schema_org"
                break

        # Try MediaWiki / HTML Infobox header
        if not person_name and soup:
            infobox = soup.find(["table", "div"], class_=lambda c: c and any(k in str(c).lower() for k in ["infobox", "vcard", "profile-box", "biography"]))
            if infobox:
                # Infobox title / above header
                above = infobox.find(["th", "caption", "div"], class_=lambda c: c and any(k in str(c).lower() for k in ["infobox-above", "fn", "infobox-title", "header"]))
                if above:
                    cand = self._clean_name_candidate(above.get_text(strip=True))
                    if cand and self._is_likely_person_name(cand):
                        person_name = cand
                        name_source = "infobox_header"

        # Try H1
        if not person_name and h1:
            cand = self._clean_name_candidate(h1)
            if cand and self._is_likely_person_name(cand):
                person_name = cand
                name_source = "h1_heading"

        # Try Title
        if not person_name and title:
            cand = self._clean_name_candidate(title)
            if cand and self._is_likely_person_name(cand):
                person_name = cand
                name_source = "page_title"

        # Try URL slug if wiki or profile URL
        if not person_name and url:
            path_slug = urlparse(url).path.rstrip("/").split("/")[-1]
            slug_name = path_slug.replace("_", " ").replace("-", " ")
            if self._is_likely_person_name(slug_name):
                person_name = slug_name.title()
                name_source = "url_slug"

        if not person_name:
            return None

        # 2. Infobox structured data extraction if HTML available
        infobox_data = self._extract_infobox_fields(soup) if soup else {}

        # 3. Designation / Role
        designation = None
        designation_source = None

        if infobox_data.get("occupation"):
            designation = infobox_data["occupation"]
            designation_source = "infobox_occupation"
        elif infobox_data.get("designation") or infobox_data.get("title") or infobox_data.get("role"):
            designation = infobox_data.get("designation") or infobox_data.get("title") or infobox_data.get("role")
            designation_source = "infobox_role"
        elif schema_persons and schema_persons[0].get("job_title"):
            designation = schema_persons[0]["job_title"]
            designation_source = "schema_job_title"
        else:
            # Check bio text
            for pat in DESIGNATION_PATTERNS:
                m = pat.search(main_text[:1000])
                if m:
                    designation = m.group(1).strip()
                    designation_source = "bio_text_pattern"
                    break

        # 4. Company / Affiliation
        company_name = None
        company_source = None

        if infobox_data.get("organization") or infobox_data.get("company") or infobox_data.get("employer"):
            company_name = infobox_data.get("organization") or infobox_data.get("company") or infobox_data.get("employer")
            company_source = "infobox_affiliation"
        elif schema_persons and schema_persons[0].get("works_for"):
            company_name = schema_persons[0]["works_for"]
            company_source = "schema_works_for"
        else:
            for pat in AFFILIATION_PATTERNS:
                m = pat.search(main_text[:1200])
                if m:
                    c_cand = m.group(1).strip().rstrip(".,;:")
                    if len(c_cand) > 2 and not any(w in c_cand.lower() for w in ["school", "college", "university", "india", "delhi", "mumbai"]):
                        company_name = c_cand
                        company_source = "bio_text_pattern"
                        break

        # 5. Location
        location = None
        if infobox_data.get("residence") or infobox_data.get("location") or infobox_data.get("born"):
            location = infobox_data.get("residence") or infobox_data.get("location") or infobox_data.get("born")
        elif schema_persons and (schema_persons[0].get("address") or schema_persons[0].get("homeLocation")):
            loc_val = schema_persons[0].get("address") or schema_persons[0].get("homeLocation")
            location = loc_val if isinstance(loc_val, str) else json.dumps(loc_val)

        # 6. Clean Bio Summary
        bio_summary = self._generate_bio_summary(main_text, person_name)

        # 7. Social Profiles
        social_profiles = list(page_data.get("social_profiles") or [])
        if raw_html:
            html_socials = self.social_discovery.discover_from_html(raw_html, url)
            existing_urls = {sp.get("url") for sp in social_profiles if sp.get("url")}
            for sp in html_socials:
                if sp.get("url") and sp["url"] not in existing_urls:
                    existing_urls.add(sp["url"])
                    social_profiles.append(sp)

        # Check infobox website/social links
        if infobox_data.get("website"):
            wb_url = infobox_data["website"]
            cl = self.social_discovery._classify_url(wb_url)
            if cl and cl["url"] not in {sp.get("url") for sp in social_profiles}:
                social_profiles.append({
                    **cl,
                    "source_url": url,
                    "extraction_method": "infobox_website",
                    "verification_status": "likely_official",
                    "confidence": 0.95,
                })

        # 8. Public Emails & Phones
        public_emails = list(page_data.get("public_emails") or [])
        public_phones = list(page_data.get("public_phones") or [])

        # 9. Associated Websites (personal website, official blog, book sites)
        associated_websites = self._extract_associated_websites(soup, infobox_data, url)

        # 10. Calculate Explainable Confidence
        conf_score, conf_reasons = self._calculate_confidence(
            person_name=person_name,
            designation=designation,
            company_name=company_name,
            bio_summary=bio_summary,
            social_profiles=social_profiles,
            public_emails=public_emails,
            public_phones=public_phones,
            name_source=name_source,
        )

        return {
            "person_name": person_name,
            "designation": designation or "Professional / Public Figure",
            "company_name": company_name,
            "location": location,
            "bio_summary": bio_summary,
            "social_profiles": social_profiles,
            "public_emails": public_emails,
            "public_phones": public_phones,
            "associated_websites": associated_websites,
            "source_url": url,
            "name_source": name_source,
            "designation_source": designation_source,
            "company_source": company_source,
            "confidence_score": conf_score,
            "confidence_reasons": conf_reasons,
            "page_category": "person_profile",
        }

    def _clean_name_candidate(self, text: Optional[str]) -> Optional[str]:
        if not text:
            return None
        cleaned = TITLE_SUFFIX_REGEX.sub("", text).strip()
        cleaned = re.sub(r'\[[0-9]+\]', '', cleaned)  # remove wiki reference brackets
        cleaned = cleaned.replace("Category:", "").replace("User:", "")
        return cleaned.strip() or None

    def _is_likely_person_name(self, text: str) -> bool:
        if not text:
            return False
        tokens = text.split()
        if len(tokens) < 2 or len(tokens) > 5:
            return False
        if any(t.lower() in INVALID_NAME_WORDS for t in tokens):
            return False
        if any(char in text for char in ["@", "/", "\\", "<", ">", "{", "}", "=", "$", "%", "*", "_"]):
            return False
        # Must contain alphabetical letters
        if not re.search(r'[A-Za-z]', text):
            return False
        # Each word should start with a capital letter or standard prefix (e.g. von, de, bin)
        valid_capitals = sum(1 for t in tokens if t[0].isupper() or t.lower() in ("de", "von", "van", "bin", "al", "da"))
        return valid_capitals >= len(tokens) - 1

    def _extract_infobox_fields(self, soup: BeautifulSoup) -> Dict[str, str]:
        fields = {}
        infobox = soup.find(["table", "div"], class_=lambda c: c and any(k in str(c).lower() for k in ["infobox", "vcard", "profile-box", "biography"]))
        if not infobox:
            return fields

        for tr in infobox.find_all("tr"):
            th = tr.find(["th", "td"], class_=lambda c: c and "label" in str(c).lower()) or tr.find("th")
            td = tr.find(["td", "div"], class_=lambda c: c and "data" in str(c).lower()) or tr.find("td")
            if th and td:
                lbl = th.get_text(separator=" ", strip=True).lower().replace(":", "")
                val = td.get_text(separator=" ", strip=True)
                val_clean = re.sub(r'\[[0-9]+\]', '', val).strip()

                # Also check links inside td
                a_link = td.find("a", href=True)
                href = a_link["href"].strip() if a_link else None

                if any(k in lbl for k in ["occupation", "profession", "designation"]):
                    fields["occupation"] = val_clean
                elif any(k in lbl for k in ["organization", "company", "employer", "firm"]):
                    fields["organization"] = val_clean
                elif any(k in lbl for k in ["role", "title", "position"]):
                    fields["role"] = val_clean
                elif any(k in lbl for k in ["residence", "location", "based"]):
                    fields["residence"] = val_clean
                elif any(k in lbl for k in ["born", "birth"]):
                    fields["born"] = val_clean
                elif any(k in lbl for k in ["website", "official site", "url"]):
                    fields["website"] = href or val_clean

        return fields

    def _generate_bio_summary(self, main_text: str, person_name: str) -> str:
        if not main_text:
            return ""

        # Remove MediaWiki citations like [1], [2], [edit], [citation needed]
        clean_text = re.sub(r'\[(?:[0-9]+|edit|citation needed)\]', '', main_text)
        paragraphs = [p.strip() for p in clean_text.split("\n") if p.strip()]

        for p in paragraphs:
            # Paragraph mentioning the person's name or key tokens
            first_name = person_name.split()[0]
            if person_name.lower() in p.lower() or first_name.lower() in p.lower():
                sentences = re.split(r'(?<=[.!?])\s+', p)
                short_summary = " ".join(sentences[:3]).strip()
                if len(short_summary) > 40:
                    return short_summary[:600]

        # Fallback to first non-empty paragraph
        if paragraphs:
            sentences = re.split(r'(?<=[.!?])\s+', paragraphs[0])
            return " ".join(sentences[:2]).strip()[:500]

        return ""

    def _extract_associated_websites(self, soup: Optional[BeautifulSoup], infobox: Dict[str, str], page_url: str) -> List[Dict[str, str]]:
        websites = []
        seen = set()

        # Infobox website
        wb = infobox.get("website")
        if wb and wb.startswith("http") and wb not in seen:
            seen.add(wb)
            websites.append({"url": wb, "label": "Official Website", "source": "infobox"})

        if not soup:
            return websites

        # Check external links section
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            if not href.startswith("http"):
                continue
            text = a.get_text(strip=True).lower()
            if any(k in text for k in ["official website", "personal website", "portfolio", "blog", "foundation"]):
                if href not in seen:
                    seen.add(href)
                    websites.append({
                        "url": href,
                        "label": a.get_text(strip=True) or "Official / Personal Link",
                        "source": "page_external_links"
                    })

        return websites

    def _calculate_confidence(
        self,
        person_name: str,
        designation: Optional[str],
        company_name: Optional[str],
        bio_summary: str,
        social_profiles: List[Dict],
        public_emails: List[str],
        public_phones: List[str],
        name_source: Optional[str],
    ) -> Tuple[float, List[str]]:
        score = 0.0
        reasons = []

        if person_name:
            score += 0.35
            reasons.append(f"High confidence person identity verified via {name_source}")

        if designation and designation != "Professional / Public Figure":
            score += 0.15
            reasons.append(f"Professional designation identified: {designation}")

        if company_name:
            score += 0.15
            reasons.append(f"Affiliation identified: {company_name}")

        if bio_summary and len(bio_summary) > 50:
            score += 0.15
            reasons.append("Structured biographical summary extracted")

        if social_profiles:
            score += 0.15
            platforms = ", ".join(list(dict.fromkeys(sp.get("platform") for sp in social_profiles if sp.get("platform"))))
            reasons.append(f"Discovered {len(social_profiles)} social media profile(s) ({platforms})")

        if public_emails or public_phones:
            score += 0.05
            reasons.append("Public contact channel(s) detected")

        final_score = min(0.99, max(0.40, round(score, 2)))
        return final_score, reasons

"""
People Discovery Service.
Discovers and verifies business leaders, founders, directors, CEOs, and executives
associated with client companies through official website subpages, JSON-LD schemas,
and permitted public search corroboration.
Features deterministic identity matching and multi-signal disambiguation.
"""
import re
import json
import logging
from typing import List, Dict, Any, Optional, Set, Tuple
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup, Tag

from app.discovery.ddgs_search import DDGSSearch
from app.discovery.social_discovery import SocialDiscovery
from app.utils.deduplication import normalize_string, normalize_linkedin_url
from app.enrichment.public_email_extractor import EMAIL_REGEX

logger = logging.getLogger(__name__)

# Core leadership and executive titles
EXECUTIVE_TITLES = [
    "founder", "co-founder", "co founder", "chief executive officer", "ceo",
    "managing director", "md", "director", "owner", "partner", "president",
    "vice president", "vp", "chief technology officer", "cto",
    "chief operating officer", "coo", "chief marketing officer", "cmo",
    "chief financial officer", "cfo", "head of marketing", "head of sales",
    "head of business development", "principal", "general manager", "chairman",
    "chairperson", "executive director", "managing partner",
]

# Words that indicate text is NOT a person's name
NON_NAME_WORDS = {
    "about", "contact", "home", "privacy", "policy", "terms", "service", "services",
    "careers", "company", "team", "features", "pricing", "login", "register",
    "signup", "welcome", "category", "tag", "archive", "blog", "news", "articles",
    "wiki", "search", "faq", "help", "support", "dashboard", "overview", "portfolio",
    "projects", "clients", "reviews", "read more", "learn more", "view profile",
    "our story", "leadership", "management", "board", "advisors", "directors",
    "executives", "founders", "members", "staff", "meet", "who we are", "office",
    "page", "not", "found", "error", "404", "denied", "access", "forbidden", "unauthorized",
    "bad", "request", "server", "timeout", "gateway", "moved", "redirect", "maintenance",
    "under", "construction", "loading", "untitled", "document", "oops", "sorry",
    "something", "went", "wrong", "blank", "default", "403", "500", "502", "503",
}


class PeopleDiscoveryService:
    def __init__(self, search_max_results: int = 5):
        self.searcher = DDGSSearch(max_results=search_max_results)
        self.social_discovery = SocialDiscovery()

    def discover_from_html(
        self,
        html: str,
        page_url: str,
        company_name: str,
        company_domain: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Extract professional people (founders, directors, leadership) directly
        from official webpage HTML and JSON-LD schemas.
        """
        if not html:
            return []

        soup = BeautifulSoup(html[:150000], "html.parser")
        discovered: List[Dict[str, Any]] = []
        seen_names: Set[str] = set()

        # 1. JSON-LD Schema.org extraction (Person, founder, alumni, employee)
        json_ld_people = self._extract_from_json_ld(soup, page_url, company_name)
        for p in json_ld_people:
            n_norm = normalize_string(p["full_name"])
            if n_norm and n_norm not in seen_names:
                seen_names.add(n_norm)
                discovered.append(p)

        # 2. Team & Leadership Card Components in DOM
        card_selectors = [
            ".team-member", ".member-card", ".leadership-card", ".bio-card",
            ".executive-card", ".profile-card", ".person-card", ".team-card",
            ".speaker-card", ".board-member", ".director-card", ".founder-card",
            ".team-item", ".our-team-item", ".leadership-item",
        ]
        cards = soup.select(", ".join(card_selectors))
        for card in cards:
            parsed_card = self._parse_person_card(card, page_url, company_name)
            if parsed_card:
                n_norm = normalize_string(parsed_card["full_name"])
                if n_norm and n_norm not in seen_names:
                    seen_names.add(n_norm)
                    discovered.append(parsed_card)

        # 3. Headings with Executive Titles in Close Vicinity
        if len(discovered) < 3:
            vicinity_people = self._extract_from_heading_vicinity(soup, page_url, company_name)
            for p in vicinity_people:
                n_norm = normalize_string(p["full_name"])
                if n_norm and n_norm not in seen_names:
                    seen_names.add(n_norm)
                    discovered.append(p)

        return discovered

    def discover_from_search(
        self,
        company_name: str,
        company_domain: Optional[str] = None,
        max_queries: int = 3,
    ) -> List[Dict[str, Any]]:
        """
        Permitted public search queries to discover company executives and their LinkedIn profiles.
        Applies strict deterministic corroboration to prevent assigning wrong people.
        """
        clean_comp = re.sub(r'[^a-zA-Z0-9\s]', '', company_name).strip()
        if not clean_comp or len(clean_comp) < 3:
            return []

        queries = [
            f'"{clean_comp}" founder OR co-founder OR CEO',
            f'"{clean_comp}" director OR "managing director"',
            f'site:linkedin.com/in/ "{clean_comp}"',
        ][:max_queries]

        results: List[Dict[str, Any]] = []
        seen_names: Set[str] = set()

        for q in queries:
            try:
                search_items = self.searcher.search(q, region="wt-wt")
                for item in search_items:
                    parsed = self._parse_search_result(item, clean_comp, company_domain)
                    if parsed:
                        n_norm = normalize_string(parsed["full_name"])
                        if n_norm and n_norm not in seen_names:
                            seen_names.add(n_norm)
                            results.append(parsed)
            except Exception as e:
                logger.warning("[PEOPLE_DISCOVERY] Search query '%s' failed gracefully: %s", q, e)

        return results

    def _extract_from_json_ld(
        self,
        soup: BeautifulSoup,
        page_url: str,
        company_name: str,
    ) -> List[Dict[str, Any]]:
        """Extract people from JSON-LD schema objects (Person, founder, employee)."""
        people = []
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string or script.get_text() or "{}")
                items = data if isinstance(data, list) else [data]
                for obj in items:
                    if not isinstance(obj, dict):
                        continue

                    # Direct Person object
                    otype = str(obj.get("@type", "")).lower()
                    if "person" in otype and obj.get("name"):
                        p = self._build_person_from_dict(obj, page_url, company_name, "json_ld_person")
                        if p:
                            people.append(p)

                    # Nested founders or employees on Organization / LocalBusiness
                    for role_key in ("founder", "founders", "employee", "employees", "alumni", "member", "members"):
                        sub = obj.get(role_key)
                        sub_items = sub if isinstance(sub, list) else ([sub] if sub else [])
                        for s_item in sub_items:
                            if isinstance(s_item, dict) and s_item.get("name"):
                                p = self._build_person_from_dict(
                                    s_item, page_url, company_name, f"json_ld_{role_key}", default_role=role_key.capitalize()
                                )
                                if p:
                                    people.append(p)
            except Exception:
                continue
        return people

    def _build_person_from_dict(
        self,
        obj: Dict[str, Any],
        page_url: str,
        company_name: str,
        source_type: str,
        default_role: str = "Executive",
    ) -> Optional[Dict[str, Any]]:
        raw_name = str(obj.get("name") or "").strip()
        if not self._is_valid_person_name(raw_name):
            return None

        job_title = obj.get("jobTitle") or obj.get("roleName") or default_role
        same_as = obj.get("sameAs") or []
        same_as_list = same_as if isinstance(same_as, list) else [same_as]

        linkedin_url = None
        for s in same_as_list:
            if isinstance(s, str) and "linkedin.com/in/" in s.lower():
                linkedin_url = s.strip()
                break

        return {
            "full_name": raw_name,
            "designation": str(job_title).strip(),
            "company_name": company_name,
            "linkedin_url": linkedin_url,
            "professional_urls": {"linkedin": linkedin_url} if linkedin_url else {},
            "bio_summary": obj.get("description"),
            "public_emails": [obj["email"]] if obj.get("email") else [],
            "public_phones": [obj["telephone"]] if obj.get("telephone") else [],
            "evidence_quote": f"Schema.org markup: {raw_name} ({job_title}) at {company_name}",
            "source_url": page_url,
            "confidence": 0.90 if linkedin_url else 0.85,
            "verification_status": "published",
            "discovery_source": "json_ld",
        }

    def _parse_person_card(
        self,
        card: Tag,
        page_url: str,
        company_name: str,
    ) -> Optional[Dict[str, Any]]:
        """Parse structured DOM member/person card."""
        # Find heading / name
        h = card.find(["h3", "h4", "h5", "h2", "strong"])
        if not h:
            return None
        raw_name = h.get_text(strip=True)
        if not self._is_valid_person_name(raw_name):
            return None

        # Find role / designation
        p_role = card.find(class_=lambda c: c and any(k in str(c).lower() for k in ["role", "title", "designation", "pos", "subtitle"]))
        if not p_role:
            # Check paragraph siblings
            for sibling in h.find_next_siblings(["p", "span", "div"]):
                stext = sibling.get_text(strip=True)
                if any(t in stext.lower() for t in EXECUTIVE_TITLES):
                    p_role = sibling
                    break

        designation = p_role.get_text(strip=True) if p_role else "Team Member"

        # Check if designation is one of the prioritized executive titles
        is_priority_role = any(t in designation.lower() for t in EXECUTIVE_TITLES)
        if not is_priority_role and designation == "Team Member":
            return None

        # Find LinkedIn profile link inside card
        linkedin_url = None
        card_socials = {}
        for a in card.find_all("a", href=True):
            href = a["href"].strip()
            if "linkedin.com/in/" in href.lower():
                linkedin_url = href
                card_socials["linkedin"] = href
            elif any(plat in href.lower() for plat in ["twitter.com", "x.com", "github.com"]):
                for plat in ["twitter", "github"]:
                    if plat in href.lower():
                        card_socials[plat] = href

        # Extract direct email or phone if printed inside the card
        card_text = card.get_text(separator=" ", strip=True)
        emails = EMAIL_REGEX.findall(card_text)
        clean_emails = [em.lower().strip(".") for em in emails if not any(d in em.lower() for d in ["example.com", "w3.org"])]

        return {
            "full_name": raw_name,
            "designation": designation,
            "company_name": company_name,
            "linkedin_url": linkedin_url,
            "professional_urls": card_socials,
            "public_emails": clean_emails,
            "public_phones": [],
            "evidence_quote": f"Published team profile: {raw_name} — {designation} at {company_name}",
            "source_url": page_url,
            "confidence": 0.90 if linkedin_url else 0.80,
            "verification_status": "published",
            "discovery_source": "website_team_page",
        }

    def _extract_from_heading_vicinity(
        self,
        soup: BeautifulSoup,
        page_url: str,
        company_name: str,
    ) -> List[Dict[str, Any]]:
        """Fallback for unstructured team sections where names and titles are in adjacent tags."""
        people = []
        for h in soup.find_all(["h3", "h4"]):
            name_cand = h.get_text(strip=True)
            if not self._is_valid_person_name(name_cand):
                continue

            nxt = h.find_next_sibling(["p", "span", "div"])
            if nxt:
                role_cand = nxt.get_text(strip=True)
                if any(t in role_cand.lower() for t in EXECUTIVE_TITLES):
                    people.append({
                        "full_name": name_cand,
                        "designation": role_cand,
                        "company_name": company_name,
                        "linkedin_url": None,
                        "professional_urls": {},
                        "public_emails": [],
                        "public_phones": [],
                        "evidence_quote": f"Published leadership section: {name_cand} ({role_cand})",
                        "source_url": page_url,
                        "confidence": 0.75,
                        "verification_status": "published",
                        "discovery_source": "website_leadership_section",
                    })
        return people

    def _parse_search_result(
        self,
        item: Dict[str, Any],
        company_name: str,
        company_domain: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Deterministic identity matching from public search result.
        Requires corroborated evidence linking the person to this specific company.
        """
        title = item.get("title", "")
        snippet = item.get("snippet", "")
        url = item.get("url", "")
        combined = f"{title} — {snippet}"

        # 1. Company Corroboration Check
        comp_lower = company_name.lower()
        dom_root = (company_domain or "").lower().replace("www.", "").split(".")[0]
        comp_matched = comp_lower in combined.lower() or (len(dom_root) >= 4 and dom_root in combined.lower())
        if not comp_matched:
            return None

        # 2. LinkedIn in/ profile extraction
        is_linkedin = "linkedin.com/in/" in url.lower()
        person_name = None
        designation = None

        if is_linkedin:
            # LinkedIn titles are usually "First Last - Title - Company | LinkedIn"
            parts = re.split(r'[-–—|•]', title)
            if parts and len(parts) >= 2:
                cand_name = parts[0].strip()
                if self._is_valid_person_name(cand_name):
                    person_name = cand_name
                    # Look for role in next segment
                    cand_role = parts[1].strip()
                    if any(t in cand_role.lower() for t in EXECUTIVE_TITLES):
                        designation = cand_role
                    else:
                        designation = "Leadership"
        else:
            # Extract pattern: "John Doe, CEO at Acme Corp" or "Acme Corp Founder John Doe"
            m = re.search(r'\b([A-Z][a-z]+ [A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s*,\s*([A-Za-z\s]+?(?:Founder|Co-Founder|CEO|Director|Managing Director|President))\b', combined)
            if m:
                cand_name, cand_role = m.group(1).strip(), m.group(2).strip()
                if self._is_valid_person_name(cand_name):
                    person_name = cand_name
                    designation = cand_role

        if not person_name:
            return None

        linkedin_url = url if is_linkedin else None

        return {
            "full_name": person_name,
            "designation": designation or "Executive",
            "company_name": company_name,
            "linkedin_url": linkedin_url,
            "professional_urls": {"linkedin": linkedin_url} if linkedin_url else {},
            "public_emails": [],
            "public_phones": [],
            "evidence_quote": f"Public search corroboration: {title} ({snippet[:120]}...)",
            "source_url": url,
            "confidence": 0.85 if is_linkedin else 0.70,
            "verification_status": "source_verified" if is_linkedin else "needs_review",
            "discovery_source": "public_search_corroborated",
        }

    def _is_valid_person_name(self, name: str) -> bool:
        """Strict person name validator: filters UI strings, company names, slogans."""
        if not name:
            return False
        clean = re.sub(r'[^a-zA-Z\s\.\-]', '', name).strip()
        words = clean.split()
        if len(words) < 2 or len(words) > 4:
            return False
        if any(w.lower() in NON_NAME_WORDS for w in words):
            return False
        # Each word must start with an uppercase letter
        if not all(w[0].isupper() for w in words if len(w) > 1):
            return False
        return True

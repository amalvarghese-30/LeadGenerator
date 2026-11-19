"""
Dedicated Portfolio DOM Extractor.
Extracts client companies, external website links, descriptions, images,
and relationship evidence directly from HTML card structures and portfolio grids.
"""
import re
import logging
from typing import Dict, List, Any, Optional, Set, Tuple
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup, Tag

from app.utils.url_utils import extract_domain

logger = logging.getLogger(__name__)

# Social & excluded domains that should NEVER be treated as a client's official website
EXCLUDED_OUTBOUND_DOMAINS = {
    "whatsapp.com", "wa.me", "facebook.com", "instagram.com", "twitter.com",
    "x.com", "linkedin.com", "youtube.com", "pinterest.com", "github.com",
    "t.me", "telegram.org", "google.com", "fonts.googleapis.com", "goo.gl",
    "maps.google.com", "schema.org", "w3.org", "cloudflare.com", "wordpress.org",
    "wix.com", "shopify.com", "squarespace.com", "webflow.com",
}

# Generic button / action labels to reject as candidate names
GENERIC_ACTION_LABELS = {
    "visit site", "visit website", "view project", "view website", "read more",
    "case study", "full story", "view case study", "learn more", "our work",
    "start your project", "get a quote", "contact us", "whatsapp us", "explore",
    "live site", "launch site", "see project", "details", "website",
}


class PortfolioExtractor:
    def __init__(self):
        pass

    def extract_portfolio_candidates(
        self,
        html: str,
        page_url: str,
        page_title: str = "",
        provider_domain: Optional[str] = None,
        provider_brand: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Extract structured client portfolio candidates from webpage HTML DOM.
        Associates company names and external website links strictly within card boundaries.
        """
        if not html:
            return []

        soup = BeautifulSoup(html, "html.parser")
        prov_dom = (provider_domain or extract_domain(page_url) or "").lower().replace("www.", "")
        candidates: List[Dict[str, Any]] = []
        seen_keys: Set[str] = set()

        # 1. Target known portfolio grid containers and card classes
        card_class_patterns = [
            "client-card", "portfolio-card", "project-card", "project-item",
            "work-item", "case-study-card", "portfolio-item", "client-item",
            "clients-item", "partner-card", "brand-card", "client-box",
            "project-box", "project-entry", "card-portfolio",
        ]

        cards: List[Tag] = []
        for pat in card_class_patterns:
            matched = soup.find_all(class_=lambda c: c and pat in str(c).lower())
            for m in matched:
                if isinstance(m, Tag) and m not in cards:
                    cards.append(m)

        # Also inspect direct children of known grid containers
        grid_class_patterns = [
            "clients-grid", "portfolio-grid", "projects-grid", "portfolio-list",
            "work-grid", "clients-list", "case-studies-grid", "our-clients-grid",
            "logo-grid", "logos-grid", "client-logos", "partners-clients",
        ]
        for g_pat in grid_class_patterns:
            grids = soup.find_all(class_=lambda c: c and g_pat in str(c).lower())
            for g in grids:
                if isinstance(g, Tag):
                    for child in g.find_all(["div", "article", "li"], recursive=False):
                        if child not in cards:
                            cards.append(child)

        # Also check <article> and <figure> elements inside portfolio sections
        portfolio_sections = soup.find_all(["section", "div"], id=lambda i: i and any(k in str(i).lower() for k in ["portfolio", "clients", "our-work", "projects", "case-studies"]))
        for sec in portfolio_sections:
            if isinstance(sec, Tag):
                for item in sec.find_all(["article", "figure"]):
                    if item not in cards:
                        cards.append(item)

        # Process each card
        for card in cards:
            cand = self._parse_card(card, page_url, prov_dom, provider_brand)
            if cand:
                dedup_key = f"{cand['candidate_name'].lower()}::{cand.get('client_website_url') or ''}"
                if dedup_key not in seen_keys:
                    seen_keys.add(dedup_key)
                    candidates.append(cand)

        # 2. Secondary Strategy: If card count is low (< 3), search for logo grids or linked logo items
        if len(candidates) < 3:
            logo_wraps = soup.find_all(class_=lambda c: c and any(k in str(c).lower() for k in ["client-logo", "logo-wrap", "partner-logo", "brand-logo", "logo-item", "logo-box"]))
            for lw in logo_wraps:
                if isinstance(lw, Tag):
                    cand = self._parse_logo_wrap(lw, page_url, prov_dom, provider_brand)
                    if cand:
                        dedup_key = f"{cand['candidate_name'].lower()}::{cand.get('client_website_url') or ''}"
                        if dedup_key not in seen_keys:
                            seen_keys.add(dedup_key)
                            candidates.append(cand)

        # 3. Tertiary Strategy: Case studies breakdown list (e.g. "Deeper Dives / Read the Full Case Studies")
        case_study_cands = self._extract_case_study_entries(soup, page_url, prov_dom, provider_brand)
        for cs in case_study_cands:
            dedup_key = f"{cs['candidate_name'].lower()}::{cs.get('client_website_url') or ''}"
            if dedup_key not in seen_keys:
                seen_keys.add(dedup_key)
                candidates.append(cs)

        # 4. Quaternary Strategy: Generic card containers with heading + external CTA link (e.g. "Visit Site →")
        if len(candidates) < 2:
            cta_words = ["visit site", "live site", "view website", "view project", "launch", "live demo", "website", "visit"]
            for a in soup.find_all("a", href=True):
                a_text = (a.get_text(strip=True) + " " + a.get("title", "") + " " + a.get("aria-label", "")).lower()
                href = a["href"].strip()
                if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
                    continue
                is_cta = any(w in a_text for w in cta_words) or a.get("target") == "_blank"
                if is_cta:
                    parent_card = a.find_parent(["article", "li", "div"])
                    if parent_card and isinstance(parent_card, Tag):
                        cand = self._parse_card(parent_card, page_url, prov_dom, provider_brand)
                        if cand:
                            dedup_key = f"{cand['candidate_name'].lower()}::{cand.get('client_website_url') or ''}"
                            if dedup_key not in seen_keys:
                                seen_keys.add(dedup_key)
                                candidates.append(cand)

        logger.info("[PORTFOLIO_DOM] Extracted %d portfolio candidates from %s", len(candidates), page_url)
        return candidates

    def _parse_card(
        self,
        card: Tag,
        page_url: str,
        prov_dom: str,
        provider_brand: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Parse an individual DOM card into structured portfolio candidate."""
        # A. Find candidate name
        card_heading = None
        for tag_name in ["h1", "h2", "h3", "h4", "h5", "h6"]:
            for h in card.find_all(tag_name):
                text_clean = h.get_text(strip=True)
                if len(text_clean) >= 2 and text_clean.lower() not in GENERIC_ACTION_LABELS:
                    card_heading = text_clean
                    break
            if card_heading:
                break

        if not card_heading:
            for tag_name in ["strong", "b"]:
                for h in card.find_all(tag_name):
                    text_clean = h.get_text(strip=True)
                    if len(text_clean) >= 2 and text_clean.lower() not in GENERIC_ACTION_LABELS:
                        card_heading = text_clean
                        break
                if card_heading:
                    break

        img_tag = card.find("img")
        img_alt = img_tag.get("alt", "").strip() if img_tag else ""
        img_url = None
        if img_tag:
            img_src = img_tag.get("src") or img_tag.get("data-src")
            if img_src:
                img_url = urljoin(page_url, img_src)

        candidate_name = card_heading
        if not candidate_name and img_alt:
            candidate_name = self._clean_name_from_alt(img_alt)

        if not candidate_name or len(candidate_name) < 2:
            return None

        # Clean candidate name
        candidate_name = self._sanitize_company_name(candidate_name)
        if not candidate_name or candidate_name.lower() in GENERIC_ACTION_LABELS:
            return None

        # Exclude tech stack platforms, CMSes, and social media platforms that are not clients
        EXCLUDED_PLATFORM_NAMES = {
            "wordpress", "shopify", "wix", "squarespace", "webflow", "magento", "drupal",
            "facebook", "instagram", "twitter", "linkedin", "youtube", "google", "meta", "whatsapp"
        }
        if candidate_name.lower() in EXCLUDED_PLATFORM_NAMES:
            return None

        # Filter out if name matches provider's own brand
        if provider_brand and candidate_name.lower() in provider_brand.lower():
            return None
        if prov_dom and prov_dom.split(".")[0] in candidate_name.lower().replace(" ", ""):
            return None

        # B. Find external client website link inside the card
        client_website_url = None
        links = card.find_all("a", href=True)
        # If card itself is inside an anchor or card is an anchor
        if card.name == "a" and card.get("href"):
            links.insert(0, card)
        parent_a = card.find_parent("a", href=True)
        if parent_a:
            links.insert(0, parent_a)

        # Prioritize links with generic CTA text (e.g. "Visit Site", "Live Site") or target="_blank"
        candidate_external_links = []
        for a in links:
            href = a.get("href", "").strip()
            if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
                continue
            resolved = urljoin(page_url, href)
            p = urlparse(resolved)
            dest_host = p.hostname or ""
            clean_dest = dest_host.lower().replace("www.", "")

            # Exclude internal links matching provider domain
            if not clean_dest or clean_dest == prov_dom or clean_dest.endswith("." + prov_dom):
                continue
            # Exclude known social & CDN platforms
            if any(clean_dest == exc or clean_dest.endswith("." + exc) for exc in EXCLUDED_OUTBOUND_DOMAINS):
                continue

            a_text = (a.get_text(strip=True) + " " + a.get("title", "") + " " + a.get("aria-label", "")).lower()
            is_cta = any(cta in a_text for cta in ["visit site", "live site", "view website", "view site", "launch", "open site", "website", "view project", "explore", "visit", "live demo"])
            is_blank = a.get("target") == "_blank"
            candidate_external_links.append((is_cta or is_blank, resolved))

        if candidate_external_links:
            # Sort so CTA or target="_blank" links come first
            candidate_external_links.sort(key=lambda x: x[0], reverse=True)
            client_website_url = candidate_external_links[0][1]

        # C. Description / Industry tags
        desc_parts = []
        p_tag = card.find("p")
        if p_tag and p_tag.get_text(strip=True):
            desc_parts.append(p_tag.get_text(strip=True))

        tag_pills = card.find_all(class_=lambda c: c and any(k in str(c).lower() for k in ["tag", "pill", "badge", "industry", "category"]))
        pill_texts = [t.get_text(strip=True) for t in tag_pills if t.get_text(strip=True)]
        if pill_texts:
            desc_parts.append(" | ".join(pill_texts))

        description = " - ".join(desc_parts) if desc_parts else None

        # D. Preceding Section Heading & Section Context
        section_heading, section_desc = self._find_section_context(card)

        # E. Evidence text & evidence snippet
        evidence_parts = []
        if section_heading:
            evidence_parts.append(f"[{section_heading}]")
        if section_desc:
            evidence_parts.append(section_desc)
        evidence_parts.append(candidate_name)
        if description:
            evidence_parts.append(description)
        if client_website_url:
            evidence_parts.append(f"Official URL: {client_website_url}")

        evidence_text = " - ".join(evidence_parts)

        # F. Confidence calculation
        confidence = 0.75
        if client_website_url:
            confidence += 0.15
        if card_heading and img_alt:
            confidence += 0.05
        if description:
            confidence += 0.05
        confidence = min(1.0, round(confidence, 2))

        return {
            "candidate_name": candidate_name,
            "company_name": candidate_name,
            "candidate_type": "company",
            "portfolio_page_url": page_url,
            "client_website_url": client_website_url,
            "external_url": client_website_url,
            "verified_website": client_website_url,
            "client_url": client_website_url,
            "company_website": client_website_url,
            "website": client_website_url,
            "image_url": img_url,
            "image_alt": img_alt,
            "card_heading": card_heading or candidate_name,
            "description": description,
            "industry": pill_texts[0] if pill_texts else None,
            "tags": pill_texts,
            "section_heading": section_heading,
            "section_context": section_desc,
            "evidence_text": evidence_text,
            "evidence_quote": evidence_text,
            "evidence_snippet": evidence_text,
            "relationship_type": "client_portfolio_reference",
            "confidence_score": confidence,
            "confidence": confidence,
            "extraction_method": "portfolio_dom",
            "discovery_status": "pending",
        }

    def _parse_logo_wrap(
        self,
        wrap: Tag,
        page_url: str,
        prov_dom: str,
        provider_brand: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Extract candidate from linked logo element."""
        img = wrap.find("img")
        if not img or not img.get("alt"):
            return None

        cand_name = self._clean_name_from_alt(img.get("alt", ""))
        cand_name = self._sanitize_company_name(cand_name)
        if not cand_name or len(cand_name) < 2 or cand_name.lower() in GENERIC_ACTION_LABELS:
            return None

        # Outbound link
        a = wrap.find("a", href=True) or wrap.find_parent("a", href=True)
        client_website_url = None
        if a and a.get("href"):
            resolved = urljoin(page_url, a["href"])
            dest_host = urlparse(resolved).hostname or ""
            clean_dest = dest_host.lower().replace("www.", "")
            if clean_dest and clean_dest != prov_dom and not clean_dest.endswith("." + prov_dom):
                if not any(clean_dest == exc or clean_dest.endswith("." + exc) for exc in EXCLUDED_OUTBOUND_DOMAINS):
                    client_website_url = resolved

        img_url = urljoin(page_url, img.get("src") or "") if img.get("src") else None
        section_heading = self._find_nearest_section_heading(wrap)

        conf = 0.80 if client_website_url else 0.65
        return {
            "candidate_name": cand_name,
            "company_name": cand_name,
            "candidate_type": "company",
            "portfolio_page_url": page_url,
            "client_website_url": client_website_url,
            "external_url": client_website_url,
            "verified_website": client_website_url,
            "client_url": client_website_url,
            "company_website": client_website_url,
            "website": client_website_url,
            "image_url": img_url,
            "image_alt": img.get("alt"),
            "card_heading": cand_name,
            "description": "Client logo reference",
            "section_heading": section_heading,
            "evidence_text": f"Client logo: {cand_name} (alt: '{img.get('alt')}')",
            "evidence_quote": f"Client logo: {cand_name} (alt: '{img.get('alt')}')",
            "evidence_snippet": f"Client logo: {cand_name} (alt: '{img.get('alt')}')",
            "relationship_type": "client_portfolio_reference",
            "confidence_score": conf,
            "confidence": conf,
            "extraction_method": "portfolio_logo_dom",
            "discovery_status": "pending",
        }

    def _extract_case_study_entries(
        self,
        soup: BeautifulSoup,
        page_url: str,
        prov_dom: str,
        provider_brand: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Extract structured case study list entries with challenge/solution/metrics."""
        results = []
        cs_headings = soup.find_all(lambda tag: tag.name in ["h2", "h3"] and any(k in tag.get_text().lower() for k in ["case studies", "deeper dives", "success stories"]))
        for h in cs_headings:
            parent_sec = h.find_parent(["section", "div"])
            if not parent_sec:
                continue
            # Look for case study items (often cards, list items, or blocks with client name + description)
            items = parent_sec.find_all(class_=lambda c: c and any(k in str(c).lower() for k in ["case-study", "study-item", "project-card", "item"]))
            if not items:
                items = parent_sec.find_all(["article", "li"])

            for it in items:
                cand = self._parse_card(it, page_url, prov_dom, provider_brand)
                if cand:
                    cand["relationship_type"] = "case_study_client"
                    cand["confidence_score"] = max(cand.get("confidence_score", 0.85), 0.90)
                    results.append(cand)

        return results

    def _clean_name_from_alt(self, alt: str) -> str:
        """Strip 'logo', 'brand', 'client' from alt text."""
        cleaned = re.sub(r'\b(logo|brand|client|website|project|icon|image|thumbnail)\b', '', alt, flags=re.IGNORECASE)
        cleaned = re.sub(r'[\-_|]', ' ', cleaned)
        return cleaned.strip()

    def _sanitize_company_name(self, name: str) -> str:
        """Clean and normalize extracted company name."""
        name = re.sub(r'\s+', ' ', name).strip()
        name = re.sub(r'^(the\s+)?(client|project|case study|brand)\s*:\s*', '', name, flags=re.IGNORECASE)
        name = re.sub(r'\s*→$', '', name)
        return name.strip()

    def _find_section_context(self, el: Tag) -> Tuple[Optional[str], Optional[str]]:
        """
        Traverse upwards to enclosing section/container to capture:
        (section_heading, section_description)
        e.g., ("Maintain", "Every site below is live, built in-house, and actively maintained...")
        """
        section_heading = None
        section_desc = None

        curr = el
        while curr and curr.name != "body":
            # 1. Look for previous heading and paragraph siblings
            prev = curr.find_previous_sibling(["h1", "h2", "h3", "h4", "header"])
            if prev and not section_heading:
                h_text = prev.get_text(strip=True)
                if h_text and len(h_text) < 100:
                    section_heading = h_text
                    next_p = prev.find_next_sibling("p")
                    if next_p and next_p.get_text(strip=True):
                        section_desc = next_p.get_text(strip=True)[:300]

            # 2. Look inside enclosing parent section
            if curr.name in ["section", "main"] or (curr.name == "div" and any(k in str(curr.get("class", [])).lower() for k in ["section", "portfolio", "container", "work"])):
                if not section_heading:
                    h = curr.find(["h1", "h2", "h3", "h4"])
                    if h:
                        section_heading = h.get_text(strip=True)
                if not section_desc:
                    p = curr.find("p")
                    if p and p != el.find("p"):
                        p_text = p.get_text(strip=True)
                        if p_text and len(p_text) > 15:
                            section_desc = p_text[:300]
                if section_heading:
                    break

            curr = curr.parent

        return section_heading, section_desc

    def _find_nearest_section_heading(self, el: Tag) -> Optional[str]:
        """Traverse upwards and backwards in DOM to find section heading."""
        h, _ = self._find_section_context(el)
        if h:
            return h
        curr = el
        while curr:
            prev = curr.find_previous_sibling(["h1", "h2", "h3", "h4"])
            if prev and prev.get_text(strip=True):
                return prev.get_text(strip=True)
            curr = curr.parent
            if curr and curr.name == "body":
                break
        return None

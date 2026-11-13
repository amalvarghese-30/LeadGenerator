"""
Google and DDG operator query generator.
Generates research queries for manual or automated inspection without scraping Google directly.
"""
from typing import List, Dict, Any
from urllib.parse import quote_plus

class GoogleDorkingHelper:
    def generate_queries(self, domain: str, brand_name: str = "") -> List[Dict[str, Any]]:
        clean_brand = brand_name.strip() or domain.split(".")[0]
        templates = [
            (f'site:{domain} "case study"', "Client Case Studies", "High"),
            (f'site:{domain} "our clients"', "Client Portfolio & Logos", "High"),
            (f'site:{domain} "testimonials"', "Customer Testimonials", "High"),
            (f'site:{domain} "success stories"', "Success Stories", "High"),
            (f'site:{domain} "founder"', "Leadership & Founders", "Medium"),
            (f'site:{domain} "personal branding"', "Service Mentions", "Medium"),
            (f'site:{domain} inurl:portfolio', "Portfolio Pages", "High"),
            (f'site:{domain} inurl:case-study', "Specific Case Studies", "High"),
            (f'site:{domain} filetype:pdf', "PDF Case Studies & Presentations", "Medium"),
            (f'site:linkedin.com/company "{clean_brand}"', "Official LinkedIn Company Profile", "High"),
            (f'site:linkedin.com/in "{clean_brand}"', "Associated Key People", "Medium"),
            (f'site:youtube.com "{clean_brand}" interview', "Founder Interviews & Client Talks", "Medium"),
        ]

        queries: List[Dict[str, Any]] = []
        for query_str, desc, priority in templates:
            encoded = quote_plus(query_str)
            queries.append({
                "query": query_str,
                "description": desc,
                "priority": priority,
                "google_search_url": f"https://www.google.com/search?q={encoded}",
                "duckduckgo_search_url": f"https://duckduckgo.com/?q={encoded}",
            })
        return queries

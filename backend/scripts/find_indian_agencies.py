import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.discovery.ddgs_search import DDGSSearch
from app.utils.url_utils import extract_domain, normalize_url

s = DDGSSearch(max_results=20)
queries = [
    'personal branding agency India',
    'executive branding agency India',
    'founder branding agency Bangalore Mumbai Delhi',
    'CEO personal branding agency India',
    'reputation management agency India'
]

excluded_domains = {
    'linkedin.com', 'clutch.co', 'medium.com', 'quora.com', 'youtube.com', 'facebook.com',
    'instagram.com', 'twitter.com', 'x.com', 'glassdoor.co.in', 'ambitionbox.com',
    'theperson.in', 'morismedia.in', 'boldface.online', 'scribblersindia.com',
    'i-midastouch.com', 'bharatcxo.com', 'ohhmybrand.com', 'postlitmedia.com',
    'brandingovercoffee.co.in', 'ra-aha.com', 'rajamedia.in', 'bhaviksarkhedi.com'
}

candidates = {}

for q in queries:
    print(f"Searching: {q}")
    results = s.search(q, region='in-en')
    for r in results:
        url = r.get("url") or r.get("href")
        title = r.get("title") or ""
        snippet = r.get("body") or r.get("snippet") or ""
        if not url:
            continue
        domain = extract_domain(url).lower()
        if any(ex in domain for ex in excluded_domains):
            continue
        # Base domain homepage
        root_url = f"https://{domain}/"
        if domain not in candidates:
            candidates[domain] = {
                "domain": domain,
                "url": root_url,
                "title": title,
                "snippet": snippet
            }

print(f"\nDiscovered {len(candidates)} candidate Indian agencies:")
for d, info in sorted(candidates.items())[:25]:
    print(f"- {d:<35} | {info['url']}")

import os
import sys
import re
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.discovery.ddgs_search import DDGSSearch
import phonenumbers

EMAIL_REGEX = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b')

def extract_phones(text: str):
    matches = []
    for match in phonenumbers.PhoneNumberMatcher(text, "IN"):
        num = match.number
        if phonenumbers.is_possible_number(num) and phonenumbers.is_valid_number(num):
            matches.append(phonenumbers.format_number(num, phonenumbers.PhoneNumberFormat.E164))
    return list(set(matches))

s = DDGSSearch(max_results=5)
tests = [
    ("Mubasshir Shaikh", "The Canvex School"),
    ("Vinay Samota", "Samota Insurance"),
    ("Omkar Mondkar", "BlankAnalytica"),
    ("Dinesh Thada", "Surge Marketing")
]

for name, comp in tests:
    print("=" * 70)
    print(f"Testing Deep Discovery for: {name} | {comp}")
    queries = [
        f'"{name}" "{comp}" email',
        f'"{name}" "{comp}" contact phone',
        f'"{name}" email "@gmail.com" OR "@"',
        f'site:thecompanycheck.com "{name}"'
    ]
    for q in queries:
        try:
            res = s.search(q, region="in-en")
            for r in res[:2]:
                title = r.get("title", "")
                snippet = r.get("snippet", "") or r.get("body", "")
                url = r.get("url", "")
                text = f"{title} {snippet}"
                emails = list(set(EMAIL_REGEX.findall(text)))
                phones = extract_phones(text)
                print(f"  Q: {q[:35]}")
                print(f"    Title: {title}")
                print(f"    Snippet: {snippet[:140]}...")
                print(f"    URL: {url}")
                if emails:
                    print(f"    >>> FOUND EMAILS: {emails}")
                if phones:
                    print(f"    >>> FOUND PHONES: {phones}")
        except Exception as e:
            print(f"    Error on {q}: {e}")

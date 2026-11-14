import os
import sys
import urllib.request
import re
import phonenumbers
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from app.enrichment.public_email_extractor import EMAIL_REGEX

sites = ['https://vitronaturals.com/', 'https://sleepycat.in/', 'https://pantproject.com/']
hdr = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}

for url in sites:
    try:
        req = urllib.request.Request(url, headers=hdr)
        html = urllib.request.urlopen(req, timeout=10).read().decode('utf-8', errors='ignore')
        soup = BeautifulSoup(html, 'html.parser')
        
        # mailto
        mailtos = [a['href'].replace('mailto:', '').split('?')[0].strip() for a in soup.select('a[href^="mailto:"]')]
        all_emails = list(set(mailtos + EMAIL_REGEX.findall(html)))
        clean_emails = [e for e in all_emails if not any(x in e.lower() for x in ['png', 'jpg', 'webp', 'sentry', 'wix', 'example'])]
        
        # tel
        tels = [a['href'].replace('tel:', '').strip() for a in soup.select('a[href^="tel:"]')]
        
        print(f"\n{url}:")
        print(f"   Emails: {clean_emails[:3]}")
        print(f"   Phones: {tels[:3]}")
    except Exception as e:
        print(f"{url} error: {e}")

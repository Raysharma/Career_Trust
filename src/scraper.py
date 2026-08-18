"""
URL Scraper that fetches the HTML content of a job posting URL, parses the text,
and extracts the clean domain name.
"""

import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse
import re


class URLScraper:
    def scrape(self, url):
        """
        Takes a URL, fetches the HTML, and extracts the core text content.
        Also returns the base domain for the domain checker.
        """
        if not url or not url.strip():
            return {
                'success': False,
                'error': 'EMPTY_URL'
            }

        url = url.strip()
        try:
            parsed_url = urlparse(url if url.startswith(('http://', 'https://')) else f'https://{url}')
            netloc = parsed_url.netloc.strip()
            if not netloc or '.' not in netloc:
                return {
                    'success': False,
                    'error': 'INVALID_URL'
                }

            if not url.startswith(('http://', 'https://')):
                url = 'https://' + url

            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept-Language': 'en-US,en;q=0.9',
            }

            print(f"  Fetching: {url}")
            response = requests.get(url, headers=headers, timeout=(5, 10))
            response.raise_for_status()

            # Use lxml if available, otherwise fallback to html.parser
            try:
                soup = BeautifulSoup(response.text, 'lxml')
            except Exception:
                soup = BeautifulSoup(response.text, 'html.parser')

            for elem in soup(['script', 'style', 'header', 'footer', 'nav', 'noscript']):
                elem.extract()

            text = soup.get_text(separator=' ')
            text = re.sub(r'\s+', ' ', text).strip()

            lower_text = text.lower()
            if len(text) < 100 or "javascript is disabled" in lower_text or "verify that you're not a robot" in lower_text or "security check" in lower_text:
                return {
                    'success': False,
                    'error': "ANTI_BOT_BLOCKED"
                }

            domain = urlparse(response.url).netloc.replace('www.', '')

            return {
                'success': True,
                'text': text,
                'domain': domain,
                'url': response.url
            }

        except Exception as e:
            print(f"  Scraper Error: {e}")
            return {
                'success': False,
                'error': str(e)
            }

"""
Extracts domain names and analyzes company web infrastructure:
SSL certificates, WHOIS registration age, reachability, suspicious TLDs, and lookalike patterns.
"""

import socket
import ssl
import sys
import io
import re
from datetime import datetime
from urllib.parse import urlparse
import requests


def extract_domain(url):
    """
    Extracts the clean host domain from any URL or domain string.
    "https://careers.google.com/jobs/results" -> "careers.google.com" -> "google.com"
    """
    if not url:
        return ""

    url = url.strip()
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url

    try:
        parsed = urlparse(url)
        domain = parsed.netloc or parsed.path
        domain = domain.replace('www.', '').strip()
        domain = domain.split('/')[0]
        domain = domain.split(':')[0]
        return domain.lower()
    except Exception:
        return url.lower()


def check_ssl(domain):
    """
    Tests HTTPS connectivity and verifies certificate validity.
    Hardened against Windows strptime timezone limitations.
    """
    if not domain:
        return {'has_ssl': False, 'ssl_days_left': 0}

    try:
        context = ssl.create_default_context()
        with socket.create_connection((domain, 443), timeout=5) as sock:
            with context.wrap_socket(sock, server_hostname=domain) as ssock:
                cert = ssock.getpeercert()
                expiry_str = cert.get('notAfter', '')
                if expiry_str:
                    days_left = _parse_ssl_date(expiry_str)
                    return {'has_ssl': True, 'ssl_days_left': days_left}
                return {'has_ssl': True, 'ssl_days_left': -1}
    except Exception:
        return {'has_ssl': False, 'ssl_days_left': 0}


def _parse_ssl_date(date_str):
    """Safely parse SSL certificate notAfter date across OS platforms."""
    try:
        # Standard format: 'May 15 12:00:00 2026 GMT'
        # Strip timezone component to avoid Windows %Z parsing failures
        parts = date_str.strip().split()
        if len(parts) >= 4:
            clean_date = " ".join(parts[:4])
            expiry = datetime.strptime(clean_date, '%b %d %H:%M:%S %Y')
            return (expiry - datetime.utcnow()).days
    except Exception:
        pass
    return 30


def check_whois(domain):
    """
    Look up domain registration age using WHOIS.
    """
    if not domain:
        return {
            'domain_age_days': 0,
            'domain_age_years': 0,
            'whois_privacy': False,
            'registrar': 'MISSING_DOMAIN',
        }

    try:
        import whois
    except ImportError:
        return {
            'domain_age_days': 0,
            'domain_age_years': 0,
            'whois_privacy': False,
            'registrar': 'LIBRARY_MISSING',
        }

    try:
        # Suppress internal whois socket timeout outputs
        stderr_backup = sys.stderr
        sys.stderr = io.StringIO()
        try:
            w = whois.whois(domain)
        finally:
            sys.stderr = stderr_backup

        creation_date = w.creation_date
        if isinstance(creation_date, list):
            creation_date = creation_date[0]

        domain_age_days = 0
        if creation_date:
            if creation_date.tzinfo is not None:
                creation_date = creation_date.replace(tzinfo=None)
            domain_age_days = max(0, (datetime.utcnow() - creation_date).days)

        registrant = str(w.get('name', '') or w.get('org', '') or '')
        privacy = any(word in registrant.lower() for word in
                      ['privacy', 'redacted', 'proxy', 'protected', 'whoisguard', 'withheld'])

        return {
            'domain_age_days': domain_age_days,
            'domain_age_years': round(domain_age_days / 365.25, 1),
            'whois_privacy': privacy,
            'registrar': str(w.registrar or 'Unknown'),
        }

    except Exception:
        return {
            'domain_age_days': 0,
            'domain_age_years': 0,
            'whois_privacy': False,
            'registrar': 'LOOKUP_FAILED',
        }


def check_website_alive(domain):
    """
    Checks if the company website is online and responsive.
    """
    if not domain:
        return {'website_alive': False, 'http_status': 0, 'final_url': ''}

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    }

    for scheme in ('https', 'http'):
        try:
            response = requests.get(
                f"{scheme}://{domain}",
                timeout=5,
                allow_redirects=True,
                headers=headers,
            )
            return {
                'website_alive': True,
                'http_status': response.status_code,
                'final_url': response.url,
            }
        except Exception:
            continue

    return {
        'website_alive': False,
        'http_status': 0,
        'final_url': '',
    }


def check_suspicious_domain_patterns(domain):
    """
    Detects scam lookalike domains and cheap throwaway TLDs commonly used in fake job campaigns.
    Example: 'tcs-careers-portal.xyz', 'google-recruitment-online.top'
    """
    domain = domain.lower()

    suspicious_tlds = {'.xyz', '.top', '.work', '.tk', '.ml', '.ga', '.cf', '.gq', '.buzz', '.monster', '.live'}
    has_suspicious_tld = any(domain.endswith(tld) for tld in suspicious_tlds)

    # Keywords frequently chained in scam domains
    scam_keywords = ['careers', 'recruitment', 'hiring', 'jobs', 'portal', 'apply', 'interview', 'hr-team']
    matched_keywords = [kw for kw in scam_keywords if kw in domain]
    is_hyphenated_scam = (len(matched_keywords) >= 2 or ('-' in domain and len(matched_keywords) >= 1))

    return {
        'has_suspicious_tld': has_suspicious_tld,
        'is_suspicious_lookalike': is_hyphenated_scam,
    }


def analyze_domain(url_or_domain):
    """
    Runs complete domain and company web infrastructure analysis.
    """
    domain = extract_domain(url_or_domain)
    if not domain:
        return {
            'domain': '',
            'has_ssl': False,
            'ssl_days_left': 0,
            'domain_age_days': 0,
            'domain_age_years': 0,
            'whois_privacy': False,
            'website_alive': False,
            'domain_risk_score': 3.0,
        }

    ssl_result = check_ssl(domain)
    whois_result = check_whois(domain)
    alive_result = check_website_alive(domain)
    pattern_result = check_suspicious_domain_patterns(domain)

    result = {'domain': domain}
    result.update(ssl_result)
    result.update(whois_result)
    result.update(alive_result)
    result.update(pattern_result)

    risk = 0.0

    # 1. SSL security
    if not result['has_ssl']:
        risk += 2.0

    # 2. Website Reachability
    if not result['website_alive']:
        risk += 3.0

    # 3. Domain Age (Newly registered domains are primary scam vectors)
    age_days = result['domain_age_days']
    if 0 < age_days < 30:
        risk += 3.5  # Brand new domain (<1 month)
    elif 0 < age_days < 90:
        risk += 2.0  # Fresh domain (<3 months)
    elif 0 < age_days < 365:
        risk += 0.5

    # 4. Lookalike & Suspicious TLD patterns
    if result.get('has_suspicious_tld'):
        risk += 2.0
    if result.get('is_suspicious_lookalike'):
        risk += 1.5

    result['domain_risk_score'] = min(round(risk, 2), 7.0)
    return result

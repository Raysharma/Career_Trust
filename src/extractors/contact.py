"""
Extracts and validates recruiter contact details (emails, phones, WhatsApp, Telegram, LinkedIn).
Detects recruiter free-email scams, messaging app hiring redirects, and company domain mismatches.
"""

import re
from urllib.parse import urlparse


def extract_emails(text):
    """
    Find all email addresses in text.
    """
    pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    emails = re.findall(pattern, text, re.IGNORECASE)
    return list(set(emails))


def extract_phones(text):
    """
    Find phone numbers in text (Indian, US, and international formats).
    """
    patterns = [
        r'(?:\+?91[\s-]?)?[6-9]\d{9}',
        r'(?:\+?91[\s-]?)?0?\d{2,4}[\s-]?\d{6,8}',
        r'\+?\d{1,3}[\s-]?\(?\d{2,4}\)?[\s-]?\d{3,4}[\s-]?\d{3,4}',
    ]

    phones = []
    for pattern in patterns:
        matches = re.findall(pattern, text)
        phones.extend(matches)

    cleaned = []
    for phone in phones:
        digits = re.sub(r'\D', '', phone)
        if 10 <= len(digits) <= 13:
            cleaned.append(phone.strip())

    return list(set(cleaned))


def extract_urls(text):
    """
    Find website URLs in text.
    """
    pattern = r'https?://[^\s<>\"\']+|www\.[^\s<>\"\']+'
    urls = re.findall(pattern, text, re.IGNORECASE)
    return list(set(urls))


def extract_linkedin(text):
    """
    Find LinkedIn profile or company page URLs.
    """
    pattern = r'(?:https?://)?(?:www\.)?linkedin\.com/(?:company|in|jobs)/[^\s<>\"\']*'
    matches = re.findall(pattern, text, re.IGNORECASE)
    return list(set(matches))


def extract_messaging_app_recruitment(text):
    """
    Detects WhatsApp or Telegram recruitment channels.
    Scammers frequently redirect job board applicants to WhatsApp or Telegram
    to avoid platform moderation and demand upfront fees or task deposits.
    """
    whatsapp_patterns = [
        r'(?:https?://)?(?:wa\.me|api\.whatsapp\.com)/[^\s<>\"\']+',
        r'(?:send\s*resume|contact|ping|msg|message|whatsapp)\s*(?:on|to|at)?\s*(?:whatsapp|wa)?\s*[:\s-]*\+?\d{10,13}',
        r'(?:whatsapp|wa)\s*(?:group|number|hr|recruiter)?\s*[:\s-]*\+?\d{10,13}',
    ]

    telegram_patterns = [
        r'(?:https?://)?(?:t\.me|telegram\.me)/[^\s<>\"\']+',
        r'(?:join|contact|dm|message)\s*(?:on|our)?\s*telegram\s*(?:channel|group|id|handle)?\s*[:\s-]*@?[a-zA-Z0-9_]+',
        r'@(?:[a-zA-Z0-9_]+(?:recruiter|hr|careers?|jobs?|official|task))',
    ]

    wa_found = []
    for pattern in whatsapp_patterns:
        wa_found.extend(re.findall(pattern, text, re.IGNORECASE))

    tg_found = []
    for pattern in telegram_patterns:
        tg_found.extend(re.findall(pattern, text, re.IGNORECASE))

    return list(set(wa_found)), list(set(tg_found))


def check_email_legitimacy(emails, company_domain=None):
    """
    Evaluates whether contact emails come from official company infrastructure
    or free public webmail providers.
    """
    free_providers = {
        'gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com',
        'aol.com', 'mail.com', 'protonmail.com', 'yandex.com',
        'rediffmail.com', 'zoho.com', 'icloud.com', 'gmx.com',
        'live.com', 'msn.com', 'inbox.com'
    }

    clean_company_domain = ""
    if company_domain:
        clean_company_domain = company_domain.lower().replace('www.', '').strip()
        if '/' in clean_company_domain:
            clean_company_domain = urlparse('http://' + clean_company_domain).netloc or clean_company_domain.split('/')[0]

    results = []
    for email in emails:
        parts = email.split('@')
        if len(parts) != 2:
            continue

        username, domain = parts
        domain = domain.lower()

        is_free = domain in free_providers
        matches_company = False
        if clean_company_domain and not is_free:
            matches_company = (domain == clean_company_domain or domain.endswith('.' + clean_company_domain))

        results.append({
            'email': email,
            'domain': domain,
            'is_free_email': is_free,
            'matches_company': matches_company,
        })

    return results


def analyze_contacts(text, company_domain=None):
    """
    Run contact authenticity checks.
    Distinguishes legitimate corporate ATS postings from recruiter impersonation scams.
    """
    emails = extract_emails(text)
    phones = extract_phones(text)
    urls = extract_urls(text)
    linkedin = extract_linkedin(text)
    wa_links, tg_links = extract_messaging_app_recruitment(text)

    email_analysis = check_email_legitimacy(emails, company_domain)

    risk = 0.0

    # 1. Messaging App Recruitment Scam (WhatsApp/Telegram direct recruiting)
    has_messaging_scam = bool(wa_links or tg_links)
    if has_messaging_scam:
        risk += 3.5

    # 2. Recruiter Free Email Scam (Only using @gmail.com, @yahoo.com for hiring)
    has_free_email_only = bool(emails and all(e['is_free_email'] for e in email_analysis))
    has_company_email = any(e.get('matches_company', False) for e in email_analysis)

    if has_free_email_only:
        risk += 3.0

    # 3. Company Domain Mismatch (Company claimed, but recruiter email is from a totally different non-free domain)
    if company_domain and emails and not has_company_email and not has_free_email_only:
        risk += 1.5

    return {
        'emails_found': emails,
        'phones_found': phones,
        'urls_found': urls,
        'linkedin_found': linkedin,
        'whatsapp_recruitment': wa_links,
        'telegram_recruitment': tg_links,
        'has_messaging_recruitment': has_messaging_scam,
        'email_analysis': email_analysis,
        'has_free_email_only': has_free_email_only,
        'has_company_email': has_company_email,
        'contact_risk_score': min(round(risk, 2), 6.0),
    }

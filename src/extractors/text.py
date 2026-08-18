"""
Detects red flags in job posting texts using calibrated pattern matching.
Identifies payment requests, task/crypto scams, urgency pressure, unrealistic promises,
and missing structural details.
"""

import re


def check_payment_requests(text):
    """
    Does the job ask for MONEY or FEES from the applicant?
    Legitimate employers never charge candidates for applying, interviewing,
    training, equipment, or document verification.
    """
    patterns = [
        r'(?:pay|send|deposit|transfer)\s*(?:₹|rs\.?|inr|usd|\$)\s*\d+',
        r'(?:registration|processing|application|training|interview|screening|onboarding)\s*(?:fee|charge|cost|amount)',
        r'(?:₹|rs\.?|inr|\$)\s*\d+\s*(?:fee|charge|deposit|payment)',
        r'pay\s*(?:to|for)\s*(?:register|apply|join|start|interview|training|kit|laptop|equipment|id\s*card)',
        r'advance\s*(?:payment|fee|deposit|money)',
        r'refundable\s*(?:deposit|fee|amount|security)',
        r'(?:security|caution|courier|delivery)\s*(?:deposit|fee|charge)',
        r'(?:purchase|buy)\s*(?:the\s*)?(?:training|starter|software|kit|package)\s*(?:to\s*start|for\s*work)?',
    ]

    count = 0
    matches_found = []
    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            count += len(matches)
            matches_found.extend(matches)

    return min(count, 5), matches_found


def check_task_and_social_scams(text):
    """
    Detects modern freelance / social task fraud commonly posted on job boards:
    - YouTube/Instagram liking or subscribing tasks
    - Hotel/Google Maps rating jobs
    - Daily UPI / Crypto / USDT payouts
    - Telegram channel task execution
    """
    patterns = [
        r'(?:like|subscribe|watch)\s*(?:youtube|video|instagram|reels|tiktok)\s*(?:and|to)\s*(?:earn|get\s*paid)',
        r'(?:hotel|google\s*maps?|app|product)\s*(?:rating|review|reviewing)\s*(?:job|task|work)',
        r'(?:daily|instant)\s*(?:payout|payment|income|withdrawal)\s*(?:via|through|in)?\s*(?:upi|gpay|phonepe|crypto|usdt|bank)',
        r'(?:complete|do)\s*(?:simple|easy)\s*tasks?\s*(?:to\s*earn|and\s*get\s*paid)',
        r'(?:typing|captcha|form\s*filling|copy\s*paste|sms\s*sending)\s*(?:job|work)',
        r'earn\s*(?:₹|rs\.?|inr|\$)\s*\d+\s*(?:per\s*day|daily|per\s*hour|per\s*task|every\s*day)',
    ]

    count = 0
    matches_found = []
    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            count += len(matches)
            matches_found.extend(matches)

    return min(count, 5), matches_found


def check_urgency(text):
    """
    Is the post using HIGH-PRESSURE language?
    Scammers manufacture artificial urgency to make victims act before researching.
    """
    urgency_phrases = [
        r'urgent(?:ly)?\s*(?:hiring|needed|required|opening|vacancy)',
        r'apply\s*(?:now|immediately|today|asap|fast)',
        r'limited\s*(?:slots?|seats?|positions?|vacancies|openings|tickets)',
        r'(?:last|final)\s*(?:date|chance|opportunity|call)',
        r'don\'?t\s*miss\s*(?:this|out)',
        r'\bhurry\b',
        r'act\s*(?:now|fast|quickly)',
        r'only\s*\d+\s*(?:spots?|openings?|seats?)\s*left',
    ]

    count = 0
    matches_found = []
    for pattern in urgency_phrases:
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            count += len(matches)
            matches_found.extend(matches)

    return min(count, 5), matches_found


def check_too_good(text):
    """
    Are they promising unrealistic rewards with little or no effort/qualifications?
    """
    patterns = [
        r'(?:no|zero|without)\s*(?:experience|qualification|skills?|degree|interview)\s*(?:needed|required|necessary)?',
        r'guaranteed\s*(?:income|salary|job|placement|earnings|returns)',
        r'(?:unlimited|passive)\s*(?:income|earning)',
        r'(?:work\s*from\s*home|wfh)\s*(?:and\s*)?earn\s*(?:₹|rs\.?|inr|\$)\s*\d{4,}',
        r'earn\s*up\s*to\s*(?:₹|rs\.?|inr|\$)\s*\d{5,}\s*(?:monthly|per\s*month|weekly)',
        r'simple\s*online\s*work\s*(?:suitable\s*for\s*(?:students?|housewives|everyone))',
    ]

    count = 0
    matches_found = []
    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            count += len(matches)
            matches_found.extend(matches)

    return min(count, 5), matches_found


def check_poor_grammar(text):
    """
    Count spam indicators such as excessive capitalization and punctuation.
    """
    patterns = [
        r'(?:dear\s+(?:candidate|applicant|sir|madam|job\s*seeker))',
        r'\b(?:kindly\s+(?:dm|inbox|contact|revert|pay|deposit))\b',
        r'!!!{2,}',
        r'\?\?\?{2,}',
        r'\b[A-Z]{6,}\b',
    ]

    count = 0
    matches_found = []
    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE if 'A-Z' not in pattern else 0)
        if matches:
            count += len(matches)
            matches_found.extend(matches)

    return min(count, 5), matches_found


def check_vague_details(text):
    """
    Legitimate job descriptions provide clear responsibilities and qualifications.
    Check whether vital sections are completely absent.
    """
    has_specific_role = bool(re.search(
        r'(?:responsibilities|duties|role\s*(?:includes|overview)|what\s*you\'?ll\s*do|key\s*tasks|deliverables)',
        text, re.IGNORECASE
    ))
    has_requirements = bool(re.search(
        r'(?:requirements?|qualifications?|must\s*have|skills?\s*(?:needed|required)|prerequisites|experience\s*in)',
        text, re.IGNORECASE
    ))
    has_company_info = bool(re.search(
        r'(?:about\s*(?:us|the\s*company|our\s*team)|who\s*we\s*are|founded|established|headquarter|leading\s*provider)',
        text, re.IGNORECASE
    ))

    missing = 0
    # Only evaluate vagueness if text is reasonably long (> 150 chars)
    if len(text.strip()) > 150:
        if not has_specific_role:
            missing += 1
        if not has_requirements:
            missing += 1
        if not has_company_info:
            missing += 1

    return missing


def analyze_text(text):
    """
    Run all red flag checks on text and return structured metrics with matched signals.
    """
    payment_count, payment_matches = check_payment_requests(text)
    task_count, task_matches = check_task_and_social_scams(text)
    urgency_count, urgency_matches = check_urgency(text)
    too_good_count, too_good_matches = check_too_good(text)
    grammar_count, grammar_matches = check_poor_grammar(text)
    vague_count = check_vague_details(text)

    # Weighted risk scoring:
    # Payment requests (weight 4) and Task scams (weight 3.5) are critical scam indicators.
    total_risk = (
        payment_count * 4.0 +
        task_count * 3.5 +
        too_good_count * 2.0 +
        urgency_count * 1.0 +
        grammar_count * 1.0 +
        vague_count * 0.8
    )

    return {
        'text_risk_score': round(total_risk, 2),
        'payment_flag': payment_count,
        'task_flag': task_count,
        'urgency_flag': urgency_count,
        'too_good_flag': too_good_count,
        'grammar_flag': grammar_count,
        'vague_flag': vague_count,
        'matched_signals': {
            'payments': payment_matches,
            'tasks': task_matches,
            'urgency': urgency_matches,
            'too_good': too_good_matches,
            'grammar': grammar_matches,
        }
    }

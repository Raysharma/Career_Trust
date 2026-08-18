"""
Unified Hybrid Scorer combining deep learning NLP (DistilBERT),
recruiter authenticity, company domain verification, and red-flag heuristics.
"""

import os
import sys

# Fix Windows console encoding if needed
if sys.stdout and getattr(sys.stdout, 'encoding', None) and sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

from src.extractors.text import analyze_text
from src.extractors.domain import analyze_domain, extract_domain
from src.extractors.contact import analyze_contacts


class HybridScorer:
    """
    Unified fraud detection scoring engine combining fine-tuned DistilBERT
    with multi-factor heuristic intelligence.
    """

    KNOWN_JOB_BOARDS = {
        'linkedin.com', 'internshala.com', 'indeed.com', 'naukri.com',
        'glassdoor.com', 'monster.com', 'foundit.in', 'unstop.com',
        'instahyre.com', 'hirist.com', 'wellfound.com', 'greenhouse.io',
        'lever.co', 'workday.com', 'smartrecruiters.com'
    }

    def __init__(self, model_path=None):
        if model_path is None:
            model_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                'fraud_job_model', 'final_model'
            )

        self.bert_available = False
        try:
            from transformers import pipeline, AutoTokenizer, AutoModelForSequenceClassification

            if os.path.exists(model_path):
                print(f"  Loading DistilBERT from {model_path}...")
                tokenizer = AutoTokenizer.from_pretrained(model_path)
                model = AutoModelForSequenceClassification.from_pretrained(model_path)
                self.fraud_label = self._resolve_fraud_label(model)
                self.classifier = pipeline(
                    "text-classification", model=model, tokenizer=tokenizer, top_k=None
                )
                self.bert_available = True
                print("  ✅ DistilBERT classifier loaded successfully")
            else:
                print(f"  ⚠️ Model not found at {model_path}. Running in rules-only fallback mode.")

        except Exception as e:
            print(f"  ⚠️ DistilBERT loading failed ({e}). Falling back to rules-only mode.")

        self.weights = self._load_weights()
        self.risk_thresholds = {
            'low': self._get_float_env('TRUST_THRESHOLD_LOW', 75.0),
            'medium': self._get_float_env('TRUST_THRESHOLD_MEDIUM', 50.0),
            'high': self._get_float_env('TRUST_THRESHOLD_HIGH', 30.0),
        }

    def _get_float_env(self, name, default, minimum=None, maximum=None):
        value = os.getenv(name)
        if value is None:
            return default
        try:
            parsed = float(value)
        except ValueError:
            return default
        if minimum is not None:
            parsed = max(minimum, parsed)
        if maximum is not None:
            parsed = min(maximum, parsed)
        return parsed

    def _load_weights(self):
        if self.bert_available:
            weights = {
                'bert': self._get_float_env('TRUST_WEIGHT_BERT', 0.40, 0.0, 1.0),
                'text_rules': self._get_float_env('TRUST_WEIGHT_TEXT', 0.25, 0.0, 1.0),
                'domain': self._get_float_env('TRUST_WEIGHT_DOMAIN', 0.20, 0.0, 1.0),
                'contact': self._get_float_env('TRUST_WEIGHT_CONTACT', 0.15, 0.0, 1.0),
            }
        else:
            weights = {
                'bert': 0.0,
                'text_rules': 0.45,
                'domain': 0.35,
                'contact': 0.20,
            }

        total = sum(weights.values())
        if total > 0:
            weights = {k: v / total for k, v in weights.items()}
        return weights

    def _resolve_fraud_label(self, model):
        config = getattr(model, "config", None)
        id2label = getattr(config, "id2label", {}) or {}

        for index, label in id2label.items():
            label_str = str(label).strip().upper()
            if any(token in label_str for token in ("FRAUD", "FAKE", "SCAM", "SPAM", "1")):
                return id2label.get(int(index), f"LABEL_{index}")

        if 1 in id2label:
            return id2label[1]
        return "LABEL_1"

    def _get_bert_score(self, text):
        if not self.bert_available:
            return 0.5
        try:
            truncated = text[:2000] if len(text) > 2000 else text
            results = self.classifier(truncated, truncation=True, max_length=256)[0]
            scores = {r['label']: r['score'] for r in results}
            return scores.get(self.fraud_label, scores.get('LABEL_1', scores.get('FRAUD', 0.5)))
        except Exception as e:
            print(f"  ⚠️ DistilBERT inference failed: {e}")
            return 0.5

    def analyze(self, job_data):
        """
        Performs full multi-factor fraud detection on a job posting.
        """
        text = job_data.get('text', '') or ''
        company_url = job_data.get('company_url', '') or ''
        company_domain = job_data.get('company_domain', '') or ''

        # Extract domain from company_url if domain is not directly provided
        if company_url and not company_domain:
            company_domain = extract_domain(company_url)

        # Check if the URL is from a known job board platform
        is_job_board = False
        if company_domain:
            is_job_board = any(jb in company_domain for jb in self.KNOWN_JOB_BOARDS)

        result = {}

        # 1. DistilBERT AI Language Context Model
        bert_fraud_prob = self._get_bert_score(text)
        result['bert_fraud_probability'] = round(bert_fraud_prob, 4)
        bert_trust = max(0.0, min(1.0, 1.0 - bert_fraud_prob))

        # 2. Text Red Flag Heuristics
        text_features = analyze_text(text)
        result['text_risk_score'] = text_features['text_risk_score']
        result['payment_flag'] = text_features['payment_flag']
        result['task_flag'] = text_features.get('task_flag', 0)
        result['urgency_flag'] = text_features['urgency_flag']
        result['too_good_flag'] = text_features['too_good_flag']
        result['grammar_flag'] = text_features['grammar_flag']
        result['vague_flag'] = text_features['vague_flag']
        result['matched_signals'] = text_features.get('matched_signals', {})

        # Maximum possible text risk ceiling for normalization
        max_text_risk = 16.0
        text_trust = max(0.0, 1.0 - (text_features['text_risk_score'] / max_text_risk))

        # 3. Domain & Infrastructure Checks
        if company_domain and not is_job_board:
            domain_features = analyze_domain(company_domain)
        else:
            # If domain is not provided or is a job board, evaluate neutrally
            domain_features = {
                'domain': company_domain,
                'has_ssl': True if is_job_board else False,
                'ssl_days_left': 365 if is_job_board else 0,
                'domain_age_days': 3650 if is_job_board else 0,
                'domain_age_years': 10.0 if is_job_board else 0,
                'whois_privacy': False,
                'website_alive': True if is_job_board else False,
                'domain_risk_score': 0.0 if is_job_board else 1.5,
            }

        result['domain_risk_score'] = domain_features.get('domain_risk_score', 1.5)
        result['has_ssl'] = int(domain_features.get('has_ssl', False))
        result['domain_age_days'] = domain_features.get('domain_age_days', 0)
        result['website_alive'] = int(domain_features.get('website_alive', False))
        result['is_job_board_hosted'] = is_job_board

        max_domain_risk = 7.0
        domain_trust = max(0.0, 1.0 - (result['domain_risk_score'] / max_domain_risk))

        # 4. Contact & Recruiter Authenticity Checks
        contact_features = analyze_contacts(text, "" if is_job_board else company_domain)
        result['email_count'] = len(contact_features.get('emails_found', []))
        result['phone_count'] = len(contact_features.get('phones_found', []))
        result['has_linkedin'] = int(bool(contact_features.get('linkedin_found', [])))
        result['has_free_email_only'] = int(contact_features.get('has_free_email_only', False))
        result['has_company_email'] = int(contact_features.get('has_company_email', False))
        result['has_messaging_recruitment'] = int(contact_features.get('has_messaging_recruitment', False))
        result['contact_risk_score'] = contact_features.get('contact_risk_score', 0.0)

        max_contact_risk = 6.0
        contact_trust = max(0.0, 1.0 - (result['contact_risk_score'] / max_contact_risk))

        # 5. Hybrid Weighted Score Computation
        hybrid_trust = (
            bert_trust    * self.weights['bert'] +
            text_trust    * self.weights['text_rules'] +
            domain_trust  * self.weights['domain'] +
            contact_trust * self.weights['contact']
        ) * 100.0

        # Critical Overrides: If payment is demanded, cap trust score to prevent false negatives
        if result['payment_flag'] > 0 or result['task_flag'] > 0:
            hybrid_trust = min(hybrid_trust, 25.0)

        hybrid_trust = max(0.0, min(100.0, round(hybrid_trust, 1)))
        result['hybrid_trust_score'] = hybrid_trust

        result['_bert_trust'] = round(bert_trust * 100, 1)
        result['_text_rules_trust'] = round(text_trust * 100, 1)
        result['_text_trust'] = round(text_trust * 100, 1)
        result['_domain_trust'] = round(domain_trust * 100, 1)
        result['_contact_trust'] = round(contact_trust * 100, 1)

        # Risk Classification
        if hybrid_trust >= self.risk_thresholds['low']:
            result['risk_level'] = 'LOW'
        elif hybrid_trust >= self.risk_thresholds['medium']:
            result['risk_level'] = 'MEDIUM'
        elif hybrid_trust >= self.risk_thresholds['high']:
            result['risk_level'] = 'HIGH'
        else:
            result['risk_level'] = 'CRITICAL'

        # Generate human-readable explanations
        result['explanation'] = self._build_explanation(result)

        return result

    def _build_explanation(self, result):
        reasons = []

        # Upfront Payment Flags
        if result['payment_flag'] > 0:
            reasons.append("🚨 Critical: Job demands upfront payment/registration/security fee (legitimate employers never charge candidates)")

        # Task & Rating Scams
        if result.get('task_flag', 0) > 0:
            reasons.append("🚨 High Risk: Contains task/rating/crypto daily payout patterns typical of online hiring scams")

        # WhatsApp / Telegram Recruitment
        if result.get('has_messaging_recruitment'):
            reasons.append("⚠️ Suspicious: Requests candidates to contact recruiter directly on WhatsApp or Telegram")

        # Free Email Scams
        if result.get('has_free_email_only'):
            reasons.append("⚠️ Suspicious: Recruiter uses a free public webmail address (@gmail/@yahoo) rather than a verified corporate domain")

        # DistilBERT NLP Pattern Detection
        if result['bert_fraud_probability'] > 0.7:
            reasons.append("🤖 AI Language Analysis detected strong semantic fraud indicators in the job text")
        elif result['bert_fraud_probability'] > 0.5:
            reasons.append("🤖 AI Language Analysis identified some suspicious phrases and structure")

        # Urgency Tactics
        if result['urgency_flag'] > 1:
            reasons.append("⚠️ Employs high-pressure urgency tactics (e.g., 'apply immediately', 'limited slots')")

        # Unrealistic Compensation
        if result['too_good_flag'] > 0:
            reasons.append("⚠️ Promises unrealistic earnings with zero experience or minimal qualifications")

        # Domain Verification Issues
        if result['domain_risk_score'] >= 5.0:
            reasons.append("🌐 Company website could not be verified, is unreachable, or has an invalid SSL certificate")
        elif result['domain_risk_score'] >= 3.0:
            reasons.append("🌐 Company domain is newly registered or has security warnings")

        # Formatting & Grammar
        if result['grammar_flag'] > 1:
            reasons.append("📝 Contains unprofessional formatting, excessive capitalization, or spam patterns")

        # Structural Vagueness
        if result['vague_flag'] >= 3:
            reasons.append("📋 Lacks essential job details (missing role responsibilities, prerequisites, or company background)")

        if not reasons:
            reasons.append("✅ Legitimate posting structure with verified trust indicators")

        return reasons

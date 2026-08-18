"""
Automated test suite verifying detection accuracy, false positive prevention,
and scam identification across all extractors and the HybridScorer.
"""

import os
import sys
import unittest

if sys.stdout and getattr(sys.stdout, 'encoding', None) and sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
from src.extractors.text import analyze_text
from src.extractors.contact import analyze_contacts
from src.extractors.domain import analyze_domain, extract_domain
from src.scorer import HybridScorer
from src.scraper import URLScraper


class TestCareerTrustIntelligence(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.scorer = HybridScorer()

    # 1. Text Red Flag Heuristic Tests
    def test_text_flags_upfront_payment(self):
        text = "Urgent opening for back office executive. Pay a refundable deposit of Rs. 1500 for training kit."
        result = analyze_text(text)
        self.assertGreater(result["payment_flag"], 0)
        self.assertGreater(result["text_risk_score"], 3.5)

    def test_text_flags_task_rating_scam(self):
        text = "Work from home! Like youtube videos and hotel rating task. Earn Rs 3000 daily payout via UPI."
        result = analyze_text(text)
        self.assertGreater(result["task_flag"], 0)
        self.assertGreater(result["text_risk_score"], 3.5)

    def test_text_clean_on_benign_job(self):
        text = (
            "About the Company: Acme Corp is a SaaS company founded in 2018. "
            "Responsibilities: Design, build, and maintain efficient APIs in Python and FastAPI. "
            "Requirements: 3+ years experience with relational databases and automated testing."
        )
        result = analyze_text(text)
        self.assertEqual(result["payment_flag"], 0)
        self.assertEqual(result["task_flag"], 0)
        self.assertLessEqual(result["text_risk_score"], 1.5)

    # 2. Contact & Recruiter Authenticity Tests
    def test_contact_detects_whatsapp_and_telegram_redirect(self):
        text = "Great opportunity! Send your resume directly to our WhatsApp recruiter: +91 9876543210 or join t.me/hiringteam"
        result = analyze_contacts(text)
        self.assertTrue(result["has_messaging_recruitment"])
        self.assertGreater(result["contact_risk_score"], 3.0)

    def test_contact_detects_recruiter_free_email_scam(self):
        text = "Interested candidates should email their resume to hr.company.recruitment@gmail.com for immediate interview."
        result = analyze_contacts(text, company_domain="acmecorp.com")
        self.assertTrue(result["has_free_email_only"])
        self.assertGreater(result["contact_risk_score"], 2.5)

    def test_contact_does_not_penalize_ats_job_without_email(self):
        text = "Apply via our careers portal. We will review your application and contact shortlisted candidates."
        result = analyze_contacts(text)
        self.assertEqual(result["contact_risk_score"], 0.0)

    # 3. Domain Extractor Tests
    def test_extract_clean_domain(self):
        self.assertEqual(extract_domain("https://careers.google.com/jobs/view"), "careers.google.com")
        self.assertEqual(extract_domain("www.amazon.jobs"), "amazon.jobs")

    # 4. End-to-End Scorer Tests (False Positive & False Negative Prevention)
    def test_scorer_flags_critical_for_payment_demands(self):
        result = self.scorer.analyze({
            "text": "Urgent hiring! Work from home data entry. Pay registration fee of Rs. 500 to get started.",
            "company_url": "",
            "company_domain": "",
        })
        self.assertIn(result["risk_level"], {"HIGH", "CRITICAL"})
        self.assertLessEqual(result["hybrid_trust_score"], 30.0)

    def test_scorer_flags_task_scam(self):
        result = self.scorer.analyze({
            "text": "Part time online work. Like YouTube videos and earn Rs. 2000 per day. Daily withdrawal via GPay.",
            "company_url": "",
            "company_domain": "",
        })
        self.assertIn(result["risk_level"], {"HIGH", "CRITICAL"})
        self.assertLessEqual(result["hybrid_trust_score"], 30.0)

    def test_scorer_scores_high_trust_for_real_job_posting(self):
        result = self.scorer.analyze({
            "text": (
                "About Us: TechCorp is a leading enterprise software provider. "
                "Role Overview: We are looking for a Senior Frontend Engineer to lead our web team. "
                "Responsibilities include architecting responsive UI components and collaborating with product managers. "
                "Requirements: Bachelor's degree in Computer Science and proficiency in JavaScript and CSS."
            ),
            "company_url": "https://linkedin.com/jobs/view/123456",
            "company_domain": "linkedin.com",
        })
        self.assertEqual(result["risk_level"], "LOW")
        self.assertGreaterEqual(result["hybrid_trust_score"], 75.0)

    # 5. Scraper Tests
    def test_scraper_rejects_empty_or_invalid_url(self):
        response = URLScraper().scrape("   ")
        self.assertFalse(response["success"])


if __name__ == "__main__":
    unittest.main()

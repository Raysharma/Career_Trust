# CareerTrust AI — Multi-Layer Job Fraud Intelligence System

CareerTrust AI is a full-stack job posting fraud detection system. It employs a **Multi-Factor Trust Scoring** engine combining:
1. **Contextual NLP Deep Learning**: A fine-tuned DistilBERT transformer that understands semantic context and red flags in job descriptions.
2. **Recruiter Authenticity & Impersonation Scanners**: Detects recruiter free-email scams (`@gmail.com`), WhatsApp/Telegram redirects, and company domain mismatches.
3. **Company Web Infrastructure Verification**: Real-time checkers for domain registration age (WHOIS), SSL certificate validity, website reachability, and lookalike domain patterns.
4. **Calibrated Financial & Red-Flag Scanners**: Deep heuristics detecting upfront payment/registration fees, task/rating/crypto scams, urgency pressure, and structural vagueness.

Scan histories are logged asynchronously to a **MongoDB** database, powering an interactive recent-scans dashboard on the frontend.

---

## Architecture Overview

```
                          Job Posting Input (URL / Text)
                                       │
         ┌─────────────────────────────┼─────────────────────────────┐
         ▼                             ▼                             ▼
   Text Heuristics                DistilBERT                Domain & Recruiter
 (Upfront Fees, Tasks,         Context Classifier          (WHOIS Age, SSL Status,
  Urgency, Vagueness)           (Semantic Model)          WhatsApp/Gmail Mismatch)
         │                             │                             │
         ▼                             ▼                             ▼
     text_trust                    bert_trust                  infra_trust
         │                             │                             │
         └─────────────────────────────┼─────────────────────────────┘
                                       ▼
                             Multi-Signal Fusion
                                       │
                                       ▼
                           Hybrid Trust Score (0-100)
                           + Risk Rating + Report
                                       │
                       ┌───────────────┴───────────────┐
                       ▼                               ▼
               Logged to MongoDB             Rendered on Frontend
              (Scan History List)             (Detailed Analytics)
```

---

## Directory Layout

```
Career_Trust/
│
├── main.py                       # FastAPI server (includes DB logging & /history endpoint)
│
├── src/                          # Backend application source code
│   ├── __init__.py
│   ├── db.py                     # MongoDB helper functions (connection & logs query)
│   ├── scorer.py                 # HybridScorer (combines BERT + multi-factor checks)
│   ├── scraper.py                # URLScraper (BeautifulSoup parser with anti-bot fallback)
│   └── extractors/               # Heuristic feature pipelines
│       ├── __init__.py
│       ├── text.py               # Upfront fees, task/crypto scams, urgency patterns
│       ├── domain.py             # WHOIS age, SSL validity, lookalike domain checks
│       └── contact.py            # Free webmail, WhatsApp/Telegram redirects, ATS safety
│
├── frontend/                     # Web User Interface
│   ├── index.html                # Glassmorphism layout (Analyze & Recent Scans tabs)
│   ├── style.css                 # Dark theme visual styling
│   └── app.js                    # Web controller managing fetches & view toggles
│
├── fraud_job_model/              # Fine-tuned Transformer Weights
│   └── final_model/              # Production DistilBERT model & tokenizer
│
├── training/                     # Standalone ML training scripts
│   └── train_bert.py             # Fine-tunes DistilBERT classification weights
│
├── tests/                        # Automated unit & integration tests
│   └── test_core.py              # Test suite for scoring accuracy & scam detection
│
├── .env.example                  # Environment configuration template
├── requirements.txt              # Project package requirements
└── README.md                     # Documentation
```

---

## Setup & Installation

### 1. Configure the Environment
Clone the repository, create a virtual environment, and install the required dependencies:

```bash
# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .\.venv\Scripts\activate

# Install requirements
pip install -r requirements.txt
```

### 2. Set Up Database Credentials
1. Copy the `.env.example` file to `.env`:
   ```bash
   cp .env.example .env
   ```
2. Open `.env` and fill in your MongoDB connection string:
   ```env
   MONGO_URI="mongodb+srv://<username>:<password>@<cluster>.mongodb.net/?appName=<app>"
   ```
   *Note: If no connection string is provided or the connection fails, the application automatically runs in a database-disabled fallback mode, and scans won't be saved.*

---

## Running the Application

### 1. Start the FastAPI Backend
Launch the server using Python or uvicorn:
```bash
# From the project root
python main.py

# Alternatively, run via uvicorn directly
uvicorn main:app --reload --port 8081
```
The server starts on `http://127.0.0.1:8081`. You can view the interactive Swagger documentation at `http://127.0.0.1:8081/docs`.

### 2. Open the Frontend
Since the frontend consists of static assets, you can run it directly:
* Double-click `frontend/index.html` to open it in your browser, OR
* Host it using Python's built-in HTTP server:
  ```bash
  python -m http.server 8000 --directory frontend
  ```
  Then navigate to `http://127.0.0.1:8000`.

---

## Running Tests

Run the automated test suite to verify detection accuracy and false positive prevention:
```bash
python -m unittest tests/test_core.py
```

---

## System Capabilities & Fraud Detection Vectors

- **LinkedIn & Job Board Impersonation**: Even when posted on trusted job boards (LinkedIn, Internshala, Indeed), the engine detects recruiter contact mismatches (e.g. asking candidates to email `@gmail.com` or join WhatsApp/Telegram groups).
- **Upfront Fee & Financial Scams**: Detects demands for registration fees, training charges, laptop security deposits, or background check fees.
- **Task & Daily Payout Fraud**: Identifies fake freelance tasks (video liking, rating hotels/apps, crypto payouts).
- **Domain & SSL Infrastructure**: Analyzes domain registration age (<30 days = critical risk), SSL certificate validity, and lookalike domain patterns.
- **ATS Safe Scoring**: Legitimate corporate jobs (which typically lack direct email/phone in description text) are not falsely penalized.

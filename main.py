"""
FastAPI server wrapping the HybridScorer, URLScraper, and MongoDB logging.
Exposes endpoints for text analysis, URL analysis, and scanning history.
"""

import sys
import os
from fastapi import FastAPI, HTTPException
from fastapi import BackgroundTasks
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel
from typing import Optional
from fastapi.middleware.cors import CORSMiddleware

# Ensure the project root is in the path
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Fix Windows console encoding if needed
if sys.stdout and getattr(sys.stdout, 'encoding', None) and sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

from src.scorer import HybridScorer
from src.scraper import URLScraper
from src import db

app = FastAPI(title="CareerTrust Job Fraud Detection API", version="2.0")

cors_origins_env = os.getenv("CORS_ORIGINS", "http://127.0.0.1:8000,http://localhost:8000")
cors_origins = [origin.strip() for origin in cors_origins_env.split(",") if origin.strip()]
if not cors_origins:
    cors_origins = ["http://127.0.0.1:8000", "http://localhost:8000"]

# Enable CORS for frontend requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load pipelines on startup
scorer = HybridScorer()
scraper = URLScraper()

class JobRequest(BaseModel):
    text: str
    company_url: Optional[str] = ""
    company_domain: Optional[str] = ""

class URLRequest(BaseModel):
    url: str

@app.get("/")
def read_root():
    return {
        "status": "online",
        "name": "CareerTrust API",
        "database_connected": db.is_db_active(),
        "bert_model_loaded": scorer.bert_available
    }

@app.post("/analyze")
async def analyze_job(request: JobRequest, background_tasks: BackgroundTasks):
    # Perform scoring
    payload = {
        'text': request.text,
        'company_url': request.company_url,
        'company_domain': request.company_domain
    }

    result = await run_in_threadpool(scorer.analyze, payload)
    
    # Persist the scan after the response is ready.
    background_tasks.add_task(db.save_scan, payload, result)
    
    # Return result
    return result

@app.post("/analyze_url")
async def analyze_url(request: URLRequest, background_tasks: BackgroundTasks):
    # 1. Scrape the URL
    scraped_data = await run_in_threadpool(scraper.scrape, request.url)
    
    if not scraped_data['success']:
        raise HTTPException(status_code=400, detail=f"Failed to scrape URL: {scraped_data['error']}")
        
    # 2. Score the scraped text and domain
    payload = {
        'text': scraped_data['text'],
        'company_url': scraped_data['url'],
        'company_domain': scraped_data['domain']
    }

    result = await run_in_threadpool(scorer.analyze, payload)
    
    # Include metadata for frontend
    result['extracted_domain'] = scraped_data['domain']
    result['scraped_url'] = scraped_data['url']
    
    # 3. Log to MongoDB
    background_tasks.add_task(
        db.save_scan,
        {
            'text': scraped_data['text'],
            'company_url': scraped_data['url'],
            'company_domain': scraped_data['domain'],
            'url': scraped_data['url']
        },
        result
    )
    
    return result

@app.get("/history")
def get_history(limit: int = 10):
    """Retrieves the recent scan history log from MongoDB."""
    limit = max(1, min(int(limit), 100))
    recent_scans = db.get_recent_scans(limit=limit)
    return {
        "success": True,
        "database_active": db.is_db_active(),
        "count": len(recent_scans),
        "history": recent_scans
    }

if __name__ == "__main__":
    import uvicorn
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8081"))
    reload_mode = os.getenv("UVICORN_RELOAD", "false").lower() == "true"
    print(f"🚀 Starting CareerTrust API server on http://{host}:{port}")
    uvicorn.run("main:app", host=host, port=port, reload=reload_mode)

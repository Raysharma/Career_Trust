const API_URL = window.CAREERTRUST_API_URL || 'http://127.0.0.1:8081';
let activeInputTab = 'url'; // 'url' or 'text'
let activeView = 'scanner'; // 'scanner' or 'history'

// Navigation between main views (Scan vs History)
const btnNavScan = document.getElementById('btn-nav-scan');
const btnNavHistory = document.getElementById('btn-nav-history');
const viewScanner = document.getElementById('view-scanner');
const viewHistory = document.getElementById('view-history');

btnNavScan.addEventListener('click', () => {
    activeView = 'scanner';
    btnNavScan.classList.add('active');
    btnNavHistory.classList.remove('active');
    viewScanner.style.display = 'block';
    viewHistory.style.display = 'none';
});

btnNavHistory.addEventListener('click', () => {
    activeView = 'history';
    btnNavHistory.classList.add('active');
    btnNavScan.classList.remove('active');
    viewScanner.style.display = 'none';
    viewHistory.style.display = 'block';
    loadHistory();
});

// Navigation between input modes (URL vs Paste Text)
document.getElementById('tab-url').addEventListener('click', () => {
    activeInputTab = 'url';
    document.getElementById('tab-url').classList.add('active');
    document.getElementById('tab-text').classList.remove('active');
    document.getElementById('url-input-section').style.display = 'block';
    document.getElementById('text-input-section').style.display = 'none';
});

document.getElementById('tab-text').addEventListener('click', () => {
    activeInputTab = 'text';
    document.getElementById('tab-text').classList.add('active');
    document.getElementById('tab-url').classList.remove('active');
    document.getElementById('text-input-section').style.display = 'block';
    document.getElementById('url-input-section').style.display = 'none';
});

// Initialize database status check
async function checkDbStatus() {
    const badge = document.getElementById('db-status');
    const badgeText = document.getElementById('db-status-text');
    try {
        const response = await fetch(`${API_URL}/`);
        if (response.ok) {
            const data = await response.json();
            if (data.database_connected) {
                badge.className = 'db-status-badge connected';
                badgeText.innerText = 'Database Connected';
            } else {
                badge.className = 'db-status-badge disconnected';
                badgeText.innerText = 'Database Offline (Rules Mode)';
            }
        }
    } catch (e) {
        badge.className = 'db-status-badge disconnected';
        badgeText.innerText = 'Server Offline';
    }
}

// Fetch scan history list
async function loadHistory() {
    const container = document.getElementById('history-container');
    container.textContent = '';
    const loading = document.createElement('div');
    loading.className = 'history-loading';
    loading.textContent = 'Fetching scan history logs...';
    container.appendChild(loading);
    
    try {
        const response = await fetch(`${API_URL}/history`);
        if (!response.ok) throw new Error("Failed to fetch history");
        
        const data = await response.json();
        container.textContent = '';
        
        if (!data.history || data.history.length === 0) {
            const empty = document.createElement('div');
            empty.className = 'history-empty';
            empty.textContent = 'No recent scans found. Create one to see it here!';
            container.appendChild(empty);
            return;
        }

        data.history.forEach(item => {
            const input = item.input || {};
            const results = item.results || {};
            const historyItem = document.createElement('div');
            historyItem.className = 'history-item';
            
            // Format Timestamp
            const dateStr = item.timestamp 
                ? new Date(item.timestamp).toLocaleString(undefined, {
                    month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit'
                  }) 
                : 'Unknown Date';
            
            // Define source display (URL vs manual snippet)
            const sourceDisplay = input.url || input.company_url || 'Pasted Job Description';
            const snippet = input.text 
                ? (input.text.length > 80 ? input.text.substring(0, 80) + '...' : input.text)
                : 'No description text';

            // Risk color classes
            let riskClass = 'badge-low';
            if (results.risk_level === 'CRITICAL') riskClass = 'badge-critical';
            else if (results.risk_level === 'HIGH') riskClass = 'badge-high';
            else if (results.risk_level === 'MEDIUM') riskClass = 'badge-medium';

            const left = document.createElement('div');
            left.className = 'history-item-left';

            const title = document.createElement('div');
            title.className = 'history-title';
            title.textContent = sourceDisplay;

            const meta = document.createElement('div');
            meta.className = 'history-meta';

            const dateMeta = document.createElement('span');
            dateMeta.textContent = `📅 ${dateStr}`;

            const snippetMeta = document.createElement('span');
            snippetMeta.textContent = `📄 ${snippet}`;

            meta.append(dateMeta, snippetMeta);
            left.append(title, meta);

            const right = document.createElement('div');
            right.className = 'history-item-right';

            const riskBadge = document.createElement('div');
            riskBadge.className = `history-risk-badge ${riskClass}`;
            riskBadge.textContent = results.risk_level || 'UNKNOWN';

            const scoreBadge = document.createElement('div');
            scoreBadge.className = 'history-score-badge';
            scoreBadge.textContent = Math.round(results.hybrid_trust_score || 0);

            right.append(riskBadge, scoreBadge);
            historyItem.append(left, right);
            
            // Load scan details on click
            historyItem.addEventListener('click', () => {
                // Switch back to scan view
                activeView = 'scanner';
                btnNavScan.classList.add('active');
                btnNavHistory.classList.remove('active');
                viewScanner.style.display = 'block';
                viewHistory.style.display = 'none';
                
                // Render results
                renderResults(results);
            });
            
            container.appendChild(historyItem);
        });
    } catch (error) {
        container.textContent = '';
        const errorState = document.createElement('div');
        errorState.className = 'history-empty';
        errorState.textContent = '⚠️ Failed to connect to server history database.';
        container.appendChild(errorState);
        console.error(error);
    }
}

// Refresh history button listener
document.getElementById('refresh-history-btn').addEventListener('click', loadHistory);

// Perform Analyse Scan
document.getElementById('analyze-btn').addEventListener('click', async () => {
    let endpoint = `${API_URL}/analyze`;
    let payload = {};

    if (activeInputTab === 'url') {
        const url = document.getElementById('job-url').value.trim();
        if (!url) { alert("Please enter a URL."); return; }
        endpoint = `${API_URL}/analyze_url`;
        payload = { url: url };
    } else {
        const text = document.getElementById('job-desc').value.trim();
        const url = document.getElementById('company-url').value.trim();
        if (!text) { alert("Please enter a job description."); return; }
        payload = { text: text, company_url: url };
    }

    // UI Loading State
    const btnText = document.getElementById('btn-text');
    const spinner = document.getElementById('btn-spinner');
    const btn = document.getElementById('analyze-btn');
    const resultsPanel = document.getElementById('results');

    btnText.innerText = "Analyzing...";
    spinner.style.display = "block";
    btn.disabled = true;
    resultsPanel.style.display = "none";

    try {
        const response = await fetch(endpoint, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (!response.ok) {
            const err = await response.json();
            if (err.detail && err.detail.includes("ANTI_BOT_BLOCKED")) {
                alert("⚠️ Anti-Bot Protection Detected!\n\nThe website blocked our scraper from reading the job description.\n\nPlease copy the job description manually and use the 'Paste Text' tab.");
            } else {
                throw new Error(err.detail || "Server error");
            }
            return;
        }
        
        const data = await response.json();
        renderResults(data);
        checkDbStatus(); // Update DB connectivity dot
    } catch (error) {
        alert("Failed to connect to API. Is the server running on port 8081?");
        console.error(error);
    } finally {
        btnText.innerText = "Analyze Job Posting";
        spinner.style.display = "none";
        btn.disabled = false;
    }
});

function renderResults(data) {
    const resultsPanel = document.getElementById('results');
    resultsPanel.style.display = "block";

    // Set Score & Risk Level
    const circle = document.getElementById('trust-score');
    const riskLabel = document.getElementById('risk-level');
    
    circle.innerText = Math.round(data.hybrid_trust_score);
    riskLabel.innerText = data.risk_level + " RISK";

    // Remove old status color classes
    circle.className = "score-circle";
    riskLabel.className = "risk-level";

    // Assign new color classes based on risk level
    let colorClass = "";
    if (data.risk_level === "CRITICAL") colorClass = "status-crit";
    else if (data.risk_level === "HIGH") colorClass = "status-high";
    else if (data.risk_level === "MEDIUM") colorClass = "status-med";
    else colorClass = "status-low";

    circle.classList.add(colorClass);
    riskLabel.classList.add(colorClass);

    // Animate Progress Bars
    animateBar('bert-bar', 'bert-val', data._bert_trust);
    animateBar('text-bar', 'text-val', data._text_trust);
    animateBar('domain-bar', 'domain-val', data._domain_trust);
    animateBar('contact-bar', 'contact-val', data._contact_trust);

    // Populate Explanations
    const list = document.getElementById('reasons-list');
    list.textContent = "";
    
    if (!data.explanation || data.explanation.length === 0) {
        const li = document.createElement('li');
        li.textContent = '✅ No significant issues found.';
        list.appendChild(li);
    } else {
        data.explanation.forEach(reason => {
            const li = document.createElement('li');
            li.textContent = `⚠️ ${reason}`;
            list.appendChild(li);
        });
    }
    
    // Smooth scroll to results
    resultsPanel.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function animateBar(barId, valId, percentage) {
    const bar = document.getElementById(barId);
    const val = document.getElementById(valId);
    
    setTimeout(() => {
        bar.style.width = percentage + "%";
        val.innerText = percentage.toFixed(1) + "%";
        
        // Color coding bars (Low trust = red, High trust = green)
        if (percentage < 35) bar.style.background = "var(--risk-crit)";
        else if (percentage < 55) bar.style.background = "var(--risk-high)";
        else if (percentage < 75) bar.style.background = "var(--risk-med)";
        else bar.style.background = "var(--risk-low)";
    }, 50);
}

// Perform initial connection checks on load
window.addEventListener('DOMContentLoaded', () => {
    checkDbStatus();
});

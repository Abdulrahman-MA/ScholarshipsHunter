# 🎓 Scholarships Hunter: Autonomous Multi-Source Scholarship & Fellowship Intelligence Engine

An enterprise-grade, autonomous scholarship hunting and matching engine built for graduate candidates (MSc/PhD) in **Physics, Theoretical Physics, High-Energy Physics (HEP), Astrophysics, Computational & Plasma Physics**.

Scholarships Hunter continuously crawls, extracts, deduplicates, and evaluates academic opportunities across **8 distinct global portals and broadcast channels** using a multi-key rotating pool of **Groq LPUs (Llama 3.3 70B/120B)** and **Google Gemini Flash**.

---

## 🌟 Key Architecture & Capabilities

```
                                  Scholarships Hunter
                                          │
        ┌──────────────┬──────────────────┼──────────────────┬──────────────┐
        ▼              ▼                  ▼                  ▼              ▼
CatchThatScholarship AIP Physics Master  WhatsApp Live    ProFellow    WeMakeScholars
   (Fast JSON)      (1,200 Programs)    (6 Channels)     (Stealth)     (Multi-Page)
        │              │                  │                  │              │
        └──────────────┴──────────────────┼──────────────────┴──────────────┘
                                          │
                           ┌──────────────┴──────────────┐
                           ▼                             ▼
                   Scholarships Corner             MastersPortal &
                   (WordPress REST API)         Italian Universities (DSU)
                                          │
                                          ▼
                      Isolated Stealth Browser Contexts +
                     PID & Excel (.lock) Concurrency Shield
                                          │
                                          ▼
                      Multi-Key AI Rotation Engine (4 Groq + 5 Gemini)
                     (Pre-Evaluation SQLite Deduplication + 1.5s Rate Pacing)
                                          │
                                          ▼
                       Excel: scholarships_tracker.xlsx
                      (Color-Coded: Green / Yellow / Red)
```

### 1. 8 Multi-Source Crawlers
- **Catch That Scholarship:** High-speed internal JavaScript database extraction (filtered for Non-EU/Egypt/STEM eligibility).
- **GradSchoolShopper:** Live AIP (American Institute of Physics) directory ingestion across 1,200 graduate programs, pre-filtered for theoretical, particle, cosmology, and quantum tracks.
- **WhatsApp Multi-Channel Live:** Automated single-session Playwright crawler traversing 6 followed scholarship broadcast channels.
- **ProFellow:** Stealth Chromium crawler equipped to bypass Cloudflare Turnstile, deeply extracting science and graduate fellowship cards.
- **WeMakeScholars:** Multi-page pagination scraper with dynamic lazy-load hydration for Physics and Applied Sciences.
- **Scholarships Corner:** High-throughput WordPress REST API extractor pulling hundreds of verified scholarship posts per minute.
- **MastersPortal (Physics & Astronomy):** Automated search directory sweep extracting university-funded MSc degree programs.
- **Hussain Silat (Italy Public Universities):** Complete directory parser binding all 67 Italian public universities to Regional DSU Full-Ride grant metadata.

### 2. Multi-Key Rotating AI Pool (Groq 120B + Gemini Flash)
- **Zero Rate-Limit Bottlenecks:** Configured with an auto-cycling pool of API keys (Groq LPU + Google Gemini). If a key encounters a `429: Rate Limit Exceeded`, the system instantly fails over to the next healthy key in the pool.
- **Smooth Rate-Pacing:** Implements an automatic 1.5-second pacing delay between LLM evaluations to prevent hitting tokens-per-minute burst limits.
- **Strict Zero-Deletion Audit Compliance:** Every opportunity—including disqualified or 0/Red matches—is committed to Excel with full AI reasoning, ensuring transparent tracking.

### 3. Concurrency & Fault Tolerance
- **PID Process Locks:** Multi-terminal locking prevents competing command-prompt windows from evaluating the same backlog queue.
- **Pre-Evaluation Deduplication:** Cross-checks SQLite (`processed_hashes`) before dispatching LLM calls—saving 100% of tokens on items already evaluated.
- **File-Level Excel Locking:** Robust `.lock` mechanism prevents collisions when multiple asynchronous scrapers write to `scholarships_tracker.xlsx`.

---

## 🚀 Quickstart Guide

### 1. Clone the Repository
```bash
git clone https://github.com/your-username/ScholarshipsHunter.git
cd ScholarshipsHunter
```

### 2. Set Up Virtual Environment & Dependencies
```bash
# Create virtual environment
python -m venv .venv

# Activate environment (Windows PowerShell)
.venv\Scripts\Activate.ps1

# Install required dependencies
pip install -r requirements.txt

# Install Playwright browser binaries
playwright install chromium
```

### 3. Configure Your Environment Variables
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
Open `.env` and add your API keys:
```env
# Comma-separated list of keys for automatic failover rotation
GROQ_API_KEYS=gsk_your_key_1,gsk_your_key_2
GEMINI_API_KEYS=your_gemini_key_1,your_gemini_key_2

# Optional: Local Ollama mode
USE_OLLAMA=False
OLLAMA_MODEL=llama3.1
```

---

## 🖥️ Running Scholarships Hunter

### Option A: The Interactive Control Panel (Recommended for Windows)
Double-click `HunterMenu.bat` (or run it in your terminal) to open the control panel:

```
==================================================
      SCHOLARSHIPS HUNTER - CONTROL PANEL
==================================================
 [1]  Run WhatsApp Multi-Channel Live Scraper (6 Channels)
 [2]  Run Catch That Scholarship (Fast JSON)
 [3]  Run GradSchoolShopper (Fast CSV)
 [4]  Run ProFellow (Hybrid Browser/AI)
 [5]  Run WeMakeScholars (Hybrid Browser/AI)
 [6]  Run Scholarships Corner (Fast REST API)
 [7]  Run MastersPortal (Hybrid Browser/AI)
 [8]  Run Hussain Silat (Italian Public Universities Directory)
 [9]  Process Pending Backlog Queue (Ultra-Fast Groq AI)
 [10] Run ALL Scrapers Concurrently (Async Orchestrator)
 [11] Launch Browser for Auto-Preload and Manual Logins
 [12] Clean Excel Sheet (Interactive cleaner)
 [13] Manual Link Evaluator (Instant AI URL assessment)
 [14] Run Deep AI Website Evaluator (Full page validation)
 [15] Exit
```

### Option B: The Automated Async Orchestrator
Run all 8 scrapers in parallel with real-time streaming status:
```bash
python run_all.py
```

### Option C: Individual Targeted Sweeps
```bash
# Sweep Scholarships Corner (7 pages, 50 posts/page)
python src/scrapers/scholarshipscorner.py --pages 7 --per-page 50

# Sweep MastersPortal across Physics (5 pages)
python src/scrapers/mastersportal.py --pages 5 --discipline physics

# Sweep WeMakeScholars across Physics (4 pages)
python src/scrapers/wemakescholars.py --pages 4 --category physics

# Sweep ProFellow Fellowships (4 pages)
python src/scrapers/profellow.py --pages 4

# Evaluate any pending queue items
python src/main.py --mode backlog
```

---

## 📊 Excel Output Structure (`scholarships_tracker.xlsx`)

Evaluated opportunities are exported and styled with automatic conditional formatting:

| Column | Description |
| :--- | :--- |
| **Category** | 🟢 `Green` (Score $\ge 75$, Top Fit) \| 🟡 `Yellow` (Score $50-74$) \| 🔴 `Red` (Score $< 50$) |
| **Title** | Opportunity / Fellowship Name |
| **Type** | Degree level (MSc, PhD, Research Fellowship, Internship) |
| **Deadline** | Verified deadline or application cycle call |
| **Funding** | Fully Funded (Tuition + Stipend + Airfare) / Partial / DSU Regional |
| **Fields** | Extracted academic specialties |
| **Link** | Clickable hyperlink to official application portal |
| **Action Items** | Immediate next step required from the applicant |
| **Institution/Country**| Host university or country |
| **Scraped Date** | Date of capture |
| **Web Source** | Platform origin |
| **Match Score** | Fit score from $0$ to $100$ |
| **AI Rationale** | Concise explanation of match score and funding guarantee |
| **Deep Checked** | Full-page deep verification indicator |

---

## 🔒 Privacy & Security

- **Zero Hardcoded Secrets:** All API keys are loaded strictly from `.env` or system environment variables.
- **Session Protection:** All browser cache directories (`data/*_session/`) and WhatsApp Web credentials are strictly excluded via `.gitignore`.
- **Concurrency Locks:** Distributed `.lock` files prevent conflicting read/writes between processes.

---

## 📄 License
MIT License. Free for academic, personal, and open-source use.

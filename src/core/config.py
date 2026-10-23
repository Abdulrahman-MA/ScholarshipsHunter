import os
from dotenv import load_dotenv

# Load variables from .env file if present
load_dotenv()

# Multi-Key Rotation Pools (Cycle seamlessly on rate limit / 429 quota exhaustion)
# Loaded dynamically from environment or .env file (comma-separated list)
_raw_groq = os.getenv("GROQ_API_KEYS", "") or os.getenv("GROQ_API_KEY", "")
GROQ_API_KEYS = [k.strip() for k in _raw_groq.split(",") if k.strip()]

_raw_gemini = os.getenv("GEMINI_API_KEYS", "") or os.getenv("GEMINI_API_KEY", "")
GEMINI_API_KEYS = [k.strip() for k in _raw_gemini.split(",") if k.strip()]

# Backward compatibility defaults
GROQ_API_KEY = GROQ_API_KEYS[0] if GROQ_API_KEYS else ""
GEMINI_API_KEY = GEMINI_API_KEYS[0] if GEMINI_API_KEYS else ""

# Local AI Configuration (Ollama)
USE_OLLAMA = os.getenv("USE_OLLAMA", "False").lower() in ("true", "1", "yes")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1")

# Applicant Profile configuration
APPLICANT_PROFILE = """
* **Name:** Abdulrahman Mohamed Anwar
* **Degree & University:** B.Sc. in Physics, Faculty of Science, Ain Shams University, Cairo, Egypt (Graduated June 2026).
* **Cumulative GPA:** **3.114 / 4.0** (Grade: B).
* **Nationality / Citizenship:** Egyptian (Non-EU / Global South).
* **Target Opportunities:** 
  * Fully Funded Master's Degrees (MSc)
  * Pre-Master / Postgraduate Diplomas (e.g., ICTP)
  * Fully Funded Research Internships & Fellowships (e.g., OIST, CERN, DESY, Helmholtz)
  * Academic Summer / Winter Schools
* **Target Disciplines:**
  * **Tier 1 (Highest Priority):** Theoretical Physics, High-Energy Physics (HEP), Particle Physics, Cosmology, General Relativity, Astrophysics, Computational Physics, Plasma Physics.
  * **Tier 2 (High Priority):** Scientific Computing, Applied Mathematics, Quantum Information, Atmospheric/Meteorological Modeling.
  * **Tier 3 (Low Priority):** General Engineering Physics, Materials Science, Data Science / Machine Learning.
  * **Disqualified:** Electronics engineering, Medicine, Pharmacy, Pure Humanities/Business (unless high-prestige general fellowship).
* **Funding Constraints:**
  * **Must be:** 100% Fully Funded (Tuition waiver + living stipend + travel) OR Low/Zero tuition with proven living support (e.g., Italian DSU, German public universities with student working rights).
  * **Exclude:** Self-funded programs, partial tuition waivers with no living stipend, or programs requiring steep upfront application fees without fee waivers.
* **Language Status:** Native Arabic, Lower Advanced English (IELTS target 7.5-8.5 in progress; English medium of instruction certificate available).
"""

# App configuration
# BASE_DIR is the root folder (D:\Apps\GItHubRebo\Mine\whatsapp_scholarship_filter)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Data storage (hidden away from the main view)
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

# Important outputs (in root folder as requested)
OUTPUT_EXCEL_FILE = os.path.join(BASE_DIR, "scholarships_tracker.xlsx")

# System tracking files (inside data directory)
RAW_MESSAGES_FILE = os.path.join(DATA_DIR, "raw_messages.txt")
PROCESSED_DB_FILE = os.path.join(DATA_DIR, "processed_history.txt") # Legacy
PROCESSED_SQLITE_DB = os.path.join(DATA_DIR, "processed_history.db") # New multi-scraper DB
DLQ_FILE = os.path.join(DATA_DIR, "dead_letter_queue.jsonl") # Failed messages log
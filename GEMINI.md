# ScholarshipsHunter Workspace Guidelines & Privacy Invariants

## 1. Zero Secret & Dossier Leaks to Git
* **Never Commit Personal Profiles:** Any applicant CV or master dossier matching `*PROFILE*.md` or `*Profile*.md` contains private personal history, grades, and phone/email contacts. These must remain strictly local and excluded via `.gitignore`.
* **Never Commit Active Trackers:** `*.xlsx` and `*.xls` files (such as `scholarships_tracker.xlsx`) represent user output and private applicant shortlists. They must never be tracked in version control.
* **Never Commit Browser Sessions:** Caches in `data/*_session/` and `data/whatsapp_session/` contain live authentication cookies and must remain untracked.
* **Clean Git History:** If sensitive files or personal spreadsheets are ever staged by mistake, purge them using `git rm --cached` and amend the commit (`git commit --amend`) rather than leaving them in git log history.

## 2. API Key Management
* Never hardcode Groq or Gemini API keys in source files (`config.py`, `matcher.py`).
* Always read from environment variables or `.env` using multi-key rotation pools with automatic 429 failover.
* Commit only `.env.example` with dummy placeholders.

## 3. Data Integrity & Concurrency
* Adhere strictly to the rules in `.agent/skills/SCRAPING_PLAYBOOK.md`.
* Never write to `processed_history.db` before an opportunity has successfully reached Excel.
* Backlog queue evaluations must respect the PID lock in `data/backlog_evaluation.lock`.

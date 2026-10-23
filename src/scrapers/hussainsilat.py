import os
import sys
import time
import json
import sqlite3
import hashlib
import argparse
import urllib.request
import ssl
from bs4 import BeautifulSoup

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core import config

def get_hash(text):
    return hashlib.md5(text.strip().encode('utf-8')).hexdigest()

def fetch_page_html(url):
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    }
    
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, context=ctx, timeout=30) as resp:
        return resp.read().decode('utf-8', errors='replace')

def run():
    parser = argparse.ArgumentParser(description="Hussain Silat Italian Public Universities Directory Scraper")
    parser.add_argument("--no-eval", action="store_true", help="Skip running main.py backlog evaluation after scraping")
    args = parser.parse_args()
    
    print("=" * 60)
    print(" 🎯 PIPELINE TEST: Hussain Silat (Target #7) ")
    print(" URL: https://hussainsilat.com/italian-public-universities/")
    print(" Mode: Fast HTML Table Extraction + DSU Regional Metadata + AI Backlog")
    print("=" * 60)
    
    target_url = "https://hussainsilat.com/italian-public-universities/"
    
    # -------------------------------------------------------------
    # Step 1: Fetch Directory HTML
    # -------------------------------------------------------------
    print(f"\n[Step 1/5] Connecting to Italian Universities Directory: {target_url}")
    try:
        html_content = fetch_page_html(target_url)
        print(f"  -> Successfully downloaded directory page ({len(html_content):,} bytes).")
    except Exception as e:
        print(f"  [!] Failed to fetch {target_url}: {e}")
        local_cache = os.path.join(config.DATA_DIR, "hussainsilat.html")
        if os.path.exists(local_cache):
            print(f"  -> Falling back to local cached copy: {local_cache}")
            with open(local_cache, "r", encoding="utf-8", errors="replace") as f:
                html_content = f.read()
        else:
            print("  [!] No local cache available. Exiting scraper.")
            return

    # -------------------------------------------------------------
    # Step 2: Parse Directory Table
    # -------------------------------------------------------------
    print("\n[Step 2/5] Parsing HTML table structure for public universities...")
    soup = BeautifulSoup(html_content, 'html.parser')
    table = soup.find('table')
    if not table:
        print("  [!] No table found on the page.")
        return
        
    rows = table.find_all('tr')
    print(f"  -> Discovered table with {len(rows)} total rows.")
    
    conn = sqlite3.connect(config.PROCESSED_SQLITE_DB)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS processed_hashes (hash TEXT PRIMARY KEY)''')
    
    BACKLOG_FILE = os.path.join(config.DATA_DIR, "scraped_backlog.json")
    queue = []
    if os.path.exists(BACKLOG_FILE):
        try:
            with open(BACKLOG_FILE, 'r', encoding='utf-8') as f:
                queue = json.load(f)
        except Exception:
            queue = []
            
    existing_texts = {m.get("text", "") for m in queue}
    new_count = 0
    scraped_count = 0
    
    # -------------------------------------------------------------
    # Step 3 & 4: Extract Metadata & Bind DSU Funding Structure
    # -------------------------------------------------------------
    print("\n[Step 3/5] Extracting university application portals, admission fees, and EMI waivers...")
    print("[Step 4/5] Binding Italian Regional DSU Full-Ride scholarship metadata...")
    
    for r in rows[1:]:
        tds = r.find_all('td')
        if len(tds) < 9:
            continue
            
        uni_name = tds[1].text.strip()
        if not uni_name or "whatsapp" in uni_name.lower() or "facebook" in uni_name.lower():
            continue
            
        # Extract application portal link
        app_link = ""
        a_tag = tds[2].find('a')
        if a_tag and a_tag.get('href'):
            app_link = a_tag['href'].strip()
            
        # Extract blog guide link
        blog_link = ""
        if len(tds) > 3:
            b_tag = tds[3].find('a')
            if b_tag and b_tag.get('href'):
                blog_link = b_tag['href'].strip()
                
        primary_link = app_link or blog_link or target_url
        
        fee = tds[4].text.strip() if len(tds) > 4 else "Unspecified"
        eng_cert = tds[5].text.strip() if len(tds) > 5 else "English Proficiency"
        admission_date = tds[6].text.strip() if len(tds) > 6 else ""
        deadline = tds[7].text.strip() if len(tds) > 7 else ""
        status = tds[8].text.strip() if len(tds) > 8 else "Upcoming"
        cgpa_req = tds[9].text.strip() if len(tds) > 9 else "No strict CGPA requirement"
        
        scraped_count += 1
        
        # Unique identifier hash
        unique_key = f"Italy_Uni_{uni_name}_{primary_link}"
        item_hash = get_hash(unique_key)
        
        cursor.execute("SELECT 1 FROM processed_hashes WHERE hash = ?", (item_hash,))
        if cursor.fetchone():
            continue # Already in SQLite
            
        deadline_text = deadline if deadline else "Check university portal / Rolling admission calls"
        start_text = admission_date if admission_date else "Check portal"
        
        text_to_eval = (
            f"Opportunity: {uni_name} - Master of Science & Regional DSU Scholarship\n"
            f"Institution / Country: {uni_name}, Italy\n"
            f"Official Application Portal: {primary_link}\n"
            f"Blog Tutorial / Guide: {blog_link if blog_link else 'N/A'}\n"
            f"Admission Application Fee: {fee}\n"
            f"English Language Requirement: {eng_cert} (English Proficiency Certificate accepted by most Italian public universities)\n"
            f"Estimated Admission Date: {start_text}\n"
            f"Application Deadline: {deadline_text}\n"
            f"Current Call Status: {status}\n"
            f"Academic / CGPA Requirement: {cgpa_req}\n\n"
            f"Funding & Scholarship Structure:\n"
            f"- Regional DSU Scholarship (Diritto allo Studio Universitario / ER.GO / LazioDiSCo / EDiSU):\n"
            f"  All admitted international students from developing / non-EU nations (including Egypt) with an equivalent family income (ISEE-Parificato) below €25,000 to €30,000 are eligible for full regional support.\n"
            f"  Benefits: 100% Tuition Fee Waiver, Free University Housing / Accommodation Subsidy, Free University Canteen Meals, and an annual cash stipend of approximately €7,000 to €8,500/year.\n"
            f"- University Merit Scholarships: Many Italian public universities offer automatic or competitive institutional merit awards (€5,000 - €10,000/yr) for high-achieving STEM applicants.\n"
            f"Eligible Programs: Master of Science (MSc) taught in English in Physics, Theoretical Physics, Applied & Nuclear Physics, Materials Science, Data Science, and Engineering."
        )
        
        if text_to_eval not in existing_texts:
            msg_dict = {
                "source": "Hussain Silat (Italy Universities)",
                "text": text_to_eval,
                "scraped_date": time.strftime("%Y-%m-%d")
            }
            queue.append(msg_dict)
            existing_texts.add(text_to_eval)
            new_count += 1
            
            cursor.execute("INSERT INTO processed_hashes (hash) VALUES (?)", (item_hash,))
            conn.commit()
            print(f"    + [NEW] {uni_name[:45]} | Fee: {fee} | Deadline: {deadline_text}")
            
    conn.close()
    
    # -------------------------------------------------------------
    # Step 5: Summary & Backlog Queuing
    # -------------------------------------------------------------
    print(f"\n[Step 5/5] Processed {scraped_count} universities. Found {new_count} BRAND NEW opportunities.")
    
    if new_count > 0:
        with open(BACKLOG_FILE, 'w', encoding='utf-8') as f:
            json.dump(queue, f, indent=4, ensure_ascii=False)
        print(f"Successfully queued {new_count} new opportunities to {BACKLOG_FILE}.")
    else:
        print("All universities in directory are already recorded in SQLite.")
        
    print("\n" + "=" * 60)
    print(" ✅ Hussain Silat Pipeline Scrape Finished ")
    print("=" * 60)
    
    # -------------------------------------------------------------
    # AI Evaluation Trigger (if items were queued)
    # -------------------------------------------------------------
    if not args.no_eval and len(queue) > 0:
        print(f"\nStarting AI Evaluation Pipeline for {len(queue)} pending backlog items (Groq 120B)...")
        import subprocess
        subprocess.run([sys.executable, "src/main.py", "--mode", "backlog"])
    elif len(queue) == 0:
        print("\nBacklog queue is currently clear.")

if __name__ == "__main__":
    run()

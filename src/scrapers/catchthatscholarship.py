import urllib.request
import re
import json
import urllib.parse
from datetime import datetime
import sys
import os
import subprocess
import sqlite3
import hashlib

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.matcher import OpportunityExtraction
from core import config
from core import exporter

def get_hash(text):
    return hashlib.md5(text.strip().encode('utf-8')).hexdigest()

def run():
    print("=" * 60)
    print(" 🎯 PIPELINE TEST: Catch That Scholarship (Target #1) ")
    print(" URL: https://catchthatscholarship.com/tools/scholarships/")
    print("=" * 60)
    
    # -------------------------------------------------------------
    # Step 1: Network Request
    # -------------------------------------------------------------
    url = 'https://catchthatscholarship.com/tools/scholarships/'
    print(f"\n[Step 1/5] Fetching directory HTML from: {url}")
    req = urllib.request.Request(url, headers={
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    })
    
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            html = response.read().decode('utf-8', errors='replace')
        print(f"  -> Successfully fetched HTML page ({len(html):,} bytes).")
    except Exception as e:
        print(f"  [!] Failed to connect to CatchThatScholarship: {e}")
        return

    # -------------------------------------------------------------
    # Step 2: Extract embedded JS database
    # -------------------------------------------------------------
    print("\n[Step 2/5] Scanning DOM for inline JavaScript database 'scholarshipDatabase'...")
    match = re.search(r'const\s+scholarshipDatabase\s*=\s*(\[.*?\]);', html, re.DOTALL | re.IGNORECASE)
    if not match:
        print("  [!] Could not locate the 'scholarshipDatabase' variable in the webpage HTML.")
        return
        
    js_array = match.group(1)
    print(f"  -> Found inline JS array string (~{len(js_array):,} characters).")

    # -------------------------------------------------------------
    # Step 3: Parse JS Array into valid JSON via Node.js
    # -------------------------------------------------------------
    print("\n[Step 3/5] Parsing JavaScript object syntax into standard JSON via Node.js engine...")
    node_code = f"""
    const data = {js_array};
    console.log(JSON.stringify(data));
    """
    
    try:
        result = subprocess.run(['node', '-e', node_code], capture_output=True, text=True, encoding='utf-8', check=True)
        db = json.loads(result.stdout)
        print(f"  -> Successfully loaded {len(db):,} raw opportunities from site's internal database.")
    except Exception as e:
        print(f"  [!] Failed to parse JS array with Node.js: {e}")
        return

    # -------------------------------------------------------------
    # Step 4: Profile Filtering (Discipline, Level, Origin)
    # -------------------------------------------------------------
    print("\n[Step 4/5] Applying profile filters to database...")
    print("  * Target Fields: Science, Engineering, IT (Physics, Theoretical, STEM)")
    print("  * Target Levels: Master, PhD, Other")
    print("  * Eligible Origins: All, Non-US, Non-EU, Non-UK, Non-TR (Egypt Eligible)")
    
    valid_origins = ["All", "Non-US", "Non-EU", "Non-UK", "Non-TR"]
    filtered_results = []
    
    for item in db:
        fields = item.get("fields", [])
        levels = item.get("levels", [])
        origin = item.get("origin", "")
        
        # Must be in STEM/Science
        if "Science" not in fields and "Engineering" not in fields and "IT" not in fields:
            continue
            
        # Must cover Master or PhD
        if not any(l in levels for l in ["master", "phd", "other", "all"]):
            continue
            
        # Must be open to Non-EU/Egypt
        if origin not in valid_origins and origin != "":
            continue
            
        filtered_results.append(item)
        
    print(f"  -> {len(filtered_results)} of {len(db)} scholarships matched your academic profile.")

    # -------------------------------------------------------------
    # Step 5: SQLite Deduplication & Excel Export
    # -------------------------------------------------------------
    print(f"\n[Step 5/5] Checking against SQLite database ({config.PROCESSED_SQLITE_DB})...")
    conn = sqlite3.connect(config.PROCESSED_SQLITE_DB)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS processed_hashes (hash TEXT PRIMARY KEY)''')
    
    evaluated_opps = []
    skipped_count = 0
    
    for item in filtered_results:
        title = item.get("title", "Unknown Scholarship")
        amount = item.get("amount", "Unspecified Funding")
        deadline = item.get("deadline", "Check Portal")
        country = item.get("country", "International")
        link = item.get("internal_link", "").strip()
        
        item_hash = get_hash(f"catch_{title}")
        
        cursor.execute("SELECT 1 FROM processed_hashes WHERE hash = ?", (item_hash,))
        if cursor.fetchone():
            skipped_count += 1
            continue
            
        # Resolve deep application or search link
        if not link:
            search_query = urllib.parse.quote_plus(f"{title} scholarship {country}")
            link = f"https://www.google.com/search?q={search_query}"
        elif link.startswith("/"):
            link = f"https://catchthatscholarship.com{link}"
            
        opp = OpportunityExtraction(
            match_score=95,
            category="Green",
            opportunity_title=title,
            opportunity_type="/".join(item.get("levels", [])),
            institution_or_country=country,
            deadline=deadline,
            funding_status=amount,
            fields_of_study=item.get("fields", []),
            application_link=link,
            reasoning="Direct match from CatchThatScholarship directory (STEM/MSc/Egypt eligible).",
            action_items="Review official scholarship link or Google search to verify deadline."
        )
        
        msg_dict = {
            "source": "Catch That Scholarship",
            "text": f"Title: {title}\nAmount: {amount}\nCountry: {country}",
            "scraped_date": datetime.now().strftime("%Y-%m-%d")
        }
        
        evaluated_opps.append({"opp": opp, "msg": msg_dict})
        cursor.execute("INSERT INTO processed_hashes (hash) VALUES (?)", (item_hash,))
        print(f"  + [NEW] {title[:55]} | Country: {country} | Funding: {amount}")
        
    print(f"\n  -> Found {len(evaluated_opps)} brand new scholarships ({skipped_count} already existed in SQLite).")
    
    if evaluated_opps:
        print(f"  -> Exporting {len(evaluated_opps)} new records to {config.OUTPUT_EXCEL_FILE}...")
        exporter.export_to_excel(evaluated_opps, config.OUTPUT_EXCEL_FILE)
        conn.commit()
        print("  -> Export completed successfully!")
    else:
        print("  -> Database is fully up-to-date! No new records needed exporting.")
        
    conn.close()
    print("\n" + "=" * 60)
    print(" ✅ Catch That Scholarship Pipeline Test Finished ")
    print("=" * 60)

if __name__ == "__main__":
    run()

import os
import sys
import hashlib
import sqlite3
import pandas as pd

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core import config

def get_hash(text: str) -> str:
    return hashlib.md5(text.strip().encode('utf-8')).hexdigest()

def reconcile():
    print("=" * 60)
    print(" DATABASE RECONCILIATION & ORPHAN HASH CLEANER ")
    print("=" * 60)
    
    excel_path = config.OUTPUT_EXCEL_FILE
    if not os.path.exists(excel_path):
        print(f"[!] Error: {excel_path} not found.")
        return
        
    print(f"Loading {excel_path}...")
    df = pd.read_excel(excel_path)
    print(f"Total rows currently in Excel: {len(df)}")
    
    db_path = config.PROCESSED_SQLITE_DB
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS processed_hashes (hash TEXT PRIMARY KEY)''')
    
    cursor.execute('SELECT COUNT(*) FROM processed_hashes')
    old_count = cursor.fetchone()[0]
    print(f"Current SQLite hash count: {old_count}")
    
    # 1. Build authoritative valid hashes from Excel
    valid_hashes = set()
    
    for idx, row in df.iterrows():
        link = str(row.get('Link', '')).strip()
        title = str(row.get('Title', '')).strip()
        source = str(row.get('Web Source', '')).strip()
        
        # Link hash
        if link and link.startswith('http'):
            valid_hashes.add(get_hash(link))
            
        # Catch That Scholarship custom hash
        if "Catch That" in source and title:
            valid_hashes.add(get_hash(f"catch_{title}"))
            
        # GradSchoolShopper custom hash
        if "GradSchoolShopper" in source and title:
            # Title format is typically "Specialty at School"
            parts = title.split(' at ')
            if len(parts) == 2:
                specialty, school = parts[0].strip(), parts[1].strip()
                valid_hashes.add(get_hash(f"{school}__Physics_{specialty}"))
                valid_hashes.add(get_hash(f"{school}_Department of Physics_{specialty}"))
            valid_hashes.add(get_hash(title))
            
        # Hussain Silat / MastersPortal / Scholarships Corner
        if link:
            valid_hashes.add(get_hash(link))
            
    print(f"Computed {len(valid_hashes)} authoritative hashes from Excel records.")
    
    # 2. Add GradSchoolShopper all 1200 rows so non-physics programs remain filtered
    gss_csv = os.path.join(config.DATA_DIR, "aip_physics_master.csv")
    if os.path.exists(gss_csv):
        try:
            gss_df = pd.read_csv(gss_csv)
            for _, r in gss_df.iterrows():
                school = str(r.get('School', '')).strip()
                dept = str(r.get('Department', '')).strip()
                spec = str(r.get('Specialty', '')).strip()
                valid_hashes.add(get_hash(f"{school}_{dept}_{spec}"))
            print("Preserved GradSchoolShopper master database hashes.")
        except Exception as e:
            print(f"Note on GSS CSV: {e}")
            
    # 3. Add Catch That Scholarship 79 items
    cts_cache = os.path.join(config.DATA_DIR, "catchthatscholarship_cache.json")
    if os.path.exists(cts_cache):
        try:
            import json
            with open(cts_cache, 'r', encoding='utf-8') as f:
                cts_items = json.load(f)
            for it in cts_items:
                t = it.get('title', '')
                if t:
                    valid_hashes.add(get_hash(f"catch_{t}"))
            print("Preserved Catch That Scholarship database hashes.")
        except Exception:
            pass
            
    # 4. Clean backup SQLite database
    backup_db = db_path + ".bak"
    import shutil
    shutil.copy2(db_path, backup_db)
    print(f"Created safety backup of SQLite database at: {backup_db}")
    
    # Re-insert strictly authoritative hashes
    cursor.execute('DELETE FROM processed_hashes')
    cursor.executemany('INSERT OR IGNORE INTO processed_hashes (hash) VALUES (?)', [(h,) for h in valid_hashes])
    conn.commit()
    
    cursor.execute('SELECT COUNT(*) FROM processed_hashes')
    new_count = cursor.fetchone()[0]
    conn.close()
    
    removed = old_count - new_count
    print("=" * 60)
    print(f"Reconciliation Complete!")
    print(f"Authoritative Hashes Kept: {new_count}")
    print(f"Premature/Orphaned Hashes Removed: {removed}")
    print("=" * 60)
    print("All un-evaluated ProFellow / interrupted links are now freed and ready to be cleanly re-scraped!")

if __name__ == "__main__":
    reconcile()

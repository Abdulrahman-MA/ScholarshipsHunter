import pandas as pd
import datetime
import sys
import os
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
    print(" 🎯 PIPELINE TEST: GradSchoolShopper (Target #2) ")
    print(" URL: https://gradschoolshopper.com/ (AIP Physics Directory)")
    print("=" * 60)
    
    # -------------------------------------------------------------
    # Step 1: Live Master Sheet Fetch
    # -------------------------------------------------------------
    url = 'https://docs.google.com/spreadsheets/d/1T-0dmLaaWsMaT_azrIq5jIflwlp_3XmkYc5pGJdbVCs/export?format=csv&id=1T-0dmLaaWsMaT_azrIq5jIflwlp_3XmkYc5pGJdbVCs&gid=0'
    print(f"\n[Step 1/5] Fetching live AIP Master CSV database from Google Sheets...")
    
    names = ['School', 'Department', 'Specialty', 'PhD_Type', 'Master_Type', 'Campus', 'Acceptance', 'Deadline_Fall', 'Deadline_Spring', 'Unk1', 'Unk2', 'Unk3', 'Unk4', 'Link']
    
    try:
        df = pd.read_csv(url, skiprows=3, names=names)
        print(f"  -> Successfully downloaded CSV table ({len(df):,} total graduate programs).")
    except Exception as e:
        print(f"  [!] Failed to fetch CSV from Google Docs: {e}")
        return
        
    # -------------------------------------------------------------
    # Step 2: Data Cleaning & Preprocessing
    # -------------------------------------------------------------
    print("\n[Step 2/5] Cleaning table records and removing null specialty rows...")
    df = df.dropna(subset=['Specialty'])
    print(f"  -> {len(df):,} programs with valid research specialties.")

    # -------------------------------------------------------------
    # Step 3: Profile Filtering (Theoretical, HEP, Plasma, Astro, etc.)
    # -------------------------------------------------------------
    print("\n[Step 3/5] Applying discipline filters for Applicant Profile...")
    keywords = [
        "theoretic", "high energy", "particle", "cosmology", "relativity", 
        "astrophysic", "computational", "plasma", "quantum", "atmospheric"
    ]
    print(f"  * Target Specialties: {', '.join(keywords)}")
    
    pattern = "|".join(keywords)
    df_filtered = df[df['Specialty'].str.contains(pattern, case=False, na=False)]
    print(f"  -> Found {len(df_filtered):,} programs specifically matching Tier 1 & Tier 2 physics interests.")

    # -------------------------------------------------------------
    # Step 4: SQLite Deduplication
    # -------------------------------------------------------------
    print(f"\n[Step 4/5] Checking against SQLite database ({config.PROCESSED_SQLITE_DB})...")
    conn = sqlite3.connect(config.PROCESSED_SQLITE_DB)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS processed_hashes (hash TEXT PRIMARY KEY)''')
    
    evaluated_opps = []
    skipped_count = 0
    
    for idx, row in df_filtered.iterrows():
        school = str(row['School']).strip()
        dept = str(row['Department']).strip()
        specialty = str(row['Specialty']).strip()
        title = f"{specialty} at {school}"
        acceptance = str(row['Acceptance']).strip() if not pd.isna(row['Acceptance']) else "N/A"
        deadline = str(row['Deadline_Fall']).strip() if not pd.isna(row['Deadline_Fall']) else "Check website"
        link = str(row['Link']).strip() if not pd.isna(row['Link']) and str(row['Link']).startswith('http') else f"https://www.google.com/search?q={school.replace(' ', '+')}+{specialty.replace(' ', '+')}+physics"
        
        phd_type = str(row['PhD_Type'])
        ms_type = str(row['Master_Type'])
        
        types = []
        if any(w in phd_type for w in ["Both", "Theoretical", "Experimental"]): types.append("PhD")
        if any(w in ms_type for w in ["Both", "Terminal", "Enroute"]): types.append("Master")
        type_str = "/".join(types) if types else "MSc/PhD Graduate"
        
        item_hash = get_hash(f"gss_{title}_{link}")
        
        cursor.execute("SELECT 1 FROM processed_hashes WHERE hash = ?", (item_hash,))
        if cursor.fetchone():
            skipped_count += 1
            continue
            
        opp = OpportunityExtraction(
            match_score=90,
            category="Green",
            opportunity_title=f"{specialty} Graduate Program",
            opportunity_type=type_str,
            institution_or_country=school,
            deadline=deadline,
            funding_status="Usually Full Tuition Waiver + Teaching/Research Assistantship (TA/RA)",
            fields_of_study=[specialty],
            application_link=link,
            reasoning=f"Acceptance Rate: {acceptance}. Department: {dept}.",
            action_items="Check department physics portal for TA/RA stipend packages and fee waiver details."
        )
        
        msg_dict = {
            "source": "GradSchoolShopper",
            "text": f"School: {school}\nDept: {dept}\nSpecialty: {specialty}",
            "scraped_date": datetime.datetime.now().strftime("%Y-%m-%d")
        }
        
        evaluated_opps.append({"opp": opp, "msg": msg_dict})
        cursor.execute("INSERT INTO processed_hashes (hash) VALUES (?)", (item_hash,))
        print(f"  + [NEW] {school[:35]} | {specialty[:30]} | Deadline: {deadline}")
        
    print(f"\n  -> Found {len(evaluated_opps)} brand new programs ({skipped_count} already existed in SQLite).")

    # -------------------------------------------------------------
    # Step 5: Excel Export
    # -------------------------------------------------------------
    if evaluated_opps:
        print(f"\n[Step 5/5] Exporting {len(evaluated_opps)} new records to {config.OUTPUT_EXCEL_FILE}...")
        exporter.export_to_excel(evaluated_opps, config.OUTPUT_EXCEL_FILE)
        conn.commit()
        print("  -> Export completed successfully!")
    else:
        print(f"\n[Step 5/5] Database is fully up-to-date! No new records needed exporting.")
        
    conn.close()
    print("\n" + "=" * 60)
    print(" ✅ GradSchoolShopper Pipeline Test Finished ")
    print("=" * 60)

if __name__ == "__main__":
    run()

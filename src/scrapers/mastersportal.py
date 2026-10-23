import os
import sys
import time
import json
import sqlite3
import hashlib
import argparse
from playwright.sync_api import sync_playwright

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core import config

def get_hash(text):
    return hashlib.md5(text.strip().encode('utf-8')).hexdigest()

def run():
    parser = argparse.ArgumentParser(description="MastersPortal Physics Scholarships Scraper")
    parser.add_argument("--pages", type=int, default=1, help="Number of search result pages to sweep (Default: 1)")
    parser.add_argument("--discipline", type=str, default="physics", help="Field slug (Default: physics, e.g. astronomy-space-sciences)")
    parser.add_argument("--no-eval", action="store_true", help="Skip running backlog evaluation after scraping")
    args = parser.parse_args()
    
    discipline = args.discipline.strip()
    
    print("=" * 60)
    print(" 🎯 PIPELINE TEST: MastersPortal (Target #6) ")
    print(f" URL: https://www.mastersportal.com/search/scholarships/master/{discipline}")
    print(f" Mode: Stealth Browser Extraction ({args.pages} page(s), discipline='{discipline}') + AI Backlog")
    print("=" * 60)
    
    # -------------------------------------------------------------
    # Step 1: Launch Persistent Stealth Context
    # -------------------------------------------------------------
    user_data_dir = os.path.join(config.DATA_DIR, "mastersportal_session")
    os.makedirs(user_data_dir, exist_ok=True)
    
    print(f"\n[Step 1/5] Initializing persistent Stealth Chromium context ({user_data_dir})...")
    
    conn = sqlite3.connect(config.PROCESSED_SQLITE_DB)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS processed_hashes (hash TEXT PRIMARY KEY)''')
    
    with sync_playwright() as p:
        browser = p.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            headless=False,
            viewport={'width': 1280, 'height': 800},
            ignore_default_args=["--enable-automation"],
            args=["--disable-blink-features=AutomationControlled"]
        )
        page = browser.new_page()
        
        from playwright_stealth import Stealth
        Stealth().apply_stealth_sync(page)
        
        # -------------------------------------------------------------
        # Step 2 & 3: Navigate Search Pages & Extract Links
        # -------------------------------------------------------------
        print(f"\n[Step 2/5] Sweeping {args.pages} search result page(s) for '{discipline}' Master scholarships...")
        all_links = []
        for current_page in range(1, args.pages + 1):
            if current_page == 1:
                search_url = f"https://www.mastersportal.com/search/scholarships/master/{discipline}"
            else:
                search_url = f"https://www.mastersportal.com/search/scholarships/master/{discipline}?page={current_page}"
                
            print(f"  -> [Page {current_page}/{args.pages}] Fetching: {search_url}")
            try:
                page.goto(search_url, wait_until="domcontentloaded", timeout=45000)
            except Exception as e:
                print(f"    [!] Navigation note: {e}")
                
            time.sleep(5) # Let dynamic cards render
            
            # Check for Cloudflare challenge
            if "Attention Required" in page.title() or "Cloudflare" in page.title():
                print("    [!] Cloudflare verification challenge detected on screen. Waiting 10s for clearance...")
                time.sleep(10)
                
            # Scroll down to trigger lazy loading of scholarship cards
            for _ in range(3):
                page.keyboard.press("PageDown")
                time.sleep(1)
                
            links = page.evaluate('''() => {
                const anchors = Array.from(document.querySelectorAll('a'));
                return anchors
                    .map(a => a.href)
                    .filter(href => href && href.includes('/scholarships/') && !href.includes('/search/') && !href.includes('#'));
            }''')
            
            unique_page_links = list(set(links))
            print(f"    Found {len(unique_page_links)} scholarship links on page {current_page}.")
            all_links.extend(unique_page_links)
            
        unique_links = list(set(all_links))
        print(f"\n[Step 3/5] Discovered {len(unique_links)} unique physics scholarship URLs across {args.pages} page(s).")
        
        # -------------------------------------------------------------
        # Step 4: SQLite & Backlog Deduplication
        # -------------------------------------------------------------
        BACKLOG_FILE = os.path.join(config.DATA_DIR, "scraped_backlog.json")
        queue = []
        if os.path.exists(BACKLOG_FILE):
            try:
                with open(BACKLOG_FILE, 'r', encoding='utf-8') as f:
                    queue = json.load(f)
            except Exception:
                queue = []
                
        backlog_links = {m.get("link", "").strip() for m in queue if m.get("link")}
        existing_texts = {m.get("text", "") for m in queue}
        
        print(f"\n[Step 4/5] Cross-referencing against SQLite and local backlog queue...")
        new_links = []
        for link in unique_links:
            clean_l = link.strip()
            item_hash = get_hash(clean_l)
            cursor.execute("SELECT 1 FROM processed_hashes WHERE hash = ?", (item_hash,))
            if cursor.fetchone():
                continue # Already in SQLite
            if clean_l in backlog_links:
                continue # Already scraped & waiting in queue!
            new_links.append((clean_l, item_hash))
                
        print(f"  -> Found {len(new_links)} BRAND NEW scholarships to deeply scrape ({len(unique_links) - len(new_links)} already processed/queued).")
        
        # -------------------------------------------------------------
        # Step 5: Deep-Page Text Scraping & Backlog Queuing
        # -------------------------------------------------------------
        new_count = 0
        
        if new_links:
            print(f"\n[Step 5/5] Deep-scraping {len(new_links)} new opportunities into backlog queue...")
            for idx, (link, item_hash) in enumerate(new_links):
                print(f"  [{idx+1}/{len(new_links)}] Extracting: {link}")
                try:
                    page.goto(link, wait_until="domcontentloaded", timeout=30000)
                    time.sleep(3)
                    page.keyboard.press("PageDown")
                    time.sleep(1)
                    body_text = page.locator("body").inner_text()
                except Exception as e:
                    print(f"    [!] Failed to read page text: {e}")
                    continue
                    
                if not body_text or len(body_text.strip()) < 50:
                    print("    [!] Page content was empty or blocked. Skipping.")
                    continue
                    
                text_to_eval = f"Source URL: {link}\n\nFull Webpage Content:\n{body_text[:12000]}"
                
                if text_to_eval not in existing_texts:
                    msg_dict = {
                        "source": "MastersPortal",
                        "link": link,
                        "title": link.split('/')[-1].replace('.html', '').replace('-', ' ').title(),
                        "text": text_to_eval,
                        "scraped_date": time.strftime("%Y-%m-%d")
                    }
                    queue.append(msg_dict)
                    existing_texts.add(text_to_eval)
                    new_count += 1
                    print(f"    + Added to AI backlog queue: {link}")
        else:
            print("\n[Step 5/5] No new scholarships to deep-scrape.")
            
        if new_count > 0:
            with open(BACKLOG_FILE, 'w', encoding='utf-8') as f:
                json.dump(queue, f, indent=4, ensure_ascii=False)
            print(f"\nSuccessfully queued {new_count} new MastersPortal scholarships to {BACKLOG_FILE}.")
            
        browser.close()
    conn.close()
    
    print("\n" + "=" * 60)
    print(" ✅ MastersPortal Pipeline Scrape Finished ")
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

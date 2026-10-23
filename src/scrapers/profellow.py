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
    parser = argparse.ArgumentParser(description="ProFellow Hybrid Scraper")
    parser.add_argument("--pages", type=int, default=1, help="Number of search result pages to sweep (Default: 1)")
    parser.add_argument("--no-eval", action="store_true", help="Skip running backlog evaluation after scraping")
    args = parser.parse_args()
    
    print("=" * 60)
    print(" 🎯 PIPELINE TEST: ProFellow (Target #3) ")
    print(" URL: https://www.profellow.com/ (Science & Masters Fellowships)")
    print(f" Mode: Hybrid Browser Extraction ({args.pages} page(s)) + AI Backlog")
    print("=" * 60)
    
    # -------------------------------------------------------------
    # Step 1: Launch Persistent Stealth Browser Context
    # -------------------------------------------------------------
    user_data_dir = os.path.join(config.DATA_DIR, "profellow_session")
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
        
        # Apply Stealth plugin to bypass Cloudflare Turnstile challenge
        from playwright_stealth import Stealth
        Stealth().apply_stealth_sync(page)
        
        # -------------------------------------------------------------
        # Step 2 & 3: Navigate Search Pages & Extract Links
        # -------------------------------------------------------------
        all_links = []
        for current_page in range(1, args.pages + 1):
            if current_page == 1:
                search_url = "https://www.profellow.com/fellowship/?_type=professional-fellowships%2Cmasters-programs&_discipline=science"
            else:
                search_url = f"https://www.profellow.com/fellowship/?_type=professional-fellowships%2Cmasters-programs&_discipline=science&_paged={current_page}"
                
            print(f"\n[Step 2/5] [Page {current_page}/{args.pages}] Navigating to: {search_url}")
            
            try:
                page.goto(search_url, wait_until="domcontentloaded", timeout=45000)
            except Exception as e:
                print(f"  [!] Navigation note: {e}")
                
            print("  -> Waiting 7 seconds for dynamic listing cards to render...")
            time.sleep(7)
            
            # Check for Cloudflare challenge
            if "Attention Required" in page.title() or "Cloudflare" in page.title():
                print("  [!] Cloudflare challenge detected on screen. Waiting 8s for session bypass...")
                time.sleep(8)
                
            links = page.evaluate('''() => {
                const anchors = Array.from(document.querySelectorAll('a'));
                return anchors
                    .map(a => a.href)
                    .filter(href => href && href.includes('/fellowship/') && !href.includes('?_type=') && !href.includes('#'));
            }''')
            print(f"  -> Found {len(set(links))} links on page {current_page}.")
            all_links.extend(links)
            
        unique_links = list(set(all_links))
        print(f"\n[Step 3/5] Discovered {len(unique_links)} unique fellowship opportunity URLs across {args.pages} page(s).")
        
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
                continue # Already evaluated in Excel
            if clean_l in backlog_links:
                continue # Already scraped & waiting in queue!
            new_links.append((clean_l, item_hash))
                
        print(f"  -> Found {len(new_links)} BRAND NEW fellowships to deeply scrape ({len(unique_links) - len(new_links)} already processed/queued).")
        
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
                    body_text = page.locator("body").inner_text()
                except Exception as e:
                    print(f"    [!] Failed to extract page body: {e}")
                    continue
                    
                if not body_text or len(body_text.strip()) < 50:
                    print("    [!] Page body empty or blocked. Skipping.")
                    continue
                    
                text_to_eval = f"Source URL: {link}\n\nFull Webpage Content:\n{body_text[:12000]}"
                
                if text_to_eval not in existing_texts:
                    msg_dict = {
                        "source": "ProFellow",
                        "link": link,
                        "title": title if 'title' in locals() else link.split('/')[-2],
                        "text": text_to_eval,
                        "scraped_date": time.strftime("%Y-%m-%d")
                    }
                    queue.append(msg_dict)
                    existing_texts.add(text_to_eval)
                    new_count += 1
                    print(f"    + Added to AI backlog queue: {link}")
        else:
            print("\n[Step 5/5] No new fellowships to deep-scrape.")
            
        if new_count > 0:
            with open(BACKLOG_FILE, 'w', encoding='utf-8') as f:
                json.dump(queue, f, indent=4, ensure_ascii=False)
            print(f"\nSuccessfully queued {new_count} brand-new ProFellow opportunities to {BACKLOG_FILE}.")
            
        browser.close()
    conn.close()
    
    print("\n" + "=" * 60)
    print(" ✅ ProFellow Pipeline Scrape Finished ")
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

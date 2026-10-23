import os
import sys
import time
import json
import sqlite3
import hashlib
import html
import re
import argparse
import urllib.request
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

def clean_html(raw_html):
    if not raw_html:
        return ""
    soup = BeautifulSoup(raw_html, 'html.parser')
    for s in soup(["script", "style", "noscript"]):
        s.extract()
    text = soup.get_text(separator='\n').strip()
    return re.sub(r'\n\s*\n', '\n\n', text)

def run():
    parser = argparse.ArgumentParser(description="Scholarships Corner WordPress REST API Scraper")
    parser.add_argument("--pages", type=int, default=2, help="Number of archive pages to sweep (Default: 2)")
    parser.add_argument("--per-page", type=int, default=20, help="Number of posts per page (Max: 100, Default: 20)")
    parser.add_argument("--no-eval", action="store_true", help="Skip running backlog evaluation after scraping")
    args = parser.parse_args()
    
    per_page = min(max(args.per_page, 1), 100)
    
    print("=" * 60)
    print(" 🎯 PIPELINE TEST: Scholarships Corner (Target #5) ")
    print(" URL: https://scholarshipscorner.website/ (WordPress REST API)")
    print(f" Mode: Direct API Extraction ({args.pages} page(s) = ~{args.pages * per_page} posts)")
    print("=" * 60)
    
    # -------------------------------------------------------------
    # Step 1 & 2: Setup REST Endpoints and Categories
    # -------------------------------------------------------------
    target_categories = "27,28,2,84,2027,87"
    print("\n[Step 1/5] Initializing REST API endpoint: /wp-json/wp/v2/posts")
    print(f"[Step 2/5] Target Categories: Masters (27), PhD (28), Fellowships (2), Scholarships (84), Fully Funded (2027), Government (87)")
    
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
            
    backlog_links = {m.get("link", "").strip() for m in queue if m.get("link")}
    existing_texts = {m.get("text", "") for m in queue}
    new_count = 0
    total_fetched = 0
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    # -------------------------------------------------------------
    # Step 3: Fetch Posts via REST API
    # -------------------------------------------------------------
    print(f"\n[Step 3/5] Querying WordPress REST API across {args.pages} page(s)...")
    for page_num in range(1, args.pages + 1):
        api_url = f"https://scholarshipscorner.website/wp-json/wp/v2/posts?categories={target_categories}&per_page={per_page}&page={page_num}"
        print(f"  -> [Page {page_num}/{args.pages}] Calling endpoint: per_page={per_page}...")
        
        try:
            req = urllib.request.Request(api_url, headers=headers)
            with urllib.request.urlopen(req, timeout=20) as response:
                posts = json.loads(response.read().decode('utf-8', errors='replace'))
        except urllib.error.HTTPError as e:
            if e.code == 400:
                print(f"    [!] Reached end of catalog on page {page_num}.")
                break
            else:
                print(f"    [!] HTTP Error {e.code} on page {page_num}: {e}")
                continue
        except Exception as e:
            print(f"    [!] Network error on page {page_num}: {e}")
            continue
            
        if not posts:
            print("    No more posts returned.")
            break
            
        print(f"    Retrieved {len(posts)} scholarship posts from page {page_num}.")
        total_fetched += len(posts)
        
        # -------------------------------------------------------------
        # Step 4 & 5: Clean HTML & SQLite Deduplication
        # -------------------------------------------------------------
        for post in posts:
            raw_title = post.get('title', {}).get('rendered', 'Unknown Title')
            title = html.unescape(raw_title)
            link = post.get('link', '').strip()
            raw_content = post.get('content', {}).get('rendered', '')
            pub_date = post.get('date', '')[:10]
            
            if not link:
                continue
                
            item_hash = get_hash(link)
            cursor.execute("SELECT 1 FROM processed_hashes WHERE hash = ?", (item_hash,))
            if cursor.fetchone():
                continue # Already in SQLite
            if link in backlog_links:
                continue # Already in backlog queue
                
            clean_body = clean_html(raw_content)
            if not clean_body or len(clean_body.strip()) < 50:
                continue
                
            text_to_eval = (
                f"Title: {title}\n"
                f"Source URL: {link}\n"
                f"Published Date: {pub_date}\n\n"
                f"Full Article Content:\n{clean_body[:12000]}"
            )
            
            if text_to_eval not in existing_texts:
                msg_dict = {
                    "source": "Scholarships Corner",
                    "link": link,
                    "title": title,
                    "text": text_to_eval,
                    "scraped_date": time.strftime("%Y-%m-%d")
                }
                queue.append(msg_dict)
                existing_texts.add(text_to_eval)
                new_count += 1
                print(f"    + [NEW] Queued: {title[:60]}...")
                
        time.sleep(1) # Polite API spacing
        
    conn.close()
    
    print(f"\n[Step 5/5] Swept {total_fetched} total posts. Found {new_count} BRAND NEW opportunities.")
    
    if new_count > 0:
        with open(BACKLOG_FILE, 'w', encoding='utf-8') as f:
            json.dump(queue, f, indent=4, ensure_ascii=False)
        print(f"Successfully saved {new_count} new opportunities to {BACKLOG_FILE}.")
        
    print("\n" + "=" * 60)
    print(" ✅ Scholarships Corner Pipeline Scrape Finished ")
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

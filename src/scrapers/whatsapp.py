import re
import os
import sys
import time
import hashlib
import datetime
from playwright.sync_api import sync_playwright

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core import config

DEFAULT_CHANNELS = [
    "World Scholarship Opportunities",
    "Erasmus+",
    "Acadimia Italia",
    "Bright Scholarship",
    "Scholarships Corner",
    "Fully Scholarships"
]

def parse_whatsapp_export(file_path):
    """
    Parses an exported WhatsApp chat file (.txt).
    Supports 12-hour and 24-hour timestamp variations.
    """
    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        return []

    with open(file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    messages = []
    
    pattern = re.compile(
        r'^\[?(?:\d{1,4}[-/]\d{1,2}[-/]\d{1,4}),?\s+\d{1,2}:\d{2}(?::\d{2})?\s*(?:[APap][Mm])?\]?\s*[-:]?\s*([^:]+?):\s*(.*)'
    )

    current_message = None

    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        if "end-to-end encrypted" in line:
            continue
            
        match = pattern.match(line)
        if match:
            if current_message:
                messages.append(current_message)
            
            sender = match.group(1).strip()
            body = match.group(2).strip()
            
            current_message = {
                "sender": sender,
                "text": body
            }
        else:
            if current_message:
                current_message["text"] += "\n" + line
            else:
                current_message = {
                    "sender": "Unknown",
                    "text": line
                }

    if current_message:
        messages.append(current_message)

    return messages

def get_text_hash(t):
    return hashlib.md5(t.strip().encode('utf-8')).hexdigest()

def load_processed_db():
    import sqlite3
    if not os.path.exists(config.PROCESSED_SQLITE_DB):
        return set()
    conn = sqlite3.connect(config.PROCESSED_SQLITE_DB)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT hash FROM processed_hashes")
        hashes = set(row[0] for row in cursor.fetchall())
    except Exception:
        hashes = set()
    conn.close()
    return hashes

def extract_channel_messages(page, channel_name, limit, processed_db):
    """
    Scrolls up inside an open WhatsApp channel and extracts unread/unprocessed messages.
    """
    seen_texts = set()
    messages_data = []
    unchanged_cycles = 0
    consecutive_skips = 0
    
    # Gain keyboard focus ONCE
    try:
        page.locator('div[role="row"]').last.click()
    except Exception:
        viewport = page.viewport_size
        if viewport:
            page.mouse.click(viewport['width'] / 2 + 100, viewport['height'] / 2)
            
    while len(messages_data) < limit:
        rows = page.locator('div[role="row"]').all()
        new_found_this_cycle = 0
        current_batch = []
        
        # Iterate in reverse (from newest on screen to oldest)
        for row in reversed(rows):
            try:
                text = row.inner_text()
                if not text or len(text.strip()) <= 20 or text in seen_texts:
                    continue
                    
                seen_texts.add(text)
                msg_hash = get_text_hash(text)
                
                if msg_hash in processed_db:
                    consecutive_skips += 1
                else:
                    consecutive_skips = 0
                    current_batch.insert(0, {
                        "sender": channel_name,
                        "source": f"{channel_name} (WhatsApp)",
                        "text": text.strip(),
                        "scraped_date": datetime.datetime.now().strftime("%Y-%m-%d")
                    })
                    
                new_found_this_cycle += 1
            except Exception:
                continue
                
        if current_batch:
            messages_data = current_batch + messages_data
            
        if len(messages_data) >= limit:
            break
            
        if new_found_this_cycle == 0:
            unchanged_cycles += 1
            if unchanged_cycles >= 4:
                print(f"    -> Reached the top of visible chat history for '{channel_name}'.")
                break
        else:
            unchanged_cycles = 0
            
        # Scroll up using the Home key
        try:
            page.keyboard.press("Home")
            page.wait_for_timeout(2000)
        except Exception as e:
            print(f"    [!] Scroll note: {e}")
            break
            
    return messages_data[-limit:]

def parse_playwright_live(channel_target=None, limit=0):
    """
    Launches WhatsApp Web, clicks on one or multiple channels, and extracts recent messages.
    Supports single channel string, list of channels, comma-separated names, or 'all'.
    """
    if not channel_target or channel_target.lower() == "all":
        channels_to_scrape = DEFAULT_CHANNELS
    elif isinstance(channel_target, list):
        channels_to_scrape = channel_target
    elif "," in channel_target:
        channels_to_scrape = [c.strip() for c in channel_target.split(",") if c.strip()]
    else:
        channels_to_scrape = [channel_target]
        
    per_channel_limit = limit if limit > 0 else 25
    
    user_data_dir = os.path.join(config.DATA_DIR, "whatsapp_session")
    os.makedirs(user_data_dir, exist_ok=True)
    
    all_extracted_messages = []
    processed_db = load_processed_db()
    
    print("=" * 60)
    print(" [*] PIPELINE TEST: WhatsApp Multi-Channel Live (Target #8) ")
    print(f" Mode: Single-Session Multi-Channel Traversal ({len(channels_to_scrape)} channels)")
    print(f" Channels: {', '.join(channels_to_scrape)}")
    print(f" Extraction limit per channel: {per_channel_limit}")
    print("=" * 60)
    
    # -------------------------------------------------------------
    # Step 1: Launch Persistent Browser Context
    # -------------------------------------------------------------
    print(f"\n[Step 1/5] Launching WhatsApp Web persistent Chromium session ({user_data_dir})...")
    with sync_playwright() as p:
        browser = p.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            headless=False, # Must be False to interact with WhatsApp Web
        )
        page = browser.new_page()
        page.goto("https://web.whatsapp.com/")
        
        # -------------------------------------------------------------
        # Step 2: Wait for Phone Sync
        # -------------------------------------------------------------
        print("\n[Step 2/5] Waiting for WhatsApp Web interface (#pane-side) to sync with phone...")
        print("  (If this is the first time, please scan the QR code in the browser window)")
        
        try:
            page.wait_for_selector('#pane-side', timeout=600000)
            print("  -> WhatsApp Web interface loaded and synchronized successfully!")
        except Exception:
            print("  [!] Timed out waiting for login. Ensure phone is connected and QR code is scanned.")
            browser.close()
            return []
            
        # -------------------------------------------------------------
        # Step 3 & 4: Traversal of Followed Channels
        # -------------------------------------------------------------
        print(f"\n[Step 3/5] Activating Channels navigation tab...")
        try:
            channels_btn = page.locator('button[aria-label="Channels"], button[data-navbar-item-index="3"]').first
            channels_btn.wait_for(state="visible", timeout=10000)
            channels_btn.click()
            page.wait_for_timeout(2000)
        except Exception:
            pass
            
        print(f"\n[Step 4/5] Sweeping {len(channels_to_scrape)} target channels sequentially...")
        for idx, ch_name in enumerate(channels_to_scrape):
            print(f"  [{idx+1}/{len(channels_to_scrape)}] Locating channel: '{ch_name}'...")
            
            try:
                channels_btn = page.locator('button[aria-label="Channels"], button[data-navbar-item-index="3"]').first
                if channels_btn.is_visible():
                    channels_btn.click()
                    page.wait_for_timeout(1500)
            except Exception:
                pass
                
            chat_selector = f'div[aria-label*="{ch_name}" i], span[title*="{ch_name}" i]'
            chat_element = page.locator(chat_selector).first
            
            found = False
            try:
                chat_element.wait_for(state="visible", timeout=6000)
                chat_element.click()
                found = True
                print(f"    -> Opened '{ch_name}' successfully!")
                page.wait_for_timeout(3000)
            except Exception:
                if len(channels_to_scrape) == 1:
                    print(f"    [!] Channel '{ch_name}' was not detected automatically.")
                    print("    Please click on the channel in the browser window and press ENTER.")
                    try:
                        input("Press ENTER when open...")
                        found = True
                    except Exception:
                        pass
                else:
                    print(f"    [!] Channel '{ch_name}' not found in followed list (Use Option 11 in Menu to follow). Skipping...")
                    continue
                    
            if found:
                print(f"    -> Extracting unread messages from '{ch_name}'...")
                msgs = extract_channel_messages(page, ch_name, per_channel_limit, processed_db)
                print(f"    -> Captured {len(msgs)} new unread/unprocessed messages from '{ch_name}'.")
                all_extracted_messages.extend(msgs)
                
            time.sleep(1)
            
        browser.close()
        
    # -------------------------------------------------------------
    # Step 5: Summary & Return to AI Queue
    # -------------------------------------------------------------
    print(f"\n[Step 5/5] Multi-Channel Live Sweep Complete! Total captured: {len(all_extracted_messages)} messages.")
    print("=" * 60)
    print(" [OK] WhatsApp Multi-Channel Pipeline Sweep Finished ")
    print("=" * 60)
    return all_extracted_messages

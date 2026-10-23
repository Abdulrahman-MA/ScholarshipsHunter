import argparse
import os
import sys
import time

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

from core import config
from scrapers.whatsapp import parse_whatsapp_export, parse_playwright_live
from core.matcher import evaluate_opportunity
from core.exporter import export_to_excel
from dotenv import load_dotenv

def main():
    load_dotenv()
    
    parser = argparse.ArgumentParser(description="WhatsApp Scholarship Filter")
    parser.add_argument("--mode", type=str, choices=["file", "live", "backlog"], default="file", help="Ingestion mode")
    parser.add_argument("--file", type=str, default=config.RAW_MESSAGES_FILE, help="Path to raw WhatsApp chat export")
    parser.add_argument("--channel", type=str, default="all", help="Channel name or 'all' for live Playwright scraping")
    parser.add_argument("--limit", type=int, default=0, help="Maximum number of recent messages to process")
    
    args = parser.parse_args()

    # Make sure data dir exists
    os.makedirs(config.DATA_DIR, exist_ok=True)
    
    if not config.GEMINI_API_KEY and not os.getenv("GEMINI_API_KEY"):
        print("WARNING: GEMINI_API_KEY is not set. Please set it in config.py, .env, or as an environment variable.")
        
    import json
    
    BACKLOG_FILE = os.path.join(config.DATA_DIR, "scraped_backlog.json")
    
    # 1. Load the active queue (messages that failed to evaluate last time, or are totally new)
    queue = []
    if os.path.exists(BACKLOG_FILE):
        with open(BACKLOG_FILE, 'r', encoding='utf-8') as f:
            try:
                queue = json.load(f)
                print(f"Loaded {len(queue)} pending messages from the local backlog queue.")
            except:
                pass
                
    # 2. Extract new messages (unless we just want to process the backlog)
    messages = []
    if args.mode == "live":
        messages = parse_playwright_live(args.channel, args.limit)
    elif args.mode == "file":
        print(f"Reading from file: {args.file}")
        messages = parse_whatsapp_export(args.file)
    elif args.mode == "backlog":
        print("Skipping ingestion. Processing strictly from the backlog queue.")
        
    # 3. Add any new live messages to the queue
    existing_texts = {m.get("text", "") for m in queue}
    new_count = 0
    for msg in messages:
        text = msg.get("text", "")
        if text and text not in existing_texts:
            queue.append(msg)
            existing_texts.add(text)
            new_count += 1
            
    if new_count > 0:
        print(f"Added {new_count} newly scraped messages to the evaluation queue.")
        with open(BACKLOG_FILE, 'w', encoding='utf-8') as f:
            json.dump(queue, f, indent=4, ensure_ascii=False)
            
    if not queue:
        print("No pending messages in the queue to evaluate.")
        return
        
    LOCK_FILE = os.path.join(config.DATA_DIR, "backlog_evaluation.lock")
    
    # Check if another process is actively evaluating the backlog
    if os.path.exists(LOCK_FILE):
        try:
            with open(LOCK_FILE, 'r') as f:
                lock_data = f.read().strip()
            lock_pid = int(lock_data.split(':')[0]) if ':' in lock_data else 0
            lock_time = float(lock_data.split(':')[1]) if ':' in lock_data else 0
            
            # Check if process is still running on Windows
            import ctypes
            h = ctypes.windll.kernel32.OpenProcess(0x1000, False, lock_pid)
            is_alive = bool(h)
            if h:
                ctypes.windll.kernel32.CloseHandle(h)
                
            if is_alive and (time.time() - lock_time < 1800):
                print(f"\n  [!] Another terminal/process (PID {lock_pid}) is already actively evaluating the backlog.")
                print("  [!] Skipping duplicate evaluation to save tokens and prevent collisions.")
                print("  [!] You can safely let the other window finish.")
                return
            else:
                try:
                    os.remove(LOCK_FILE)
                except:
                    pass
        except Exception:
            pass
            
    # Acquire lock
    try:
        with open(LOCK_FILE, 'w') as f:
            f.write(f"{os.getpid()}:{time.time()}")
    except:
        pass
        
    print(f"Total messages in queue ready for AI evaluation: {len(queue)}")
    
    # 4. Evaluate the queue
    import hashlib
    import sqlite3
    def get_text_hash(t):
        return hashlib.md5(t.strip().encode('utf-8')).hexdigest()
        
    evaluated_opps = []
    remaining_queue = list(queue) # We make a copy so we can safely remove items while looping
    
    conn = sqlite3.connect(config.PROCESSED_SQLITE_DB, timeout=30.0)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS processed_hashes (hash TEXT PRIMARY KEY)''')
    
    try:
        for idx, msg in enumerate(queue):
            text = msg.get("text", "")
            # Basic filter
            if len(text.split()) < 10:
                if msg in remaining_queue:
                    remaining_queue.remove(msg) # Discard it permanently from the queue
                continue
                
            # Pre-evaluation check: has another terminal already evaluated and saved this?
            msg_hash = get_text_hash(text)
            cursor.execute("SELECT 1 FROM processed_hashes WHERE hash = ?", (msg_hash,))
            if cursor.fetchone():
                title_preview = msg.get("title", "") or msg.get("opportunity_title", "")
                print(f"  [{idx + 1}/{len(queue)}] Already evaluated & saved in database. Skipping '{title_preview[:40]}'...")
                if msg in remaining_queue:
                    remaining_queue.remove(msg)
                continue
                
            print(f"Evaluating message {idx + 1}/{len(queue)}...")
            opp, error_msg = evaluate_opportunity(text)
            
            if opp:
                # The AI successfully extracted it!
                evaluated_opps.append({"opp": opp, "msg": msg})
                
                # 3. Batch Saving (Auto-save every 3 items for frequent disk sync)
                if len(evaluated_opps) >= 3:
                    print("\n[Auto-Save] Saving batch to Excel & SQLite...")
                    try:
                        export_to_excel(evaluated_opps, config.OUTPUT_EXCEL_FILE)
                        
                        save_conn = sqlite3.connect(config.PROCESSED_SQLITE_DB, timeout=30.0)
                        save_cursor = save_conn.cursor()
                        save_cursor.execute('''CREATE TABLE IF NOT EXISTS processed_hashes (hash TEXT PRIMARY KEY)''')
                        
                        for item in evaluated_opps:
                            raw_msg = item["msg"]
                            opp = item["opp"]
                            item_hash = get_text_hash(raw_msg.get("text", ""))
                            save_cursor.execute("INSERT OR IGNORE INTO processed_hashes (hash) VALUES (?)", (item_hash,))
                            
                            link_val = raw_msg.get("link") or getattr(opp, "application_link", None)
                            if link_val and isinstance(link_val, str) and link_val.startswith('http'):
                                save_cursor.execute("INSERT OR IGNORE INTO processed_hashes (hash) VALUES (?)", (get_text_hash(link_val.strip()),))
                                
                            if raw_msg in remaining_queue:
                                remaining_queue.remove(raw_msg)
                        
                        save_conn.commit()
                        save_conn.close()
                                    
                        with open(BACKLOG_FILE, 'w', encoding='utf-8') as f:
                            json.dump(remaining_queue, f, indent=4, ensure_ascii=False)
                            
                        evaluated_opps.clear() 
                        print("Batch successfully secured and RAM cleared.")
                    except Exception as e:
                        print(f"\n[!] Failed to save Excel! (Is the file open?). Error: {e}")
                        print("Data remains safely in your backlog queue for next time.")
                        break # Stop the loop so we don't keep failing
            else:
                print(f"API failed. Moving message to Dead Letter Queue (DLQ)...")
                
                import datetime
                failed_msg = {
                    "timestamp": datetime.datetime.now().isoformat(),
                    "source": msg.get("sender", "Unknown"),
                    "raw_text": text,
                    "error_reason": error_msg or "Unknown API Error"
                }
                
                # Append to DLQ file
                with open(config.DLQ_FILE, 'a', encoding='utf-8') as f:
                    f.write(json.dumps(failed_msg, ensure_ascii=False) + '\n')
                
                # We also mark it in the processed DB so the scraper ignores it in the future
                import sqlite3
                conn = sqlite3.connect(config.PROCESSED_SQLITE_DB)
                cursor = conn.cursor()
                cursor.execute('''CREATE TABLE IF NOT EXISTS processed_hashes (hash TEXT PRIMARY KEY)''')
                cursor.execute("INSERT OR IGNORE INTO processed_hashes (hash) VALUES (?)", (get_text_hash(text),))
                conn.commit()
                conn.close()
                
                # Finally, remove from backlog so it doesn't clog future runs
                if msg in remaining_queue:
                    remaining_queue.remove(msg)
                with open(BACKLOG_FILE, 'w', encoding='utf-8') as f:
                    json.dump(remaining_queue, f, indent=4, ensure_ascii=False)
                    
            # Pace the API calls
            time.sleep(2)
            
    except KeyboardInterrupt:
        print("\n[!] Script manually stopped by user. Saving current progress...")
    except Exception as e:
        print(f"\n[!] An unexpected error occurred: {e}")
    finally:
        # Export whatever is left in the list (e.g. the last 5 messages that didn't make a full batch of 10)
        if evaluated_opps:
            print(f"\nExporting final batch of {len(evaluated_opps)} opportunities to {config.OUTPUT_EXCEL_FILE}...")
            try:
                export_to_excel(evaluated_opps, config.OUTPUT_EXCEL_FILE)
                
                import sqlite3
                conn = sqlite3.connect(config.PROCESSED_SQLITE_DB)
                cursor = conn.cursor()
                cursor.execute('''CREATE TABLE IF NOT EXISTS processed_hashes (hash TEXT PRIMARY KEY)''')
                
                for item in evaluated_opps:
                    raw_msg = item["msg"]
                    opp = item["opp"]
                    msg_hash = get_text_hash(raw_msg.get("text", ""))
                    cursor.execute("INSERT OR IGNORE INTO processed_hashes (hash) VALUES (?)", (msg_hash,))
                    
                    link_val = raw_msg.get("link") or getattr(opp, "application_link", None)
                    if link_val and isinstance(link_val, str) and link_val.startswith('http'):
                        cursor.execute("INSERT OR IGNORE INTO processed_hashes (hash) VALUES (?)", (get_text_hash(link_val.strip()),))
                        
                    if raw_msg in remaining_queue:
                        remaining_queue.remove(raw_msg)
                        
                conn.commit()
                conn.close()
                print("Data safely saved! You can close the terminal.")
            except Exception as e:
                print(f"\n[!] Failed to save final Excel! (Is the file open?). Error: {e}")
                print("Data remains safely in your backlog queue for next time.")
        else:
            print("\nAll batches safely saved. Run complete!")
            
        # ALWAYS safely persist remaining non-evaluated queue back to disk (Fault-Tolerant Fallback)
        try:
            with open(BACKLOG_FILE, 'w', encoding='utf-8') as f:
                json.dump(remaining_queue, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"  [!] Failed to update backlog file: {e}")
            
        # Clean up backlog process lock so subsequent runs can start cleanly
        try:
            if os.path.exists(LOCK_FILE):
                os.remove(LOCK_FILE)
        except Exception:
            pass

if __name__ == "__main__":
    main()

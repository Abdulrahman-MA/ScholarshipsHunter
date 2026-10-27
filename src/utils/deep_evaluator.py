import os
import sys
import time
import argparse
import pandas as pd
from playwright.sync_api import sync_playwright

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core import config
from core import matcher
from core import exporter

def save_df_safely(df, excel_path):
    for attempt in range(3):
        try:
            df.to_excel(excel_path, index=False)
            exporter.apply_excel_formatting(excel_path)
            return True
        except PermissionError:
            if attempt < 2:
                print(f"  [!] Excel file is open! Retrying in 2 seconds... ({attempt+1}/3)")
                time.sleep(2)
            else:
                print(f"  [!] CRITICAL: Could not save to {excel_path}. Please close Excel!")
                return False
        except Exception as e:
            print(f"  [!] Error saving Excel: {e}")
            return False

def run(limit=None, all_sources=True, auto=False):
    print("=" * 60)
    print(" 🔍 Deep Website Evaluator & Verification Engine ")
    print("=" * 60)
    
    excel_path = config.OUTPUT_EXCEL_FILE
    if not os.path.exists(excel_path):
        print(f"Error: Could not find {excel_path}")
        return
        
    print(f"Loading {excel_path}...")
    try:
        df = pd.read_excel(excel_path)
    except Exception as e:
        print(f"Failed to read Excel file. Please make sure it is closed! Error: {e}")
        return
        
    if "Deep Checked" not in df.columns:
        df["Deep Checked"] = ""
    else:
        df["Deep Checked"] = df["Deep Checked"].fillna("")
        
    if not auto:
        print("\nWhich rows would you like to deeply evaluate?")
        print("[1] Only WhatsApp rows")
        print("[2] ALL eligible rows across all web sources (Default)")
        source_choice = input("Enter choice (1/2) [Default: 2]: ").strip()
        all_sources = (source_choice != "1")
    else:
        print(f"Mode: Automated run (All sources: {all_sources}, Limit: {limit})")

    # Identify target rows:
    # 1. Match Score >= 50 (Focus on Green & Yellow opportunities)
    # 2. Deep Checked is blank (never deep checked)
    # 3. Link starts with http
    target_items = []
    for idx, row in df.iterrows():
        try:
            score = float(row.get("Match Score", 0))
        except (ValueError, TypeError):
            score = 0
            
        deep_checked = str(row.get("Deep Checked", "")).strip().lower()
        link = str(row.get("Link", "")).strip()
        web_source = str(row.get("Web Source", "")).strip()
        category = str(row.get("Category", "")).strip().lower()
        
        # Only select rows that haven't been successfully deep-checked or marked failed
        if score >= 50 and (not deep_checked or deep_checked == "") and link.startswith("http"):
            if not all_sources and "whatsapp" not in web_source.lower():
                continue
            # Store tuple: (priority, -score, idx)
            # Priority: 0 for Green, 1 for Yellow
            pri = 0 if "green" in category else 1
            target_items.append((pri, -score, idx))
            
    if not target_items:
        print("\n✅ All eligible scholarships are already Deep Checked! (0 unchecked links remaining)")
        return
        
    # Sort: Green first, then highest Match Score first
    target_items.sort()
    target_indices = [item[2] for item in target_items]

    print(f"\nFound {len(target_indices)} scholarships eligible for Deep Website Evaluation.")
    
    if not auto:
        batch_input = input(f"How many would you like to process right now? (Enter a number, or press ENTER for all {len(target_indices)}): ").strip()
        if batch_input.isdigit() and int(batch_input) > 0:
            target_indices = target_indices[:int(batch_input)]
    elif limit and limit > 0:
        target_indices = target_indices[:limit]
        print(f"Batch ceiling applied: Processing top {len(target_indices)} priority rows today.")

    # Force matcher to use high-speed Cloud AI (Groq 120B with Gemini fallback)
    config.USE_OLLAMA = False
    
    user_data_dir = os.path.join(config.DATA_DIR, "deep_evaluator_session")
    os.makedirs(user_data_dir, exist_ok=True)
    
    print(f"\nLaunching Stealth Browser to evaluate {len(target_indices)} scholarships...")
    print("AI Engine: Groq Ultra-Fast LPUs (120B Model) with Gemini Fallback.\n")
    
    processed_count = 0
    
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch_persistent_context(
                user_data_dir=user_data_dir,
                headless=True,
                viewport={'width': 1280, 'height': 800},
                ignore_default_args=["--enable-automation"],
                args=["--disable-blink-features=AutomationControlled"]
            )
            page = browser.new_page()
            
            from playwright_stealth import Stealth
            Stealth().apply_stealth_sync(page)
            
            for count, idx in enumerate(target_indices, 1):
                row = df.loc[idx]
                title = row.get("Title", "Unknown Title")
                url = str(row.get("Link", "")).strip()
                
                print(f"[{count}/{len(target_indices)}] Deep checking: {title[:55]}")
                print(f"  -> Visiting: {url}")
                
                try:
                    page.goto(url, wait_until="domcontentloaded", timeout=20000)
                    time.sleep(1.5) # Let dynamic content settle
                    body_text = page.locator("body").inner_text()
                except Exception as e:
                    print(f"  -> [!] Webpage load failed: {e}")
                    df.at[idx, "Deep Checked"] = "Failed (Load Error)"
                    continue
                    
                if not body_text or len(body_text.strip()) < 100:
                    print("  -> [!] Webpage had insufficient text (possibly blocked or empty). Skipping.")
                    df.at[idx, "Deep Checked"] = "Failed (Empty/Blocked)"
                    continue
                    
                text_to_eval = (
                    f"Original Summary Title: {title}\n"
                    f"Source URL: {url}\n\n"
                    f"Full Website Text:\n{body_text[:12000]}"
                )
                
                print("  -> Querying Groq/Gemini LPU...")
                opp, error_msg = matcher.evaluate_opportunity(text_to_eval)
                
                if opp:
                    print(f"  -> Verdict: {opp.category.upper()} (New Score: {opp.match_score})")
                    print(f"  -> Reason: {opp.reasoning[:100]}...")
                    
                    df.at[idx, "Category"] = opp.category
                    df.at[idx, "Match Score"] = opp.match_score
                    df.at[idx, "AI Rationale"] = opp.reasoning
                    df.at[idx, "Action Items"] = opp.action_items
                    if opp.deadline and opp.deadline.lower() != "unspecified":
                        df.at[idx, "Deadline"] = opp.deadline
                    if opp.funding_status and opp.funding_status.lower() != "unspecified":
                        df.at[idx, "Funding"] = opp.funding_status
                    df.at[idx, "Deep Checked"] = "Yes"
                    processed_count += 1
                else:
                    print(f"  -> [!] AI evaluation error: {error_msg}")
                    df.at[idx, "Deep Checked"] = f"Error: {error_msg}"
                    
                # Auto-save every 5 items so progress is never lost
                if processed_count > 0 and processed_count % 5 == 0:
                    print("  [Auto-Save] Saving progress to Excel...")
                    save_df_safely(df, excel_path)
                    print("  [Auto-Save] Saved!\n")
                    
                # Polite pacing between browser navigations
                if count < len(target_indices):
                    time.sleep(1.0)
                    
            browser.close()
            
    except KeyboardInterrupt:
        print("\n[!] Deep evaluation manually interrupted by user. Saving progress so far...")
    finally:
        if processed_count > 0:
            print("\nSaving final updates and re-applying Excel formatting...")
            if save_df_safely(df, excel_path):
                print(f"✅ Successfully updated {processed_count} scholarships with full website verification!")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Deep Website Evaluator")
    parser.add_argument("--limit", type=int, default=None, help="Max rows to process (e.g. 100)")
    parser.add_argument("--all-sources", action="store_true", help="Evaluate all web sources, not just WhatsApp")
    parser.add_argument("--auto", action="store_true", help="Run unattended in automated mode")
    args = parser.parse_args()
    
    run(limit=args.limit, all_sources=args.all_sources or args.auto, auto=args.auto)

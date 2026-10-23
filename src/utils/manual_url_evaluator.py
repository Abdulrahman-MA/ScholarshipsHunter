import os
import sys
import time
from playwright.sync_api import sync_playwright

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core import config
from core import matcher
from core import exporter

def run():
    print("==================================================")
    print(" 🤖 Manual URL Evaluator (AI Profiler) ")
    print("==================================================")
    
    url = input("\nPaste the Scholarship URL you want to evaluate: ").strip()
    if not url:
        print("No URL provided. Exiting.")
        return
        
    print("\n[1/3] Spinning up Stealth Browser to extract text...")
    user_data_dir = os.path.join(config.DATA_DIR, "manual_evaluator_session")
    os.makedirs(user_data_dir, exist_ok=True)
    
    try:
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
            
            page.goto(url, wait_until="domcontentloaded")
            time.sleep(3) # Let JS settle
            
            print("[2/3] Reading page content...")
            body_text = page.locator("body").inner_text()
            browser.close()
    except Exception as e:
        print(f"Failed to scrape URL: {e}")
        return
        
    text_to_eval = f"Source URL: {url}\n\n{body_text[:12000]}"
    
    print("\n[3/3] Feeding full text to AI with your Applicant Profile...")
    result, error_msg = matcher.evaluate_opportunity(text_to_eval)
    
    if result:
        print("\n==================================================")
        print(f"{result.opportunity_title} ({result.institution_or_country})")
        print(f"Verdict: {result.category.upper()} (Score: {result.match_score})")
        print(f"\nReason:\n{result.reasoning}")
        print(f"\nNext Step:\n{result.action_items}")
        print("==================================================")
        
        # Override the application link to be the exact URL they pasted
        result.application_link = url
        
        msg_dict = {
            "source": "Manual Link Submission",
            "text": text_to_eval,
            "scraped_date": time.strftime("%Y-%m-%d")
        }
        
        print("\nSaving evaluation directly to your Excel Tracker...")
        exporter.export_to_excel([{"opp": result, "msg": msg_dict}], config.OUTPUT_EXCEL_FILE)
        print("✅ Done!")
    else:
        print(f"\n❌ AI Failed to evaluate. Reason: {error_msg}")

if __name__ == "__main__":
    run()

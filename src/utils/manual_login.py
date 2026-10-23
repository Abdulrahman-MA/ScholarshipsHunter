import os
import sys
from playwright.sync_api import sync_playwright

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core import config

def launch_whatsapp_session():
    print("\nOpening WhatsApp Web session...")
    print("Please scan the QR code or wait for your chats to sync.")
    print("Close the browser window when you are finished.")
    
    user_data_dir = os.path.join(config.DATA_DIR, "whatsapp_session")
    os.makedirs(user_data_dir, exist_ok=True)
    
    with sync_playwright() as p:
        # Standard configuration for WhatsApp (no stealth plugins as required)
        browser = p.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            headless=False,
        )
        page = browser.pages[0] if browser.pages else browser.new_page()
        page.goto("https://web.whatsapp.com/")
        
        try:
            page.wait_for_event("close", timeout=0)
        except Exception:
            pass
            
    print("WhatsApp browser closed. Session saved!")

def launch_scrapers_session():
    print("\nOpening Scholarship Websites (ProFellow, WeMakeScholars, MastersPortal) in tabs...")
    print("Please sign in, accept cookies, or solve any captchas on each tab.")
    print("Close the entire browser window when you are finished.")
    
    user_data_dir = os.path.join(config.DATA_DIR, "profellow_session")
    os.makedirs(user_data_dir, exist_ok=True)
    
    urls = [
        "https://www.profellow.com/sign-in",
        "https://www.wemakescholars.com/masters-scholarships-in-physics-to-study-abroad",
        "https://www.mastersportal.com/search/scholarships/master/physics"
    ]
    
    with sync_playwright() as p:
        browser = p.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            headless=False,
            viewport={'width': 1280, 'height': 800},
            ignore_default_args=["--enable-automation"],
            args=["--disable-blink-features=AutomationControlled"]
        )
        
        from playwright_stealth import Stealth
        stealth_plugin = Stealth()
        
        pages = []
        for i, url in enumerate(urls):
            page = browser.pages[0] if (i == 0 and browser.pages) else browser.new_page()
            stealth_plugin.apply_stealth_sync(page)
            print(f"  -> Preloading tab {i+1}: {url}")
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=30000)
            except Exception as e:
                print(f"     (Note: Tab {i+1} took a while to load, you can interact with it directly)")
            pages.append(page)
            
        print("\nAll tabs opened! Take your time logging in. Close the browser window when done.")
        try:
            browser.wait_for_event("close", timeout=0)
        except Exception:
            pass
            
    print("Scraper browser closed. Session data saved successfully!")

def launch_whatsapp_channels():
    print("\nOpening WhatsApp Channel invite links in tabs...")
    print("Click 'View Channel' / 'Follow' on each tab, then close the browser window.")
    
    user_data_dir = os.path.join(config.DATA_DIR, "whatsapp_session")
    os.makedirs(user_data_dir, exist_ok=True)
    
    channel_urls = [
        "https://whatsapp.com/channel/0029Vak1jydG3R3nzCgkdn3l", # Erasmus+
        "https://whatsapp.com/channel/0029VbCzDEb8qIzwLLzxFI2w", # Acadimia Italia
        "https://whatsapp.com/channel/0029VaeP7zxKwqSSVQNAus05", # World Scholarship Opportunities
        "https://whatsapp.com/channel/0029VaBuS5lDeON2qKPfgJ2h", # Bright Scholarship
        "https://whatsapp.com/channel/0029VaB8GDzBPzjUIeVner1n", # Scholarships Corner
        "https://whatsapp.com/channel/0029VaC9hl4FCCoVbr1xxj2Q", # Fully Scholarships
    ]
    
    with sync_playwright() as p:
        browser = p.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            headless=False,
        )
        for i, url in enumerate(channel_urls):
            page = browser.pages[0] if (i == 0 and browser.pages) else browser.new_page()
            print(f"  -> Opening Channel {i+1}/6: {url}")
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=30000)
            except Exception:
                pass
                
        print("\nAll channel tabs opened! Follow them and close the browser when done.")
        try:
            browser.wait_for_event("close", timeout=0)
        except Exception:
            pass
            
    print("WhatsApp channels window closed. Sessions updated!")

def run():
    print("==================================================")
    print(" 🔐 AUTO-PRELOAD & MANUAL LOGIN UTILITY ")
    print("==================================================")
    print("[1] Open ALL Scholarship Websites (ProFellow, WeMakeScholars, MastersPortal)")
    print("[2] Open WhatsApp Web (QR Code / Sync)")
    print("[3] Open All 6 WhatsApp Channels (Preload invite links to easily click 'Follow')")
    print("[4] Open Everything Sequentially (Sites -> WhatsApp Web -> Channels)")
    print("==================================================")
    
    choice = input("Select an option (1-4) [Default: 1]: ").strip()
    if not choice:
        choice = "1"
        
    if choice == "1":
        launch_scrapers_session()
    elif choice == "2":
        launch_whatsapp_session()
    elif choice == "3":
        launch_whatsapp_channels()
    elif choice == "4":
        launch_scrapers_session()
        launch_whatsapp_session()
        launch_whatsapp_channels()
    else:
        print("Invalid choice.")

if __name__ == "__main__":
    run()

"""
TEST SCRIPT: Verify the bot correctly identifies already-disputed tracking IDs

This script will:
1. Open a browser and navigate to a specific invoice
2. Read the Dispute Activity section
3. Read the main shipments table
4. Compare and show which ones would be skipped vs disputed
5. Does NOT actually submit any disputes - just shows what it would do

Usage: python test_duplicate_check.py
"""

import time
import re
import json
import os
from datetime import datetime
from playwright.sync_api import sync_playwright

def log(message):
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] {message}")

def test_invoice(page, invoice_number, account_no="202744967"):
    """Test the duplicate detection on a single invoice"""
    
    invoice_no_clean = invoice_number.replace("-", "")
    invoice_url = f"https://www.fedex.com/online/billing/cbs/invoices/invoice-details?accountNo={account_no}&countryCode=CA&invoiceNumber={invoice_no_clean}"
    
    log(f"Navigating to invoice {invoice_number}...")
    page.goto(invoice_url, wait_until="domcontentloaded")
    time.sleep(3)
    
    if "invoice-details" not in page.url:
        log(f"ERROR: Failed to load invoice page")
        return
    
    # ========== STEP 1: Get ALL tracking IDs from the main shipments table ==========
    log("")
    log("=" * 60)
    log("STEP 1: Scanning main shipments table...")
    log("=" * 60)
    
    all_tracking_ids = set()
    try:
        page.wait_for_selector("tbody tr", timeout=10000)
        time.sleep(2)
        
        main_rows = page.locator("tbody tr").all()
        for row in main_rows:
            row_text = row.text_content() or ""
            tracking_nums = re.findall(r'\b\d{12}\b', row_text)
            all_tracking_ids.update(tracking_nums)
        
        log(f"Found {len(all_tracking_ids)} tracking IDs in shipments table:")
        for tid in sorted(all_tracking_ids):
            log(f"   {tid}")
    except Exception as e:
        log(f"ERROR: {e}")
        return
    
    # ========== STEP 2: Get ALL already-disputed tracking IDs from Dispute Activity ==========
    log("")
    log("=" * 60)
    log("STEP 2: Checking Dispute Activity section...")
    log("=" * 60)
    
    already_disputed_duty_tax = set()
    already_disputed_other = set()
    
    try:
        # Try to find and click the Dispute Activity section
        dispute_section = None
        for selector in ["text=Dispute activity", "text=Dispute Activity", "text=DISPUTE ACTIVITY"]:
            try:
                elem = page.locator(selector).first
                if elem.is_visible(timeout=2000):
                    dispute_section = elem
                    log(f"Found section with selector: {selector}")
                    break
            except:
                continue
        
        if dispute_section:
            log("Clicking to expand Dispute Activity...")
            dispute_section.click()
            time.sleep(3)
            
            # Scroll to load all
            for _ in range(10):
                page.keyboard.press("End")
                time.sleep(0.3)
            page.keyboard.press("Home")
            time.sleep(0.5)
            
            # Get all rows
            dispute_table_rows = page.locator("tr").all()
            log(f"Found {len(dispute_table_rows)} rows in page")
            
            log("")
            log("Disputes found:")
            for row in dispute_table_rows:
                row_text = row.text_content() or ""
                
                if not row_text.strip():
                    continue
                if "DISPUTE ID" in row_text.upper() and "AIR WAYBILL" in row_text.upper():
                    continue
                if "DISPUTE REASON" in row_text.upper():
                    continue
                
                tracking_nums = re.findall(r'\b\d{12}\b', row_text)
                
                if tracking_nums:
                    tracking_num = tracking_nums[0]
                    
                    if "Duty/Tax" in row_text or "Duty / Tax" in row_text:
                        already_disputed_duty_tax.add(tracking_num)
                        log(f"   ✓ {tracking_num} - Duty/Tax")
                    else:
                        already_disputed_other.add(tracking_num)
                        reason = "Other"
                        for r in ["Duplicate", "Dimension", "Weight", "Address"]:
                            if r in row_text:
                                reason = r
                                break
                        log(f"   ○ {tracking_num} - {reason}")
            
            log("")
            log(f"Total Duty/Tax disputes: {len(already_disputed_duty_tax)}")
            log(f"Total Other disputes: {len(already_disputed_other)}")
        else:
            log("No Dispute Activity section found")
    except Exception as e:
        log(f"ERROR reading disputes: {e}")
        import traceback
        traceback.print_exc()
    
    # ========== STEP 3: Compare and show results ==========
    log("")
    log("=" * 60)
    log("STEP 3: COMPARISON RESULTS")
    log("=" * 60)
    
    to_dispute = all_tracking_ids - already_disputed_duty_tax
    to_skip = all_tracking_ids & already_disputed_duty_tax
    
    log(f"")
    log(f"Tracking IDs in shipments table: {len(all_tracking_ids)}")
    log(f"Already disputed for Duty/Tax:   {len(already_disputed_duty_tax)}")
    log(f"")
    
    if to_skip:
        log(f"WOULD SKIP ({len(to_skip)} tracking IDs already disputed for Duty/Tax):")
        for tid in sorted(to_skip):
            log(f"   ⏭ {tid}")
    
    log("")
    
    if to_dispute:
        log(f"WOULD DISPUTE ({len(to_dispute)} tracking IDs need Duty/Tax dispute):")
        for tid in sorted(to_dispute):
            log(f"   📝 {tid}")
    else:
        log("✅ ALL TRACKING IDs ALREADY DISPUTED - Nothing to do!")
    
    log("")
    log("=" * 60)
    log("TEST COMPLETE - No disputes were submitted")
    log("=" * 60)

def main():
    print("=" * 60)
    print("DUPLICATE CHECK TEST")
    print("=" * 60)
    print("")
    
    # Load config
    config = {}
    try:
        with open("bot_config.json", 'r') as f:
            config = json.load(f)
    except:
        config = {
            "user_data_dir": "./user_data_v6",
            "account_number": "202744967",
        }
    
    with sync_playwright() as p:
        log("Launching browser...")
        
        browser_context = p.chromium.launch_persistent_context(
            user_data_dir=config.get('user_data_dir', './user_data_v6'),
            headless=False,
            channel="chrome",
            args=["--disable-blink-features=AutomationControlled"],
            viewport={"width": 1400, "height": 900}
        )
        
        page = browser_context.pages[0]
        
        # Navigate to FedEx
        fedex_url = "https://www.fedex.com/en-ca/logged-in-home.html"
        log(f"Navigating to {fedex_url}...")
        page.goto(fedex_url, wait_until="domcontentloaded")
        
        print("")
        print("=" * 60)
        print("PLEASE LOG IN TO FEDEX IF NEEDED")
        print("=" * 60)
        print("")
        
        invoice_number = input("Enter invoice number to test (e.g., 2-700-61230): ").strip()
        
        if invoice_number:
            test_invoice(page, invoice_number, config.get("account_number", "202744967"))
        
        input("\nPress Enter to close browser...")
        browser_context.close()

if __name__ == "__main__":
    main()


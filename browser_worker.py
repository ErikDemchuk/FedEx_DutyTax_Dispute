"""
Browser Worker - Runs Playwright in a separate process
Communicates with the main app via JSON files
"""
import json
import time
import re
import os
import sys
from datetime import datetime
from playwright.sync_api import sync_playwright

# State file paths
STATE_FILE = "bot_state.json"
LOG_FILE = "bot_logs.json"

def load_state():
    """Load current state from file"""
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r') as f:
                return json.load(f)
        except:
            pass
    return {"command": "idle", "config": {}}

def save_state(state):
    """Save state to file"""
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f)

def load_logs():
    """Load logs from file"""
    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, 'r') as f:
                return json.load(f)
        except:
            pass
    return {"logs": [], "stats": {"disputed": 0, "skipped": 0, "errors": 0, "invoices_processed": 0, "total_invoices": 0}, "invoices": []}

def save_logs(logs_data):
    """Save logs to file"""
    with open(LOG_FILE, 'w') as f:
        json.dump(logs_data, f)

def log(message, level="INFO"):
    """Log a message"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    logs_data = load_logs()
    logs_data["logs"].append(f"[{timestamp}] {message}")
    # Keep only last 100
    logs_data["logs"] = logs_data["logs"][-100:]
    save_logs(logs_data)
    print(f"[{timestamp}] [{level}] {message}")

def update_stat(key, value=None, increment=False):
    """Update a statistic"""
    logs_data = load_logs()
    if increment:
        logs_data["stats"][key] = logs_data["stats"].get(key, 0) + 1
    else:
        logs_data["stats"][key] = value
    save_logs(logs_data)

def save_invoices(invoices):
    """Save found invoices"""
    logs_data = load_logs()
    logs_data["invoices"] = invoices
    save_logs(logs_data)

def navigate_to_invoices(page):
    """Navigate from logged-in page to invoices list"""
    log("Navigating to invoices...")
    
    try:
        pay_bill = page.locator("text=PAY A BILL").first
        if pay_bill.is_visible(timeout=3000):
            pay_bill.click()
            time.sleep(2)
    except:
        pass
    
    try:
        billing_link = page.locator("text=FedEx Billing Online").first
        if billing_link.is_visible(timeout=3000):
            billing_link.click()
            time.sleep(3)
    except:
        pass
    
    try:
        close_btn = page.locator("button:has-text('Close'), button:has-text('CLOSE')").first
        if close_btn.is_visible(timeout=1000):
            close_btn.click()
            time.sleep(1)
    except:
        pass
    
    try:
        invoices_link = page.locator("text=INVOICES").first
        if invoices_link.is_visible(timeout=5000):
            invoices_link.click()
            time.sleep(3)
    except:
        pass
    
    if "invoices" not in page.url.lower():
        log("Trying direct navigation to invoices...")
        page.goto("https://www.fedex.com/online/billing/cbs/invoices", wait_until="domcontentloaded")
        time.sleep(3)
    
    log("Navigation complete.")

def handle_dispute_form(page, config):
    """
    Handle the dispute form with multiple fallback methods.
    Returns True if successful, False otherwise.
    """
    try:
        # Wait for form to appear
        time.sleep(2)
        
        # Check if we're on the dispute form
        form_visible = False
        for selector in ["text=Dispute type", "text=DISPUTE TYPE", "div[role='dialog']"]:
            try:
                if page.locator(selector).first.is_visible(timeout=3000):
                    form_visible = True
                    break
            except:
                continue
        
        if not form_visible:
            log("   ⚠️ Dispute form not visible, waiting longer...")
            time.sleep(3)
        
        # ========== STEP 1: Select Dispute Type = "Incorrect charge" ==========
        log("   Step 1: Selecting Dispute Type...")
        type_selected = False
        
        # Method 1: Click the first "Select" dropdown
        try:
            selects = page.locator("text=Select").all()
            if len(selects) > 0:
                selects[0].click()
                time.sleep(1)
                page.locator("text=Incorrect charge").first.click()
                time.sleep(1)
                type_selected = True
                log("   ✓ Selected 'Incorrect charge' (method 1)")
        except Exception as e:
            log(f"   Method 1 failed: {str(e)[:40]}")
        
        # Method 2: Click dropdown by aria-label or role
        if not type_selected:
            try:
                page.locator("[aria-haspopup='listbox']").first.click()
                time.sleep(1)
                page.locator("text=Incorrect charge").first.click()
                time.sleep(1)
                type_selected = True
                log("   ✓ Selected 'Incorrect charge' (method 2)")
            except Exception as e:
                log(f"   Method 2 failed: {str(e)[:40]}")
        
        # Method 3: Use keyboard navigation
        if not type_selected:
            try:
                page.keyboard.press("Tab")
                time.sleep(0.3)
                page.keyboard.press("Enter")
                time.sleep(0.5)
                page.keyboard.type("Incorrect")
                time.sleep(0.3)
                page.keyboard.press("Enter")
                time.sleep(1)
                type_selected = True
                log("   ✓ Selected 'Incorrect charge' (method 3 - keyboard)")
            except Exception as e:
                log(f"   Method 3 failed: {str(e)[:40]}")
        
        if not type_selected:
            log("   ❌ Could not select Dispute Type")
            return False
        
        # ========== STEP 2: Select Dispute Reason = "Duty/Tax" ==========
        log("   Step 2: Selecting Dispute Reason...")
        reason_selected = False
        
        # Method 1: Click the next "Select" dropdown
        try:
            selects = page.locator("text=Select").all()
            if len(selects) > 0:
                selects[0].click()
                time.sleep(1)
                page.locator("text=Duty/Tax").first.click()
                time.sleep(1)
                reason_selected = True
                log("   ✓ Selected 'Duty/Tax' (method 1)")
        except Exception as e:
            log(f"   Method 1 failed: {str(e)[:40]}")
        
        # Method 2: Click dropdown by aria-label or role
        if not reason_selected:
            try:
                dropdowns = page.locator("[aria-haspopup='listbox']").all()
                if len(dropdowns) > 1:
                    dropdowns[1].click()
                elif len(dropdowns) > 0:
                    dropdowns[0].click()
                time.sleep(1)
                page.locator("text=Duty/Tax").first.click()
                time.sleep(1)
                reason_selected = True
                log("   ✓ Selected 'Duty/Tax' (method 2)")
            except Exception as e:
                log(f"   Method 2 failed: {str(e)[:40]}")
        
        # Method 3: Use keyboard
        if not reason_selected:
            try:
                page.keyboard.press("Tab")
                time.sleep(0.3)
                page.keyboard.press("Enter")
                time.sleep(0.5)
                page.keyboard.type("Duty")
                time.sleep(0.3)
                page.keyboard.press("Enter")
                time.sleep(1)
                reason_selected = True
                log("   ✓ Selected 'Duty/Tax' (method 3 - keyboard)")
            except Exception as e:
                log(f"   Method 3 failed: {str(e)[:40]}")
        
        if not reason_selected:
            log("   ❌ Could not select Dispute Reason")
            return False
        
        # ========== STEP 3: Enter Comment ==========
        log("   Step 3: Entering comment...")
        comment = config.get("dispute_comment", "Reason for dispute- Products are CUSMA compliant.")
        
        comment_entered = False
        try:
            textarea = page.locator("textarea").first
            if textarea.is_visible(timeout=2000):
                textarea.fill(comment)
                comment_entered = True
                log("   ✓ Entered comment in textarea")
        except:
            pass
        
        if not comment_entered:
            try:
                text_input = page.locator("input[type='text']").last
                if text_input.is_visible(timeout=2000):
                    text_input.fill(comment)
                    comment_entered = True
                    log("   ✓ Entered comment in text input")
            except:
                pass
        
        if not comment_entered:
            log("   ⚠️ Could not find comment field, continuing anyway...")
        
        # ========== STEP 4: Click Submit ==========
        log("   Step 4: Submitting dispute...")
        submitted = False
        
        # Try multiple submit button selectors
        for selector in [
            "button:has-text('SUBMIT DISPUTE')",
            "button:has-text('Submit Dispute')",
            "button:has-text('SUBMIT')",
            "button:has-text('Submit')",
            "button[type='submit']"
        ]:
            try:
                btn = page.locator(selector).first
                if btn.is_visible(timeout=1000):
                    btn.click()
                    submitted = True
                    log(f"   ✓ Clicked submit button")
                    break
            except:
                continue
        
        if not submitted:
            log("   ❌ Could not find submit button")
            return False
        
        # Wait for submission to complete
        time.sleep(3)
        
        # Check for success (form should close or we should see a success message)
        try:
            if page.locator("text=successfully").is_visible(timeout=2000):
                log("   ✓ Dispute submitted successfully")
            elif page.locator("text=ERROR").is_visible(timeout=1000):
                log("   ⚠️ Error message appeared, but continuing...")
        except:
            pass
        
        return True
        
    except Exception as e:
        log(f"   ❌ Error in dispute form: {str(e)[:80]}")
        return False

def scan_invoices(page):
    """Scan the invoice list"""
    log("Scanning invoice list...")
    
    try:
        page.wait_for_selector("table tbody", timeout=30000)
        time.sleep(2)
    except Exception as e:
        log(f"Error waiting for table: {e}")
        return []

    all_rows = page.locator("tbody tr").all()
    found_invoices = []
    
    for row in all_rows:
        row_text = row.text_content() or ""
        invoice_match = re.search(r'\d-\d{3}-\d{5}', row_text)
        invoice_num = invoice_match.group() if invoice_match else "Unknown"
        
        status = "Unknown"
        if "Transportation" in row_text: status = "Transportation"
        elif "OPEN IN DISPUTE" in row_text: status = "Disputed"
        elif "Duty/Tax" in row_text: status = "Duty/Tax"
        
        found_invoices.append({
            "invoice": invoice_num,
            "type": status,
            "text": row_text[:100]
        })
    
    save_invoices(found_invoices)
    duty_tax_count = sum(1 for inv in found_invoices if inv["type"] == "Duty/Tax")
    log(f"Found {len(found_invoices)} invoices, {duty_tax_count} Duty/Tax to process.")
    return found_invoices

def process_invoice(page, invoice_number, config):
    """Process a single invoice"""
    invoice_no_clean = invoice_number.replace("-", "")
    account_no = config.get("account_number", "202744967")
    invoice_url = f"https://www.fedex.com/online/billing/cbs/invoices/invoice-details?accountNo={account_no}&countryCode=CA&invoiceNumber={invoice_no_clean}"
    
    page.goto(invoice_url, wait_until="domcontentloaded")
    time.sleep(3)
    
    if "invoice-details" not in page.url:
        log(f"Failed to load invoice {invoice_number}")
        return False
    
    # ========== STEP 1: Get ALL tracking IDs from the main shipments table ==========
    log("📋 Scanning shipments table...")
    all_tracking_ids = set()
    try:
        page.wait_for_selector("tbody tr", timeout=10000)
        time.sleep(2)
        
        # Check if there's pagination in the main table and handle it
        main_rows = page.locator("tbody tr").all()
        for row in main_rows:
            row_text = row.text_content() or ""
            tracking_nums = re.findall(r'\b\d{12}\b', row_text)
            all_tracking_ids.update(tracking_nums)
        
        log(f"   Found {len(all_tracking_ids)} tracking IDs in shipments table")
    except Exception as e:
        log(f"Error scanning shipments table: {e}")
        return False
    
    # ========== STEP 2: Get ALL already-disputed tracking IDs from Dispute Activity ==========
    log("🔍 Checking Dispute Activity section...")
    already_disputed_duty_tax = set()
    already_disputed_other = set()  # Track other dispute reasons too
    
    try:
        # Try to find and click the Dispute Activity section (try multiple selectors)
        dispute_section = None
        for selector in ["text=Dispute activity", "text=Dispute Activity", "text=DISPUTE ACTIVITY"]:
            try:
                elem = page.locator(selector).first
                if elem.is_visible(timeout=2000):
                    dispute_section = elem
                    break
            except:
                continue
        
        if dispute_section:
            log("   Found Dispute Activity section, clicking to expand...")
            dispute_section.click()
            time.sleep(3)  # Wait for section to expand and load
            
            # Wait for the dispute table to load - try multiple selectors
            table_loaded = False
            for selector in ["text=AIR WAYBILL NUMBER", "text=Air Waybill", "th:has-text('AIR WAYBILL')"]:
                try:
                    page.wait_for_selector(selector, timeout=3000)
                    table_loaded = True
                    break
                except:
                    continue
            
            if not table_loaded:
                log("   ⚠ Could not find dispute table headers, trying to read anyway...")
            
            time.sleep(2)
            
            # Scroll to load all dispute entries if the list is long
            # First, try to find if there's a scrollable container
            try:
                for _ in range(10):
                    page.keyboard.press("End")
                    time.sleep(0.3)
                page.keyboard.press("Home")  # Go back to top
                time.sleep(0.5)
            except:
                pass
            
            # Get all rows in the dispute activity table
            dispute_table_rows = page.locator("tr").all()
            
            log(f"   Scanning {len(dispute_table_rows)} rows for existing disputes...")
            
            found_disputes = 0
            for row in dispute_table_rows:
                row_text = row.text_content() or ""
                
                # Skip header row or empty rows
                if not row_text.strip():
                    continue
                if "DISPUTE ID" in row_text.upper() and "AIR WAYBILL" in row_text.upper():
                    continue
                if "DISPUTE REASON" in row_text.upper():
                    continue
                
                # Extract the AIR WAYBILL NUMBER (12-digit tracking ID)
                tracking_nums = re.findall(r'\b\d{12}\b', row_text)
                
                if tracking_nums:
                    tracking_num = tracking_nums[0]
                    found_disputes += 1
                    
                    # Check the DISPUTE REASON column
                    if "Duty/Tax" in row_text or "Duty / Tax" in row_text:
                        already_disputed_duty_tax.add(tracking_num)
                        log(f"      ✓ {tracking_num} - Duty/Tax (SKIP)")
                    else:
                        # Other reasons like "Duplicate shipment", "Dimensions", etc.
                        already_disputed_other.add(tracking_num)
                        # Extract the reason for logging
                        reason = "Other"
                        for r in ["Duplicate", "Dimension", "Weight", "Address", "Service", "Rate"]:
                            if r in row_text:
                                reason = r
                                break
                        log(f"      ○ {tracking_num} - {reason} (will still dispute for Duty/Tax)")
            
            log(f"")
            log(f"   📊 Dispute Activity Summary:")
            log(f"      Total disputes found: {found_disputes}")
            log(f"      Already Duty/Tax: {len(already_disputed_duty_tax)}")
            log(f"      Other reasons: {len(already_disputed_other)}")
        else:
            log("   ℹ No Dispute Activity section found (invoice may have no disputes yet)")
    except Exception as e:
        log(f"   ⚠ Error reading Dispute Activity: {str(e)[:100]}")
        import traceback
        traceback.print_exc()
    
    # ========== STEP 3: Calculate which tracking IDs need to be disputed ==========
    to_dispute = all_tracking_ids - already_disputed_duty_tax
    
    log(f"")
    log(f"═══════════════════════════════════════════════════")
    log(f"📊 SUMMARY FOR INVOICE {invoice_number}")
    log(f"═══════════════════════════════════════════════════")
    log(f"   Tracking IDs in shipments table: {len(all_tracking_ids)}")
    log(f"   Already disputed (Duty/Tax):     {len(already_disputed_duty_tax)}")
    log(f"   Disputed (other reasons):        {len(already_disputed_other)}")
    log(f"   ─────────────────────────────────")
    log(f"   NEED TO DISPUTE:                 {len(to_dispute)}")
    log(f"═══════════════════════════════════════════════════")
    
    if len(to_dispute) == 0:
        log(f"✅ All tracking IDs already disputed for Duty/Tax! Nothing to do.")
        return True
    
    # List out which ones we will dispute
    log(f"")
    log(f"Will dispute these {len(to_dispute)} tracking IDs:")
    for tid in sorted(to_dispute):
        log(f"   → {tid}")
    
    # ========== STEP 4: Process each tracking ID that needs disputing ==========
    # Re-get the rows since we may have navigated
    try:
        rows = page.locator("tbody tr").all()
        
        disputed_count = 0
        for row in rows:
            # Check for stop command
            state = load_state()
            if state.get("command") == "stop":
                log("Stop command received.")
                return False
            
            row_text = row.text_content() or ""
            tracking_nums = re.findall(r'\b\d{12}\b', row_text)
            
            if not tracking_nums:
                continue
            tracking_num = tracking_nums[0]
            
            # Skip if already disputed for Duty/Tax
            if tracking_num in already_disputed_duty_tax:
                log(f"⏭ Skipping {tracking_num} (already disputed for Duty/Tax)")
                update_stat("skipped", increment=True)
                continue
            
            # This one needs to be disputed
            log(f"📝 Disputing {tracking_num}...")
            try:
                btns = row.locator("button").all()
                if not btns:
                    continue
                
                btns[0].evaluate("element => element.click()")
                time.sleep(0.5)
                
                page.get_by_text("Dispute", exact=True).click()
                time.sleep(2)
                
                # Check for "Item already in dispute status" popup
                try:
                    already_popup = page.locator("text=already in dispute").first
                    if already_popup.is_visible(timeout=1500):
                        log(f"⏭️ {tracking_num} - Already in dispute status (pending), skipping...")
                        update_stat("skipped", increment=True)
                        # Close the popup by clicking the X or pressing Escape
                        try:
                            close_btn = page.locator("button:has-text('×'), [aria-label='Close'], svg[data-icon='times']").first
                            if close_btn.is_visible(timeout=500):
                                close_btn.click()
                            else:
                                page.keyboard.press("Escape")
                        except:
                            page.keyboard.press("Escape")
                        time.sleep(1)
                        continue
                except:
                    pass  # No popup, continue with dispute form
                
                # Handle dispute form with multiple fallback methods
                if not handle_dispute_form(page, config):
                    log(f"❌ Failed to complete dispute form for {tracking_num}")
                    update_stat("errors", increment=True)
                    # Try to close any open dialog
                    try:
                        page.keyboard.press("Escape")
                        time.sleep(1)
                    except:
                        pass
                    continue
                
                log(f"✅ Successfully disputed {tracking_num}")
                update_stat("disputed", increment=True)
                disputed_count += 1
                
                # Handle error popup
                try:
                    if page.locator("text=ERROR CODE").is_visible(timeout=1000):
                        log("⚠️ Handling error popup...")
                        page.locator("button:has-text('CLOSE')").click()
                        time.sleep(1)
                except:
                    pass
                
            except Exception as e:
                log(f"❌ Error disputing {tracking_num}: {str(e)[:80]}")
                update_stat("errors", increment=True)
                # Try to recover
                try:
                    page.keyboard.press("Escape")
                    time.sleep(1)
                except:
                    pass
                continue
        
        log(f"✓ Finished invoice {invoice_number} - Disputed {disputed_count} tracking IDs")
        return True
                
    except Exception as e:
        log(f"Error processing shipments: {e}")
        return False

def main():
    """Main worker - LOGIN MODE then PROCESSING MODE"""
    print("=" * 50)
    print("FedEx Dispute Bot - Browser Worker")
    print("=" * 50)
    
    # Initialize state
    save_state({"command": "idle", "status": "starting"})
    save_logs({"logs": [], "stats": {"disputed": 0, "skipped": 0, "errors": 0, "invoices_processed": 0, "total_invoices": 0}, "invoices": []})
    
    # Load config
    config = {}
    try:
        with open("bot_config.json", 'r') as f:
            config = json.load(f)
    except:
        config = {
            "user_data_dir": "./user_data_v6",
            "account_number": "202744967",
            "dispute_comment": "Reason for dispute- Products are CUSMA compliant. COO is Canada. FTN CCP 10221998 / PWDBW 7702060 Database and USMCA on file.",
            "fedex_url": "https://www.fedex.com/en-ca/logged-in-home.html"
        }
    
    with sync_playwright() as p:
        # ========== PHASE 1: LOGIN (Visible Browser) ==========
        log("🚀 Launching browser for login...")
        
        browser_context = p.chromium.launch_persistent_context(
            user_data_dir=config.get('user_data_dir', './user_data_v6'),
            headless=False,  # VISIBLE for login
            channel="chrome",
            args=["--disable-blink-features=AutomationControlled"],
            viewport={"width": 1280, "height": 800}
        )
        
        page = browser_context.pages[0]
        
        fedex_url = config.get('fedex_url', "https://www.fedex.com/en-ca/logged-in-home.html")
        log(f"📍 Navigating to {fedex_url}...")
        
        try:
            page.goto(fedex_url, timeout=60000, wait_until="domcontentloaded")
        except Exception as e:
            log(f"Navigation warning: {e}")
        
        log("=" * 40)
        log("👤 PLEASE LOG IN TO FEDEX NOW")
        log("=" * 40)
        log("Once logged in, go back to the UI and click 'Start Processing'")
        save_state({"command": "idle", "status": "waiting_for_login"})
        
        # Wait for user to click "Start Processing" in the UI
        while True:
            state = load_state()
            command = state.get("command", "idle")
            
            if command == "stop":
                log("Stopping...")
                browser_context.close()
                save_state({"command": "idle", "status": "stopped"})
                return
            
            if command == "start":
                break
            
            time.sleep(1)
        
        # ========== PHASE 2: PROCESSING (Can minimize or work in background) ==========
        log("=" * 40)
        log("🤖 BOT TAKING OVER - You can minimize the browser")
        log("=" * 40)
        save_state({"command": "processing", "status": "running"})
        
        # Navigate to invoices
        navigate_to_invoices(page)
        
        # Scan invoices
        found_invoices = scan_invoices(page)
        
        # Filter for Duty/Tax only
        to_process = [inv["invoice"] for inv in found_invoices if inv["type"] == "Duty/Tax"]
        total = len(to_process)
        update_stat("total_invoices", total)
        
        if total == 0:
            log("No Duty/Tax invoices to process!")
            save_state({"command": "idle", "status": "completed"})
            browser_context.close()
            return
        
        log(f"📋 Processing {total} Duty/Tax invoices...")
        
        for i, invoice_num in enumerate(to_process):
            # Check for stop
            state = load_state()
            if state.get("command") == "stop":
                log("Stopping by user request...")
                break
            
            update_stat("invoices_processed", i + 1)
            log(f"")
            log(f"━━━ Invoice {i+1}/{total}: {invoice_num} ━━━")
            
            try:
                process_invoice(page, invoice_num, config)
            except Exception as e:
                log(f"❌ Error: {e}")
                update_stat("errors", increment=True)
                try:
                    page.goto("https://www.fedex.com/online/billing/cbs/invoices", wait_until="domcontentloaded")
                    time.sleep(3)
                except:
                    pass
        
        # Done!
        log("")
        log("=" * 40)
        logs_data = load_logs()
        stats = logs_data["stats"]
        log(f"🎉 COMPLETED!")
        log(f"   Disputed: {stats['disputed']}")
        log(f"   Skipped:  {stats['skipped']}")
        log(f"   Errors:   {stats['errors']}")
        log("=" * 40)
        
        save_state({"command": "idle", "status": "completed"})
        browser_context.close()
    
    print("Browser Worker Finished")

if __name__ == "__main__":
    main()

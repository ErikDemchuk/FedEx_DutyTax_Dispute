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

def log_event(title, description, status="processing", tags=None, details=None, data=None):
    """Log a structured event"""
    if tags is None: tags = []
    if details is None: details = []
    if data is None: data = {}
    timestamp = datetime.now().strftime("%H:%M:%S")
    
    event = {
        "timestamp": timestamp,
        "title": title,
        "description": description,
        "status": status,
        "tags": tags,
        "details": details,
        "data": data
    }
    
    logs_data = load_logs()
    # Ensure logs is a list of objects, handle legacy strings if any
    if logs_data["logs"] and isinstance(logs_data["logs"][0], str):
        logs_data["logs"] = [] # Clear legacy logs on format switch
        
    logs_data["logs"].append(event)
    logs_data["logs"] = logs_data["logs"][-5000:]
    save_logs(logs_data)
    print(f"[{timestamp}] [{status.upper()}] {title} - {description}")

def log(message, level="INFO"):
    """Legacy log wrapper"""
    # Map legacy logs to generic events
    log_event("System Log", message, "processing", ["System"])

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

STATS_FILE = "stats.json"

def load_persistent_stats():
    """Load persistent stats from file"""
    if os.path.exists(STATS_FILE):
        try:
            with open(STATS_FILE, 'r') as f:
                return json.load(f)
        except:
            pass
    return {"total_disputes": 0, "monthly_disputes": {}}

def save_persistent_stats(stats):
    """Save persistent stats to file"""
    with open(STATS_FILE, 'w') as f:
        json.dump(stats, f)

def update_persistent_stat(increment=False):
    """Update persistent stats (Total and Monthly)"""
    if not increment:
        return
        
    stats = load_persistent_stats()
    stats["total_disputes"] = stats.get("total_disputes", 0) + 1
    
    current_month = datetime.now().strftime("%Y-%m")
    if "monthly_disputes" not in stats:
        stats["monthly_disputes"] = {}
    
    stats["monthly_disputes"][current_month] = stats["monthly_disputes"].get(current_month, 0) + 1
    
    save_persistent_stats(stats)
    
    # Also update the session stats file so UI can read it
    logs_data = load_logs()
    logs_data["stats"]["total_all_time"] = stats["total_disputes"]
    logs_data["stats"]["total_month"] = stats["monthly_disputes"][current_month]
    save_logs(logs_data)

def navigate_to_invoices(page):
    """Navigate from logged-in page to invoices list"""
    # log_event("Accessing FedEx Portal", "Login successful. Navigating to the Invoice Dashboard.", "processing")
    # aggregated into the initialization phase logs usually, or keep silent until scan is done

    # 1. Click "PAY A BILL" - Robust Selectors
    try:
        log("Looking for 'PAY A BILL'...")
        # Try multiple selectors for the Pay A Bill card/link
        selectors = [
            "text=PAY A BILL",
            "a[href*='/billing/']",
            "h3:has-text('PAY A BILL')",
            ".fxg-c-card__content:has-text('PAY A BILL')"
        ]
        
        found = False
        for sel in selectors:
            try:
                elem = page.locator(sel).first
                if elem.is_visible(timeout=2000):
                    elem.click()
                    found = True
                    time.sleep(3)
                    break
            except:
                continue
                
        if not found:
            log("Could not find 'PAY A BILL' button, trying direct URL...")
            page.goto("https://www.fedex.com/online/billing/cbs/invoices", wait_until="domcontentloaded")
            time.sleep(3)
            
    except Exception as e:
        log(f"Navigation error: {e}")

    # 2. Handle "The latest with FedEx Billing Online" Popup -> Click CONTINUE
    try:
        # log("Checking for 'CONTINUE' popup...")
        continue_btn = page.locator("button:has-text('CONTINUE')").first
        if continue_btn.is_visible(timeout=5000):
            log("Popup found, clicking CONTINUE...")
            continue_btn.click()
            time.sleep(3)
    except:
        pass

    # 3. Click "VIEW ALL INVOICES"
    try:
        log("Looking for 'VIEW ALL INVOICES'...")
        view_invoices = page.locator("text=VIEW ALL INVOICES").first
        if view_invoices.is_visible(timeout=5000):
            view_invoices.click()
            time.sleep(3)
        else:
            # Fallback to standard "INVOICES" tab
            page.locator("text=INVOICES").first.click()
            time.sleep(3)
    except:
        pass

    # Final check: are we on the invoices page?
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
    # log_event("Analyzing Invoice List", "Scanning available invoices to identify dispute candidates.", "processing")

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

def process_invoice(page, invoice_number, config, current_index, total_count):
    """Process a single invoice"""
    invoice_no_clean = invoice_number.replace("-", "")
    account_no = config.get("account_number", "202744967")
    invoice_url = f"https://www.fedex.com/online/billing/cbs/invoices/invoice-details?accountNo={account_no}&countryCode=CA&invoiceNumber={invoice_no_clean}"
    
    # Log START event for UI status
    log_event(
        f"Processing Invoice {invoice_number}", 
        f"Processing {current_index}/{total_count}", 
        "processing", 
        ["invoice_start"],
        data={
            "type": "invoice_start",
            "invoice_id": invoice_number,
            "index": current_index,
            "total": total_count
        }
    )

    page.goto(invoice_url, wait_until="domcontentloaded")
    time.sleep(3)

    if "invoice-details" not in page.url:
        log(f"Failed to load invoice {invoice_number}")
        return False
    
    # ========== STEP 1: Get ALL tracking IDs from the main shipments table ==========
    # Initialize invoice log aggregation
    invoice_logs = []
    invoice_status = "pending" # Default to grey/skipped
    dispute_count = 0
    skip_count = 0
    error_count = 0
    
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

        # log(f"   Found {len(all_tracking_ids)} tracking IDs in shipments table")
    except Exception as e:
        log(f"Error scanning shipments table: {e}")
        return False

    # ========== STEP 2: Get ALL already-disputed tracking IDs from Dispute Activity ==========
    # log("🔍 Checking Dispute Activity section...")
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
            dispute_section.click()
            time.sleep(2)
            
            # Scroll to load all dispute entries if the list is long
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
            
            # log(f"   Scanning {len(dispute_table_rows)} rows for existing disputes...")
            
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
                
                # Extract DATE (MM/DD/YYYY)
                date_match = re.search(r'\d{2}/\d{2}/\d{4}', row_text)
                dispute_date = date_match.group() if date_match else "Unknown Date"
                
                if tracking_nums:
                    tracking_num = tracking_nums[0]
                    
                    # Check the DISPUTE REASON column
                    if "Duty/Tax" in row_text or "Duty / Tax" in row_text:
                        already_disputed_duty_tax.add(tracking_num)
                        # Removed per-item logging
                    else:
                        # Other reasons like "Duplicate shipment", "Dimensions", etc.
                        already_disputed_other.add(tracking_num)
        else:
            # log("   ℹ No Dispute Activity section found (invoice may have no disputes yet)")
            pass
    except Exception as e:
        log(f"   ⚠ Error reading Dispute Activity: {str(e)[:100]}")
        import traceback
        traceback.print_exc()
    
    # ========== STEP 3: Calculate which tracking IDs need to be disputed ==========
    to_dispute = all_tracking_ids - already_disputed_duty_tax
    
    if len(to_dispute) == 0:
        # Emit final summary for this invoice (invoice_complete)
        # Format: ✓ InvoiceID — 11 IDs scanned, 0 new disputes (11 already handled)
        
        skip_count_total = len(all_tracking_ids)
        handled_count = len(already_disputed_duty_tax) + len(already_disputed_other)
        
        # Update stats
        update_stat("skipped", skip_count_total, increment=False) 
        logs_data = load_logs()
        logs_data["stats"]["skipped"] = logs_data["stats"].get("skipped", 0) + skip_count_total
        save_logs(logs_data)

        summary_desc = f"{len(all_tracking_ids)} IDs scanned, 0 new disputes ({handled_count} already handled)"

        detail_lines = []
        
        log_event(
            f"✓ {invoice_number}", 
            summary_desc, 
            "pending", # grey/completed state
            ["invoice_complete", "skipped"],
            details=detail_lines,
            data={
                "type": "invoice_complete",
                "invoice_id": invoice_number,
                "stats": {
                    "scanned": len(all_tracking_ids),
                    "disputed": 0,
                    "skipped": skip_count_total,
                    "handled": handled_count
                }
            }
        )
        return True
    
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
                # Log already handled in the scan phase, but we iterate rows here
                # Only count if not counted? 
                # actually we already filtered to_dispute.
                continue
            
            # This one needs to be disputed
            try:
                # Extract amount if possible (usually column 10 or similar, but varies)
                # We will try to parse the text row more carefully
                amount_match = re.search(r'\$\s?([\d,]+\.\d{2})', row_text)
                dispute_amount = amount_match.group(1).replace(',', '') if amount_match else "0.00"

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
                        update_stat("skipped", increment=True)
                        skip_count += 1
                        invoice_logs.append(f"Skipped|1|Pending Status|{tracking_num}")
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
                    # Only counting form errors here
                    update_stat("errors", increment=True)
                    error_count += 1
                    invoice_logs.append(f"Failed|1|Form Error|{tracking_num}")
                    invoice_status = "warning"
                    # Try to close any open dialog
                    try:
                        page.keyboard.press("Escape")
                        time.sleep(1)
                    except:
                        pass
                    continue
                
                update_stat("disputed", increment=True)
                update_persistent_stat(increment=True)
                disputed_count += 1
                invoice_logs.append(f"Disputed|1|Success|{tracking_num}")
                
                # Append to detailed dispute record for report
                # Timestamp, Invoice, TrackingID, Amount
                timestamp_iso = datetime.now().isoformat()
                invoice_logs.append(f"ReportDetail|{timestamp_iso}|{invoice_number}|{tracking_num}|{dispute_amount}")

                # Emit real-time dispute event for Frontend
                log_event(
                    "Dispute Filed",
                    f"Successfully filed dispute for {tracking_num} (${dispute_amount})",
                    "success",
                    ["dispute_filed"],
                    data={
                        "type": "dispute_filed",
                        "invoice_id": invoice_number,
                        "tracking_id": tracking_num,
                        "amount": float(dispute_amount) if dispute_amount else 0.0
                    }
                )

                invoice_status = "processing" 
                
                # Handle error popup
                try:
                    if page.locator("text=ERROR CODE").is_visible(timeout=1000):
                        page.locator("button:has-text('CLOSE')").click()
                        time.sleep(1)
                except:
                    pass
                
            except Exception as e:
                # Only count as error if it's not just a navigation/element issue but a failed dispute attempt
                # update_stat("errors", increment=True) <--- Removed to avoid overcounting
                # error_count += 1
                invoice_logs.append(f"Failed|1|Error: {str(e)[:20]}|{tracking_num}")
                invoice_status = "warning"
                # Try to recover
                try:
                    page.keyboard.press("Escape")
                    time.sleep(1)
                except:
                    pass
                continue
        
        # Final Summary Log for the Invoice (Mixed results)
        # Format: ✓ InvoiceID — 11 IDs scanned, X new disputes (Y already handled)
        handled_count = len(already_disputed_duty_tax) + len(already_disputed_other)
        summary_desc = f"{len(all_tracking_ids)} IDs scanned, {disputed_count} new disputes ({skip_count} skipped)"
        
        # Aggregate any skips from step 2 into invoice_logs if mixed
        if len(already_disputed_duty_tax) > 0:
             for _ in range(len(already_disputed_duty_tax)): update_stat("skipped", increment=True)

        if len(already_disputed_other) > 0:
             for _ in range(len(already_disputed_other)): update_stat("skipped", increment=True)

        log_event(
            f"✓ {invoice_number}", 
            summary_desc, 
            invoice_status, 
            ["invoice_complete"], 
            details=invoice_logs,
            data={
                "type": "invoice_complete",
                "invoice_id": invoice_number,
                "stats": {
                    "scanned": len(all_tracking_ids),
                    "disputed": disputed_count,
                    "skipped": skip_count,
                    "handled": handled_count
                }
            }
        )
        
        return True
                
    except Exception as e:
        log(f"Error processing shipments: {e}")
        
        # Attempt to log partial completion if we have data
        if 'invoice_logs' in locals() and invoice_logs:
             # Final Summary Log for the Invoice (Partial/Failed)
            handled_count = len(already_disputed_duty_tax) + len(already_disputed_other)
            summary_desc = f"{len(all_tracking_ids)} IDs scanned, {disputed_count} new disputes ({skip_count} skipped) - TERMINATED EARLY"
            
            log_event(
                f"✓ {invoice_number} (Partial)", 
                summary_desc, 
                "warning", 
                ["invoice_complete", "partial"], 
                details=invoice_logs,
                data={
                    "type": "invoice_complete",
                    "invoice_id": invoice_number,
                    "stats": {
                        "scanned": len(all_tracking_ids),
                        "disputed": disputed_count,
                        "skipped": skip_count,
                        "handled": handled_count
                    }
                }
            )
        return False

def login_to_fedex(page, username, password):
    """Auto-login to FedEx"""
    # log_event("Initiating Dispute Process", "Starting the automated dispute sequence for the current session.", "processing", ["Browser Initialized", "Session Started"])
    try:
        # Check if already logged in
        try:
            # Check for various indicators of being logged in
            if page.locator("text=Sign Out").first.is_visible(timeout=1000) or \
               page.locator("text=Log Out").first.is_visible(timeout=1000) or \
               page.locator("text=Good afternoon").first.is_visible(timeout=1000) or \
               page.locator("text=Account:").first.is_visible(timeout=1000) or \
               page.locator("[aria-label='My Profile']").first.is_visible(timeout=1000):
                log("Already logged in (verified by element).")
                return True
        except:
            pass

        # Wait for ANY username field
        # log("Waiting for login fields...")
        username_selector = "input#username, input[name='username'], input[type='email'], #userId"
        
        # Try generic wait
        try:
            # Try to handle cookie consent if it appears
            try:
                page.locator("button:has-text('Accept'), button:has-text('ACCEPT')").click(timeout=2000)
            except:
                pass

            page.wait_for_selector(username_selector, timeout=10000)
        except:
            log("⚠️ Timeout waiting for standard login fields.")
            # Maybe we are on a landing page and need to click 'Sign Up or Log In'
            try:
                log("Trying to find 'Sign Up or Log In' button...")
                page.click("text=Sign Up or Log In", timeout=3000)
                time.sleep(2)
                page.click("text=Sign Up / Log In", timeout=3000)
            except:
                pass
        
        # Fill Username - Aggressive Search
        user_filled = False
        
        # List of potential selectors
        selectors = [
            "#userId", 
            "input#username", 
            "input[name='username']", 
            "input[type='email']",
            "input[id*='user']",  # Contains 'user' in ID
            "input[id*='User']"
        ]
        
        # 1. Try standard selectors with force=True
        for selector in selectors:
            try:
                if page.locator(selector).first.is_visible(timeout=500):
                    # log(f"Found username field via {selector}")
                    page.fill(selector, username, force=True)
                    user_filled = True
                    break
            except:
                continue
        
        # 2. Try get_by_label
        if not user_filled:
            try:
                # log("Trying get_by_label('User ID')...")
                page.get_by_label("User ID").fill(username, force=True)
                user_filled = True
            except:
                pass

        # 3. Try finding ANY visible input and checking placeholders/labels
        if not user_filled:
            # log("Trying to find ANY visible input...")
            try:
                inputs = page.locator("input:visible").all()
                for inp in inputs:
                    try:
                        # Check attributes
                        id_attr = inp.get_attribute("id") or ""
                        name_attr = inp.get_attribute("name") or ""
                        placeholder = inp.get_attribute("placeholder") or ""
                        aria_label = inp.get_attribute("aria-label") or ""
                        
                        if any(x in (id_attr + name_attr + placeholder + aria_label).lower() for x in ['user', 'id', 'email', 'login']):
                            # log(f"Found potential username input: {id_attr}")
                            inp.click(force=True)
                            time.sleep(0.5)
                            page.keyboard.type(username, delay=50) # Type like a human
                            user_filled = True
                            break
                    except:
                        continue
            except:
                pass
        
        if not user_filled:
            log("❌ Could not find username field (check static/debug_login_fail.png)")
            page.screenshot(path="static/debug_username_fail.png")
            return False

        # Fill Password - Try multiple selectors including password
        pass_filled = False
        for selector in ["#password", "input#password", "input[name='password']", "input[type='password']"]:
            try:
                if page.is_visible(selector):
                    page.fill(selector, password)
                    pass_filled = True
                    break
            except:
                continue
        
        # Try get_by_label if standard selectors fail
        if not pass_filled:
            try:
                page.get_by_label("Password").fill(password)
                pass_filled = True
            except:
                pass

        if not pass_filled:
            log("❌ Could not find password field")
            return False

        # Click Login
        clicked = False
        for selector in ["button#login_button", "button:has-text('LOG IN')", "button:has-text('Log In')", "button[type='submit']", "#login-btn"]:
            try:
                if page.is_visible(selector):
                    page.click(selector)
                    clicked = True
                    break
            except:
                continue
        
        if not clicked:
            page.keyboard.press("Enter")
        
        # log("Credentials submitted. Verifying...")
        try:
            page.wait_for_load_state("domcontentloaded", timeout=15000)
        except:
            pass
        
        time.sleep(2)
        
        if "secure-login" not in page.url or "logged-in-home" in page.url:
            # log("Login successful.")
            return True
        else:
            log("Login check: Still on login page (might need manual intervention).")
            return False
            
    except Exception as e:
        log(f"Auto-login error: {e}")
        return False

def main():
    """Main worker - LOGIN MODE then PROCESSING MODE"""
    print("=" * 50)
    print("FedEx Dispute Bot - Browser Worker")
    print("=" * 50)
    
    # Initialize state
    save_state({"command": "idle", "status": "waiting_for_login", "start_time": time.time()})
    save_logs({"logs": [], "stats": {"disputed": 0, "skipped": 0, "errors": 0, "invoices_processed": 0, "total_invoices": 0}, "invoices": []})
    
    # Load config
    config = {}
    try:
        with open("bot_config.json", 'r') as f:
            config = json.load(f)
    except:
        log("Could not load bot_config.json")
        return
    
    with sync_playwright() as p:
        # ========== PHASE 1: LOGIN (Visible Browser) ==========
        log_event("System Initialization", "🟢 System Ready. Launching browser...", "processing")
        
        # Launch with specific channel to ensure it opens the real Google Chrome
        browser_context = p.chromium.launch_persistent_context(
            user_data_dir=config.get('user_data_dir', './user_data_v6'),
            headless=False,  # VISIBLE MODE
            channel="chrome", # Force use of Google Chrome
            args=["--disable-blink-features=AutomationControlled", "--start-maximized"],
            viewport=None
        )
        
        page = browser_context.pages[0]
        
        fedex_url = config.get('fedex_url', "https://www.fedex.com/en-ca/logged-in-home.html")
        log(f"📍 Navigating to {fedex_url}...")
        
        try:
            page.goto(fedex_url, timeout=60000, wait_until="domcontentloaded")
        except Exception as e:
            log(f"Navigation warning: {e}")
            
        # Auto-login
        if config.get("username") and config.get("password"):
            if login_to_fedex(page, config["username"], config["password"]):
                log_event("Login Success", "✅ Login complete. Accessing Invoice Dashboard.", "success")
            else:
                log_event("Login Warning", "⚠️ Login might have failed or required manual intervention.", "warning")
        
        log("=" * 40)
        # log("✅ Login complete. Waiting for start command...")
        save_state({"command": "idle", "status": "idle"})
        
        # Load initial stats to display in UI
        stats = load_persistent_stats()
        current_month = datetime.now().strftime("%Y-%m")
        logs_data = load_logs()
        logs_data["stats"]["total_all_time"] = stats["total_disputes"]
        logs_data["stats"]["total_month"] = stats.get("monthly_disputes", {}).get(current_month, 0)
        save_logs(logs_data)
        
        # Wait for user to click "Start Processing" in the UI
        # (Removed for one-click operation - worker starts immediately)
        # while True:
        #     state = load_state()
        #     command = state.get("command", "idle")
        #    
        #     if command == "stop":
        #         log("Stopping...")
        #         browser_context.close()
        #         save_state({"command": "idle", "status": "stopped"})
        #         return
        #    
        #     if command == "start":
        #         break
        #    
        #     time.sleep(1)
        
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
        # The list 'found_invoices' comes from scanning the table top-to-bottom (Newest to Oldest)
        # Previously we reversed it to process Oldest (bottom) first.
        # User wants to process Newest (top) first, so we simply do NOT reverse it.
        # to_process.reverse()  <-- Removed
        
        total = len(to_process)
        update_stat("total_invoices", total)
        
        if total == 0:
            log("No Duty/Tax invoices to process!")
            save_state({"command": "idle", "status": "completed"})
            browser_context.close()
            return
        
        log(f"📋 Processing {total} Duty/Tax invoices (Top-to-Bottom)...")
        
        for i, invoice_num in enumerate(to_process):
            # Check for stop
            state = load_state()
            if state.get("command") == "stop":
                log("Stopping by user request...")
                save_state({"command": "idle", "status": "stopped"})
                browser_context.close()
                return
            
            update_stat("invoices_processed", i + 1)
            # log(f"")
            # log(f"━━━ Invoice {i+1}/{total}: {invoice_num} ━━━")
            
            try:
                process_invoice(page, invoice_num, config, i + 1, total)
            except Exception as e:
                log(f"❌ Error: {e}")
                # Only update global error count on invoice-level crash
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
        
        # Emit detailed Job Complete event for Frontend
        log_event(
            "Job Complete", 
            f"Processed {stats['invoices_processed']} invoices. Filed {stats['disputed']} disputes.", 
            "success", 
            ["job_complete"], 
            data={
                "type": "job_complete",
                "stats": {
                    "disputed": stats['disputed'],
                    "skipped": stats['skipped'],
                    "errors": stats['errors'],
                    "invoices_processed": stats['invoices_processed'],
                    "total_invoices": stats['total_invoices']
                }
            }
        )
        
        save_state({"command": "idle", "status": "completed"})
        browser_context.close()
    
    print("Browser Worker Finished")

if __name__ == "__main__":
    main()

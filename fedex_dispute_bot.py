import time
import re
from playwright.sync_api import sync_playwright, Page

# Configuration
USER_DATA_DIR = "./user_data_v6"
FEDEX_URL = "https://www.fedex.com/en-ca/logged-in-home.html"
HEADLESS = False

# Dispute comment text
DISPUTE_COMMENT = "Reason for dispute- Products are CUSMA compliant. COO is Canada. FTN CCP 10221998 / PWDBW 7702060 Database and USMCA on file."

def handle_dispute_form(page: Page):
    """
    Handles the dispute form page.
    Selects 'Incorrect charge' -> 'Duty/Tax', types comment, and submits.
    
    The FedEx site uses custom dropdown components (not standard <select> elements).
    We need to click the dropdown to open it, then click the option.
    """
    print("    Handling dispute form...")
    try:
        # Wait for the dispute form page to load
        print("    Waiting for dispute form to load...")
        time.sleep(2)  # Give the page time to render
        
        print(f"    Current URL: {page.url}")
        
        # 1. Click on "Dispute type" dropdown and select "Incorrect charge"
        print("    Step 1: Selecting Dispute Type -> 'Incorrect charge'...")
        try:
            # Find the Dispute type dropdown - look for the label then find the dropdown near it
            dispute_type_dropdown = page.locator("text=Dispute type").locator("..").locator("div[role='button'], div[class*='select'], button, [class*='dropdown']").first
            
            # If that doesn't work, try finding by the "Select" placeholder text
            if not dispute_type_dropdown.is_visible(timeout=2000):
                dispute_type_dropdown = page.locator("text=Dispute type*").locator("xpath=following::*[contains(text(),'Select')]").first
            
            # Click to open the dropdown
            dispute_type_dropdown.click()
            time.sleep(1)
            
            # Now click on "Incorrect charge" option
            page.locator("text=Incorrect charge").first.click()
            print("    ✓ Selected 'Incorrect charge'")
            time.sleep(1.5)  # Wait for the second dropdown to appear
            
        except Exception as e:
            print(f"    ERROR with method 1 for Dispute Type: {e}")
            print("    Trying alternative method...")
            try:
                # Alternative: Click any element containing "Select" that's in a dropdown-like container
                page.click("text=Select >> nth=0")
                time.sleep(0.5)
                page.click("text=Incorrect charge")
                print("    ✓ Selected 'Incorrect charge' (alt method)")
                time.sleep(1.5)
            except Exception as e2:
                print(f"    ERROR with alternative method: {e2}")
                return False
        
        # 2. Click on "Dispute reason" dropdown and select "Duty/Tax"
        print("    Step 2: Selecting Dispute Reason -> 'Duty/Tax'...")
        try:
            # The second dropdown should now be visible
            dispute_reason_dropdown = page.locator("text=Dispute reason").locator("..").locator("div[role='button'], div[class*='select'], button, [class*='dropdown']").first
            
            if not dispute_reason_dropdown.is_visible(timeout=2000):
                dispute_reason_dropdown = page.locator("text=Dispute reason*").locator("xpath=following::*[contains(text(),'Select')]").first
            
            dispute_reason_dropdown.click()
            time.sleep(1)
            
            # Click on "Duty/Tax" option
            page.locator("text=Duty/Tax").first.click()
            print("    ✓ Selected 'Duty/Tax'")
            time.sleep(1)
            
        except Exception as e:
            print(f"    ERROR with method 1 for Dispute Reason: {e}")
            print("    Trying alternative method...")
            try:
                page.click("text=Select >> nth=0")
                time.sleep(0.5)
                page.click("text=Duty/Tax")
                print("    ✓ Selected 'Duty/Tax' (alt method)")
                time.sleep(1)
            except Exception as e2:
                print(f"    ERROR with alternative method: {e2}")
        
        # 3. Fill comment
        print("    Step 3: Typing comment...")
        try:
            textarea = page.locator("textarea").first
            if textarea.is_visible(timeout=2000):
                textarea.fill(DISPUTE_COMMENT)
                print("    ✓ Filled comment in textarea")
            else:
                comment_input = page.locator("input[type='text']").last
                comment_input.fill(DISPUTE_COMMENT)
                print("    ✓ Filled comment in input field")
            time.sleep(0.5)
        except Exception as e:
            print(f"    WARNING: Could not fill comment: {e}")
        
        # 4. Submit
        print("    Step 4: Clicking SUBMIT DISPUTE...")
        try:
            submit_btn = page.locator("button:has-text('SUBMIT'), button:has-text('Submit')").first
            submit_btn.click()
            print("    ✓ Clicked SUBMIT DISPUTE")
            
            # Wait for response
            time.sleep(3)
            
            # Check for error popup and handle it
            error_handled = handle_error_popup(page)
            if error_handled:
                print("    ⚠️ Error occurred but was handled, continuing...")
                return False  # Mark as not successful but don't crash
            
            # Check for success message
            try:
                success_msg = page.locator("text=successfully submitted").first
                if success_msg.is_visible(timeout=2000):
                    print("    ✓ Dispute submitted successfully")
                    return True
            except:
                pass
            
            # If we got here without error, assume success
            print("    ✓ Dispute submitted (assumed success)")
            return True
            
        except Exception as e:
            print(f"    ERROR clicking submit: {e}")
            # Try to handle any error popup that appeared
            handle_error_popup(page)
            return False
        
    except Exception as e:
        print(f"    ERROR in dispute form: {e}")
        import traceback
        traceback.print_exc()
        # Try to handle any error popup
        handle_error_popup(page)
        return False


def handle_error_popup(page: Page):
    """
    Handles FedEx error popups like "ERROR CODE: 0000".
    Clicks CLOSE button and returns True if an error was found and handled.
    """
    try:
        # Look for error popup indicators
        error_indicators = [
            "ERROR CODE",
            "error processing your request",
            "try again later",
            "Error processing"
        ]
        
        for indicator in error_indicators:
            error_popup = page.locator(f"text={indicator}").first
            if error_popup.is_visible(timeout=1000):
                print(f"    ⚠️ Detected error popup: {indicator}")
                
                # Try to click CLOSE button
                try:
                    close_btn = page.locator("button:has-text('CLOSE'), button:has-text('Close')").first
                    if close_btn.is_visible(timeout=2000):
                        close_btn.click()
                        print("    ✓ Clicked CLOSE on error popup")
                        time.sleep(1)
                        return True
                except:
                    pass
                
                # Try clicking X button
                try:
                    x_btn = page.locator("[aria-label='close'], [aria-label='Close'], button:has-text('×')").first
                    if x_btn.is_visible(timeout=1000):
                        x_btn.click()
                        print("    ✓ Clicked X on error popup")
                        time.sleep(1)
                        return True
                except:
                    pass
                
                # Try pressing Escape
                try:
                    page.keyboard.press("Escape")
                    print("    ✓ Pressed Escape to close popup")
                    time.sleep(1)
                    return True
                except:
                    pass
                
                return True  # Error was found even if we couldn't close it
        
        return False  # No error popup found
        
    except:
        return False


def process_shipments(page: Page):
    """
    Loops through shipments in the current invoice and disputes them.
    ONLY skips tracking numbers that were already disputed under "Duty/Tax" reason.
    If disputed under other reasons (Dimensions, Duplicate, etc.), we STILL dispute for Duty/Tax.
    Returns tuple: (disputed_count, skipped_count)
    """
    print("  Processing shipments...")
    
    # Step 1: Check Dispute Activity section for tracking numbers disputed under "Duty/Tax" ONLY
    already_disputed_duty_tax = set()
    try:
        print("  Checking Dispute Activity section for Duty/Tax disputes...")
        
        # Look for Dispute Activity section
        dispute_section = page.locator("text=Dispute Activity").first
        
        if dispute_section.is_visible(timeout=3000):
            print("    ✓ Found Dispute Activity section")
            
            # Try to expand it if collapsed
            try:
                dispute_section.click()
                time.sleep(1)
            except:
                pass
            
            # Find rows that contain "Duty/Tax" - ONLY these should be skipped
            try:
                # Look for table rows containing "Duty/Tax"
                duty_tax_rows = page.locator("tr:has-text('Duty/Tax')").all()
                for row in duty_tax_rows:
                    row_text = row.text_content() or ""
                    tracking_nums = re.findall(r'\b\d{12}\b', row_text)
                    already_disputed_duty_tax.update(tracking_nums)
                
                if already_disputed_duty_tax:
                    print(f"    ✓ Found {len(already_disputed_duty_tax)} tracking numbers disputed for Duty/Tax:")
                    for tn in list(already_disputed_duty_tax)[:5]:
                        print(f"      - {tn}")
                    if len(already_disputed_duty_tax) > 5:
                        print(f"      ... and {len(already_disputed_duty_tax) - 5} more")
                else:
                    print("    ℹ️ No Duty/Tax disputes found (other dispute types will be re-disputed)")
            except Exception as e:
                print(f"    Error extracting Duty/Tax disputes: {e}")
        else:
            print("    ℹ️ No Dispute Activity section (this invoice has no disputes yet)")
    except Exception as e:
        print(f"    Error checking Dispute Activity: {e}")
    
    # Quick check: Count total shipments vs already disputed for Duty/Tax
    try:
        all_shipment_rows = page.locator("tbody tr").all()
        total_shipments = 0
        shipment_tracking_nums = set()
        for row in all_shipment_rows:
            row_text = row.text_content() or ""
            tracking_in_row = re.findall(r'\b\d{12}\b', row_text)
            if tracking_in_row:
                total_shipments += 1
                shipment_tracking_nums.update(tracking_in_row)
        
        # Check how many still need Duty/Tax dispute
        not_disputed_duty_tax = shipment_tracking_nums - already_disputed_duty_tax
        
        if total_shipments > 0 and len(not_disputed_duty_tax) == 0:
            print(f"\n  🎉 ALL {total_shipments} shipments already disputed for Duty/Tax! Skipping this invoice.")
            return 0, total_shipments
        elif already_disputed_duty_tax:
            print(f"\n  📊 {len(not_disputed_duty_tax)} of {total_shipments} shipments need Duty/Tax dispute")
    except:
        pass
    
    # Step 2: Process shipment rows
    disputed_count = 0
    skipped_count = 0
    
    try:
        print("  Looking for shipment table...")
        page.wait_for_selector("tbody tr", timeout=10000)
        time.sleep(2)
        
        rows = page.locator("tbody tr").all()
        print(f"  Found {len(rows)} rows in the table")
        
        for i, row in enumerate(rows):
            # Skip header rows
            if row.locator("th").count() > 0:
                continue
            
            row_text = row.text_content() or ""
            
            # Extract tracking number from this row
            tracking_nums_in_row = re.findall(r'\b\d{12,14}\b', row_text)
            
            if not tracking_nums_in_row:
                continue  # Skip rows without tracking numbers
            
            tracking_num = tracking_nums_in_row[0]
            
            # Check if already disputed for Duty/Tax specifically
            is_disputed_duty_tax = False
            
            # Method 1: Check against Duty/Tax Dispute Activity list
            if tracking_num in already_disputed_duty_tax:
                print(f"  Row {i+1} (Tracking: {tracking_num}): ⏭️ Already disputed for Duty/Tax - SKIPPING")
                is_disputed_duty_tax = True
            
            if is_disputed_duty_tax:
                skipped_count += 1
                continue
            
            print(f"  Row {i+1} (Tracking: {tracking_num}): Processing...")
            try:
                row.scroll_into_view_if_needed()
                time.sleep(0.5)
                
                # Find the action menu button
                try:
                    btns = row.locator("button").all()
                    
                    if not btns or len(btns) == 0:
                        print(f"    ERROR: No buttons found in row - skipping")
                        continue
                    
                    menu_btn = btns[0]
                    print(f"    Found {len(btns)} button(s) in row, using first one")
                    
                    # Use JavaScript click
                    print(f"    Clicking ... menu (JavaScript)")
                    menu_btn.evaluate("element => element.click()")
                    time.sleep(1)
                    
                except Exception as e:
                    print(f"    ERROR: Could not click menu button: {e}")
                    continue
                
                # Click "Dispute" in the menu
                page.get_by_text("Dispute", exact=True).click()
                time.sleep(0.5)
                
                # Fill out the dispute form
                if handle_dispute_form(page):
                    disputed_count += 1
                    print(f"    ✓ Successfully disputed tracking {tracking_num}")
                else:
                    print(f"    ⚠️ Issue with tracking {tracking_num} (may have been processed)")
                
                # Handle any lingering error popups before moving to next row
                handle_error_popup(page)
                
                # Make sure we're back on the invoice page
                time.sleep(1)
                if "create-dispute" in page.url:
                    print("    Still on dispute page, navigating back...")
                    page.go_back()
                    time.sleep(2)
                
            except Exception as e:
                print(f"    ✗ Error: {e}")
                # Handle any error popup
                handle_error_popup(page)
                # Try to recover
                try:
                    if "create-dispute" in page.url:
                        page.go_back()
                        time.sleep(2)
                except:
                    pass
                continue
        
    except Exception as e:
        print(f"  Error processing shipments: {e}")
    
    return disputed_count, skipped_count


def process_invoices(page: Page):
    """
    Scrapes the invoice list and processes 'Duty/Tax' invoices.
    Skips 'Transportation' invoices and already-disputed invoices.
    Processes from TOP to BOTTOM in the order shown on the page.
    """
    print("\n" + "="*60)
    print("SCANNING INVOICE LIST...")
    print("="*60)
    
    # Wait for invoice table to appear
    print("Waiting for invoice table to appear...")
    try:
        page.wait_for_selector("table tbody", timeout=30000)
        print("Table found! Waiting for it to populate...")
        time.sleep(3)
    except Exception as e:
        print(f"Error waiting for table: {e}")
        print("Trying to proceed anyway...")
    
    # Find all rows and categorize them
    print("\nAnalyzing invoice list (top to bottom)...")
    
    # Get all data rows (skip header)
    all_rows = page.locator("tbody tr").all()
    
    # Categorize each row
    duty_tax_rows = []
    skipped_transportation = 0
    skipped_disputed = 0
    
    for row in all_rows:
        row_text = row.text_content() or ""
        
        # Try to extract invoice number for logging
        invoice_match = re.search(r'\d-\d{3}-\d{5}', row_text)
        invoice_num = invoice_match.group() if invoice_match else "Unknown"
        
        if "Transportation" in row_text:
            print(f"  ⏭️  {invoice_num} - Transportation - SKIPPING")
            skipped_transportation += 1
        elif "OPEN IN DISPUTE" in row_text:
            print(f"  ⏭️  {invoice_num} - Already in dispute - SKIPPING")
            skipped_disputed += 1
        elif "Duty/Tax" in row_text:
            print(f"  ✅ {invoice_num} - Duty/Tax - WILL PROCESS")
            duty_tax_rows.append(row)
    
    # Store invoice numbers for processing
    invoice_numbers = []
    for row in duty_tax_rows:
        row_text = row.text_content() or ""
        invoice_match = re.search(r'\d-\d{3}-\d{5}', row_text)
        if invoice_match:
            invoice_numbers.append(invoice_match.group())
    
    count = len(invoice_numbers)
    print(f"\n📊 Summary: {count} Duty/Tax to process, {skipped_transportation} Transportation skipped, {skipped_disputed} already disputed")
    
    if count == 0:
        print("No Duty/Tax invoices found that need processing.")
        print(f"Current URL: {page.url}")
        return
    
    total_disputed = 0
    total_skipped = 0
    
    # Process each invoice by navigating directly to its URL
    for i, invoice_number in enumerate(invoice_numbers):
        print(f"\n{'='*60}")
        print(f"INVOICE {i+1} of {count}: {invoice_number}")
        print(f"{'='*60}")
        
        try:
            # Construct the invoice detail URL directly
            # Remove hyphens from invoice number for URL
            invoice_no_clean = invoice_number.replace("-", "")
            
            # Build the URL (using the account number from the current session)
            invoice_url = f"https://www.fedex.com/online/billing/cbs/invoices/invoice-details?accountNo=202744967&countryCode=CA&invoiceNumber={invoice_no_clean}"
            
            print(f"  Navigating directly to invoice...")
            print(f"  URL: {invoice_url}")
            
            # Navigate directly to the invoice
            page.goto(invoice_url)
            time.sleep(3)
            
            # Verify we're on the right page
            if "invoice-details" in page.url:
                print(f"  ✓ Successfully opened invoice {invoice_number}")
                
                # Process the shipments in this invoice
                disputed, skipped = process_shipments(page)
                total_disputed += disputed
                total_skipped += skipped
                
                print(f"\n  Invoice {invoice_number} complete: {disputed} disputed, {skipped} skipped")
            else:
                print(f"  ❌ Failed to navigate to invoice {invoice_number}")
                print(f"  Current URL: {page.url}")
            
        except Exception as e:
            print(f"  ERROR processing invoice {invoice_number}: {e}")
            import traceback
            traceback.print_exc()
    
    print(f"\n{'='*60}")
    print(f"ALL INVOICES PROCESSED!")
    print(f"TOTAL: {total_disputed} tracking numbers disputed, {total_skipped} skipped")
    print(f"{'='*60}")


def navigate_to_invoices(page: Page):
    """
    Navigate from the logged-in homepage to the invoice list.
    """
    print(f"\nCurrent URL: {page.url}")
    
    # Step 1: Navigate to FedEx Billing Online
    print("\n1. Navigating to FedEx Billing Online...")
    billing_found = False
    
    # Method 1: Try clicking "VIEW & PAY BILL" in Quick links
    try:
        view_pay_bill = page.locator("text=VIEW & PAY BILL").first
        if view_pay_bill.is_visible(timeout=3000):
            print("   Found 'VIEW & PAY BILL' link...")
            view_pay_bill.click()
            time.sleep(3)
            print("   ✓ Clicked VIEW & PAY BILL")
            billing_found = True
    except Exception as e:
        print(f"   VIEW & PAY BILL not found")
    
    # Method 2: Try clicking "FEDEX BILLING ONLINE" link
    if not billing_found:
        try:
            fedex_billing = page.locator("text=FEDEX BILLING ONLINE").first
            if fedex_billing.is_visible(timeout=3000):
                print("   Found 'FEDEX BILLING ONLINE' link...")
                fedex_billing.click()
                time.sleep(3)
                print("   ✓ Clicked FEDEX BILLING ONLINE")
                billing_found = True
        except Exception as e:
            print(f"   FEDEX BILLING ONLINE not found")
    
    # Method 3: Navigate directly to billing URL
    if not billing_found:
        print("   Navigating directly to billing portal...")
        page.goto("https://www.fedex.com/online/billing/cbs/summary")
        time.sleep(3)
        print("   ✓ Navigated to billing portal directly")
    
    print(f"   Current URL: {page.url}")
    
    # Step 2: Handle any popup that might appear
    print("\n2. Checking for popup...")
    try:
        continue_btn = page.get_by_role("button", name="CONTINUE").first
        if continue_btn.is_visible(timeout=3000):
            print("   Found popup, clicking CONTINUE...")
            continue_btn.click()
            time.sleep(2)
            print("   ✓ Closed popup")
    except:
        print("   No popup found (or already closed)")
    
    # Step 3: Click "INVOICES" in the left sidebar
    print("\n3. Clicking 'INVOICES' in sidebar...")
    invoices_clicked = False
    
    # Method 1: Click INVOICES text in sidebar
    try:
        invoices_link = page.locator("text=INVOICES").first
        if invoices_link.is_visible(timeout=5000):
            invoices_link.click()
            time.sleep(3)
            print("   ✓ Clicked INVOICES")
            invoices_clicked = True
    except Exception as e:
        print(f"   Could not click INVOICES")
    
    # Method 2: Try "VIEW ALL INVOICES" button
    if not invoices_clicked:
        try:
            view_all = page.locator("text=VIEW ALL INVOICES").first
            if view_all.is_visible(timeout=3000):
                view_all.click()
                time.sleep(3)
                print("   ✓ Clicked VIEW ALL INVOICES")
                invoices_clicked = True
        except Exception as e:
            print(f"   VIEW ALL INVOICES not found")
    
    # Method 3: Navigate directly to invoices URL
    if not invoices_clicked:
        print("   Navigating directly to invoices page...")
        page.goto("https://www.fedex.com/online/billing/cbs/invoices")
        time.sleep(3)
        print("   ✓ Navigated to invoices directly")
    
    print(f"\n   Final URL: {page.url}")


def main():
    print("="*60)
    print("FedEx Dispute Bot - FULL MODE")
    print("Processing ALL Duty/Tax invoices")
    print("="*60)
    
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=USER_DATA_DIR,
            headless=HEADLESS,
            channel="chrome",
            args=["--disable-blink-features=AutomationControlled"],
        )
        
        page = context.pages[0]
        page.goto(FEDEX_URL)
        
        print("\n" + "="*60)
        print("INSTRUCTIONS:")
        print("1. Log in to FedEx if needed")
        print("2. Once you see the homepage, press ENTER")
        print("3. Bot will automatically:")
        print("   - Navigate to FedEx Billing Online")
        print("   - Go to Invoices")
        print("   - Process ALL Duty/Tax invoices")
        print("   - Skip Transportation invoices")
        print("   - Skip already-disputed items")
        print("="*60 + "\n")
        input("Press Enter to continue...")
        
        try:
            # Navigate to invoices
            navigate_to_invoices(page)
            
            # Process all invoices
            process_invoices(page)
            
            print("\n" + "="*60)
            print("SUCCESS! All Duty/Tax invoices have been processed.")
            print("="*60)
            
        except Exception as e:
            print("\n" + "="*60)
            print(f"ERROR: {e}")
            print("="*60)
            import traceback
            traceback.print_exc()
        
        print("\nScript finished.")
        input("Press any key to close...")


if __name__ == "__main__":
    main()

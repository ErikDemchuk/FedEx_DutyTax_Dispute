import time
from playwright.sync_api import sync_playwright, Page
import re

# Configuration
USER_DATA_DIR = "./user_data_v6"
FEDEX_URL = "https://www.fedex.com/en-us/billing-online.html"
HEADLESS = False

# TEST MODE: Only process this specific invoice
TEST_INVOICE = "2-700-01643"

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
            # The dropdown shows "Select" initially
            dispute_type_dropdown = page.locator("text=Dispute type").locator("..").locator("div[role='button'], div[class*='select'], button, [class*='dropdown']").first
            
            # If that doesn't work, try finding by the "Select" placeholder text
            if not dispute_type_dropdown.is_visible(timeout=2000):
                # Try to find any clickable element that says "Select" near "Dispute type"
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
                return
        
        # 2. Click on "Dispute reason" dropdown and select "Duty/Tax"
        print("    Step 2: Selecting Dispute Reason -> 'Duty/Tax'...")
        try:
            # The second dropdown should now be visible
            # Look for "Dispute reason" label and find the dropdown
            dispute_reason_dropdown = page.locator("text=Dispute reason").locator("..").locator("div[role='button'], div[class*='select'], button, [class*='dropdown']").first
            
            if not dispute_reason_dropdown.is_visible(timeout=2000):
                # Try finding "Select" text that appears after Dispute reason
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
                # Alternative: Find the second "Select" dropdown
                page.click("text=Select >> nth=0")  # Click first available "Select"
                time.sleep(0.5)
                page.click("text=Duty/Tax")
                print("    ✓ Selected 'Duty/Tax' (alt method)")
                time.sleep(1)
            except Exception as e2:
                print(f"    ERROR with alternative method: {e2}")
        
        # 3. Fill comment
        print("    Step 3: Typing comment...")
        comment_text = "Reason for dispute- Products are CUSMA compliant. COO is Canada. FTN CCP 10221998 / PWDBW 7702060 Database and USMCA on file."
        try:
            # Find textarea or input for comments
            textarea = page.locator("textarea").first
            if textarea.is_visible(timeout=2000):
                textarea.fill(comment_text)
                print("    ✓ Filled comment in textarea")
            else:
                # Try input field
                comment_input = page.locator("input[type='text']").last
                comment_input.fill(comment_text)
                print("    ✓ Filled comment in input field")
            time.sleep(0.5)
        except Exception as e:
            print(f"    WARNING: Could not fill comment: {e}")
        
        # 4. Submit
        print("    Step 4: Clicking SUBMIT DISPUTE...")
        try:
            # Find the submit button - look for button with "SUBMIT" text
            submit_btn = page.locator("button:has-text('SUBMIT'), button:has-text('Submit')").first
            submit_btn.click()
            print("    ✓ Clicked SUBMIT DISPUTE")
            
            # Wait for navigation/confirmation
            time.sleep(4)
            print("    ✓ Dispute submitted successfully")
            
        except Exception as e:
            print(f"    ERROR clicking submit: {e}")
        
    except Exception as e:
        print(f"    ERROR in dispute form: {e}")
        import traceback
        traceback.print_exc()

def process_shipments(page: Page):
    """
    Loops through shipments in the current invoice and disputes them.
    Skips shipments that are already listed in the Dispute Activity section.
    """
    print("  Processing shipments...")
    
    # Step 1: Check Dispute Activity section for already-disputed tracking numbers
    already_disputed = set()
    try:
        print("  Checking Dispute Activity section...")
        # Look for the Dispute Activity section
        if page.locator("text=Dispute Activity").is_visible(timeout=3000):
            print("    Found Dispute Activity section")
            
            # Try to expand it
            try:
                page.locator("text=Dispute Activity").click()
                time.sleep(1)
            except:
                pass
            
            # Extract tracking numbers from the dispute activity table
            # Look for rows with "Duty/Tax" in the dispute reason column
            dispute_table = page.locator("text=AIR WAYBILL NUMBER").locator("xpath=ancestor::table").first
            if dispute_table.is_visible(timeout=2000):
                rows = dispute_table.locator("tbody tr").all()
                for row in rows:
                    row_text = row.text_content() or ""
                    # Extract tracking numbers (12-14 digits)
                    tracking_nums = re.findall(r'\b\d{12,14}\b', row_text)
                    already_disputed.update(tracking_nums)
                
                print(f"    Found {len(already_disputed)} already-disputed tracking numbers: {already_disputed}")
            else:
                print("    Dispute Activity table not found")
        else:
            print("    No Dispute Activity section (this invoice has no disputes yet)")
    except Exception as e:
        print(f"    Error checking Dispute Activity: {e}")
    
    # Step 2: Process shipment rows
    try:
        print("  Looking for shipment table...")
        # Wait for the main shipment table
        page.wait_for_selector("tbody tr", timeout=10000)
        time.sleep(2)
        
        rows = page.locator("tbody tr").all()
        print(f"  Found {len(rows)} rows in the table")
        
        disputed_count = 0
        skipped_count = 0
        
        for i, row in enumerate(rows):
            # Skip header rows
            if row.locator("th").count() > 0:
                continue
            
            row_text = row.text_content() or ""
            
            # Extract tracking number from this row
            tracking_nums_in_row = re.findall(r'\b\d{12,14}\b', row_text)
            
            if not tracking_nums_in_row:
                print(f"  Row {i+1}: No tracking number found - skipping")
                continue
            
            tracking_num = tracking_nums_in_row[0]
            
            # Check if already disputed
            if tracking_num in already_disputed:
                print(f"  Row {i+1} (Tracking: {tracking_num}): Already disputed - SKIPPING")
                skipped_count += 1
                continue
            
            # Also check status column
            if "IN DISPUTE" in row_text or "PAST DUE IN DISPUTE" in row_text:
                print(f"  Row {i+1} (Tracking: {tracking_num}): Status shows IN DISPUTE - SKIPPING")
                skipped_count += 1
                continue
            
            print(f"  Row {i+1} (Tracking: {tracking_num}): Processing...")
            try:
                # Scroll row into view
                row.scroll_into_view_if_needed()
                time.sleep(0.5)
                
                # Find the action menu button (3 dots) - simple and direct approach
                # Just get the first button in the row (which is the ... menu)
                try:
                    # Find all buttons in this row with short timeout
                    btns = row.locator("button").all()
                    
                    if not btns or len(btns) == 0:
                        print(f"    ERROR: No buttons found in row - skipping")
                        continue
                    
                    # The ... menu is typically the first button
                    menu_btn = btns[0]
                    print(f"    Found {len(btns)} button(s) in row, using first one")
                    
                    # Use JavaScript click - most reliable
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
                handle_dispute_form(page)
                disputed_count += 1
                
                print(f"    ✓ Successfully disputed tracking {tracking_num}")
                
            except Exception as e:
                print(f"    ✗ Error: {e}")
                continue
        
        print(f"\n  {'='*60}")
        print(f"  SUMMARY: {disputed_count} disputed, {skipped_count} skipped")
        print(f"  {'='*60}\n")
        
    except Exception as e:
        print(f"  Error processing shipments: {e}")

def main():
    print("="*60)
    print("FedEx Dispute Bot - TEST MODE")
    print(f"Only processing invoice: {TEST_INVOICE}")
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
        print("1. Log in if needed")
        print("2. Press ENTER once you see the homepage")
        print("3. Bot will automatically navigate to Invoice List")
        print(f"4. Then it will process invoice: {TEST_INVOICE}")
        print("="*60 + "\n")
        input("Press Enter to continue...")
        
        print(f"\nCurrent URL: {page.url}")
        
        # Step 1: Navigate to FedEx Billing Online
        # Try multiple methods since the page can vary
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
            print(f"   VIEW & PAY BILL not found: {e}")
        
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
                print(f"   FEDEX BILLING ONLINE not found: {e}")
        
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
            print(f"   Could not click INVOICES: {e}")
        
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
                print(f"   VIEW ALL INVOICES not found: {e}")
        
        # Method 3: Navigate directly to invoices URL
        if not invoices_clicked:
            print("   Navigating directly to invoices page...")
            page.goto("https://www.fedex.com/online/billing/cbs/invoices")
            time.sleep(3)
            print("   ✓ Navigated to invoices directly")
        
        print(f"\nNew URL: {page.url}\n")
        
        # Find and click the specific invoice
        try:
            print(f"Looking for invoice {TEST_INVOICE}...")
            
            # Wait for table
            page.wait_for_selector("table tbody", timeout=10000)
            time.sleep(2)
            
            # Find the row containing our invoice number
            print(f"Searching for row with invoice {TEST_INVOICE}...")
            row = page.locator(f"tr:has-text('{TEST_INVOICE}')").first
            
            if row.is_visible(timeout=5000):
                print(f"   ✓ Found invoice row")
                
                # Scroll into view
                row.scroll_into_view_if_needed()
                time.sleep(1)
                
                # Instead of clicking, construct the URL manually
                # The invoice detail URL follows a predictable pattern
                print(f"Constructing URL for invoice {TEST_INVOICE}...")
                
                # Remove hyphens from invoice number for URL
                invoice_no = TEST_INVOICE.replace("-", "")
                
                # Construct the invoice detail URL with all required parameters
                # Based on the actual URL from FedEx
                invoice_url = f"https://www.fedex.com/online/billing/cbs/invoices/invoice-details?accountNo=202744967&countryCode=CA&invoiceNumber={invoice_no}"
                
                print(f"   Invoice URL: {invoice_url}")
                print(f"   Navigating to invoice detail page...")
                
                # Navigate directly to the URL
                page.goto(invoice_url)
                time.sleep(4)
                
                print(f"   ✓ Successfully navigated to invoice")
                print(f"   Current URL: {page.url}")
                
                print("\n" + "="*60)
                print(f"Processing invoice: {TEST_INVOICE}")
                print("="*60 + "\n")
                
                # Process this invoice
                process_shipments(page)
                
                print("\n" + "="*60)
                print("TEST COMPLETED!")
                print("="*60)
            else:
                print(f"ERROR: Could not find invoice {TEST_INVOICE} in the table")
                
        except Exception as e:
            print(f"ERROR: {e}")
            import traceback
            traceback.print_exc()
        
        print("\nPress any key to close...")
        input()

if __name__ == "__main__":
    main()

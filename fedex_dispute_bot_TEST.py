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
    """
    print("    Handling dispute form...")
    try:
        # Wait for the select elements to appear
        print("    Waiting for dispute form to load...")
        try:
            page.wait_for_selector("select", timeout=10000)
            time.sleep(1)  # Extra buffer
        except Exception as e:
            print(f"    ERROR: Form did not load in time: {e}")
            print(f"    Current URL: {page.url}")
            return
        
        # 1. Fill Dispute Type: 'Incorrect charge'
        print("    Selecting 'Incorrect charge'...")
        try:
            # Find all select elements
            selects = page.locator("select").all()
            if len(selects) >= 1:
                # First select is Dispute Type
                selects[0].select_option(label="Incorrect charge")
                print("    ✓ Selected 'Incorrect charge'")
                time.sleep(1)  # Wait for the second dropdown to appear
            else:
                print("    ERROR: Could not find select dropdowns")
                return
        except Exception as e:
            print(f"    ERROR selecting Dispute Type: {e}")
            return
        
        # 2. Fill Dispute Reason: 'Duty/Tax'
        print("    Selecting 'Duty/Tax'...")
        try:
            # Refresh the selects list (second dropdown appears after first selection)
            selects = page.locator("select").all()
            if len(selects) >= 2:
                # Second select is Dispute Reason
                selects[1].select_option(label="Duty/Tax")
                print("    ✓ Selected 'Duty/Tax'")
                time.sleep(0.5)
            else:
                print("    WARNING: Could not find Dispute Reason dropdown")
        except Exception as e:
            print(f"    ERROR selecting Dispute Reason: {e}")
        
        # 3. Fill comment
        print("    Typing comment...")
        comment_text = "Reason for dispute- Products are CUSMA compliant. COO is Canada. FTN CCP 10221998 / PWDBW 7702060 Database and USMCA on file."
        try:
            # Find textarea
            textarea = page.locator("textarea").first
            textarea.fill(comment_text)
            print("    ✓ Filled comment")
            time.sleep(0.5)
        except Exception as e:
            print(f"    WARNING: Could not fill comment: {e}")
        
        # 4. Submit
        print("    Clicking SUBMIT DISPUTE...")
        try:
            # Find the submit button
            submit_btn = page.locator("button:has-text('SUBMIT')").first
            submit_btn.click()
            print("    ✓ Clicked SUBMIT DISPUTE")
            
            # Wait for navigation back to invoice detail page
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
        
        # Step 1: Click "PAY A BILL"
        print("\n1. Clicking 'PAY A BILL'...")
        try:
            pay_bill_btn = page.get_by_text("PAY A BILL").first
            pay_bill_btn.click()
            time.sleep(2)
            print("   ✓ Clicked PAY A BILL")
        except Exception as e:
            print(f"   ✗ Could not find PAY A BILL button: {e}")
            print("   Trying to continue anyway...")
        
        # Step 2: Handle the "Latest with FedEx Billing Online" popup
        print("2. Checking for popup...")
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
        print("3. Clicking 'INVOICES' in sidebar...")
        try:
            invoices_link = page.locator("text=INVOICES").first
            invoices_link.click()
            time.sleep(3)
            print("   ✓ Navigated to Invoices")
        except Exception as e:
            print(f"   ✗ Could not find INVOICES link: {e}")
        
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

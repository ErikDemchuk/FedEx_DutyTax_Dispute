import time
from playwright.sync_api import sync_playwright, Page

# Configuration
USER_DATA_DIR = "./user_data_v6"
FEDEX_URL = "https://www.fedex.com/en-us/billing-online.html"
HEADLESS = False

def handle_dispute_form(page: Page):
    """
    Handles the dispute popup form.
    Selects 'Incorrect charge' -> 'Duty/Tax', types comment, and submits.
    """
    print("    Handling dispute form...")
    try:
        # Wait for the modal/popup to appear
        page.wait_for_selector("div[role='dialog']", timeout=5000)
        
        # 1. Select 'Dispute Type': 'Incorrect charge'
        print("    Selecting 'Incorrect charge'...")
        page.get_by_text("Dispute Type", exact=True).click()
        page.get_by_role("option", name="Incorrect charge").click()
        
        # 2. Select 'Dispute Reason': 'Duty/Tax'
        print("    Selecting 'Duty/Tax'...")
        page.get_by_text("Dispute Reason", exact=True).click()
        page.get_by_role("option", name="Duty/Tax").click()
        
        # 3. Type comment
        print("    Typing comment...")
        try:
            page.get_by_role("textbox").fill("Dispute per logic")
        except:
            page.locator("textarea").fill("Dispute per logic")
        
        # 4. Submit
        print("    Submitting...")
        page.get_by_role("button", name="Submit").click()
        
        # Wait for success message or modal close
        time.sleep(2) 
        print("    Dispute submitted successfully.")
        
    except Exception as e:
        print(f"    Error in dispute form: {e}")
        page.keyboard.press("Escape")

def process_shipments(page: Page):
    """
    Loops through shipments in the current invoice and disputes them.
    Skips shipments that are already listed in the Dispute Activity section.
    """
    print("  Processing shipments...")
    
    # Step 1: Check if there's a "Dispute Activity" section and extract disputed tracking numbers
    already_disputed = set()
    try:
        print("  Checking for already-disputed tracking numbers...")
        # Try to find and expand the Dispute Activity section
        dispute_activity = page.locator("text=Dispute Activity").first
        if dispute_activity.is_visible(timeout=2000):
            print("    Found Dispute Activity section")
            # Click to expand if it's collapsed
            try:
                dispute_activity.click()
                time.sleep(1)
            except:
                pass  # Already expanded
            
            # Extract all Air Waybill Numbers from the dispute activity table
            dispute_rows = page.locator("text=Duty/Tax").all()
            for row in dispute_rows:
                # Get parent row to access all columns
                try:
                    parent = row.locator("xpath=ancestor::tr").first
                    row_text = parent.text_content() or ""
                    # Extract tracking number (usually 12-14 digits)
                    import re
                    tracking_numbers = re.findall(r'\d{12,14}', row_text)
                    already_disputed.update(tracking_numbers)
                except:
                    pass
            
            if already_disputed:
                print(f"    Found {len(already_disputed)} already-disputed tracking numbers")
            else:
                print("    No disputed tracking numbers found in activity section")
    except:
        print("    No Dispute Activity section found (this is normal for new invoices)")
    
    # Step 2: Process shipments
    try:
        # Wait for shipment table to appear
        print("  Waiting for shipment table...")
        page.wait_for_selector("tbody tr", timeout=10000)
        time.sleep(2)  # Extra delay for rendering
        
        rows = page.locator("tbody tr").all()
        print(f"  Found {len(rows)} potential shipment rows.")
        
        disputed_count = 0
        skipped_count = 0
        
        for i, row in enumerate(rows):
            # Skip if it's a header or empty
            if row.locator("th").count() > 0:
                continue
            
            row_text = row.text_content() or ""
            
            # Check if this tracking number is already disputed
            import re
            tracking_numbers_in_row = re.findall(r'\d{12,14}', row_text)
            if any(tn in already_disputed for tn in tracking_numbers_in_row):
                print(f"  Row {i+1}: Already disputed (found in Dispute Activity) - SKIPPING")
                skipped_count += 1
                continue
            
            # Also check for dispute status text (backup method)
            if "PAST DUE IN DISPUTE" in row_text or "IN DISPUTE" in row_text:
                print(f"  Row {i+1}: Already disputed (status text) - SKIPPING")
                skipped_count += 1
                continue
                
            print(f"  Processing row {i+1}...")
            try:
                row.hover()
                
                btns = row.get_by_role("button").all()
                if not btns:
                    print(f"    No action buttons found - skipping")
                    continue
                
                # Assume the menu button is the last one
                menu_btn = btns[-1]
                menu_btn.click()
                time.sleep(0.5)  # Wait for menu to appear
                
                # Click 'Dispute' in the menu that appears
                page.get_by_text("Dispute", exact=True).click()
                
                # Handle the form
                handle_dispute_form(page)
                disputed_count += 1
                
            except Exception as e:
                print(f"    Error processing shipment row {i+1}: {e}")
                continue
        
        print(f"  Summary: {disputed_count} disputed, {skipped_count} skipped (already disputed)")
                
    except Exception as e:
        print(f"  Error reading shipments table: {e}")

def process_invoices(page: Page):
    """
    Scrapes the invoice list and processes 'Duty/Tax' invoices.
    """
    print("Scanning Invoice List...")
    
    # Wait for invoice table to appear (specific element, not networkidle)
    print("Waiting for invoice table to appear...")
    try:
        page.wait_for_selector("table tbody", timeout=30000)
        print("Table found! Waiting for it to populate...")
        time.sleep(3)  # Give time for rows to load
    except Exception as e:
        print(f"Error waiting for table: {e}")
        print("Trying to proceed anyway...")
    
    # Find all rows containing "Duty/Tax"
    print("Looking for Duty/Tax invoices...")
    rows = page.get_by_role("row").filter(has_text="Duty/Tax").all()
    count = len(rows)
    print(f"Found {count} invoices with 'Duty/Tax'.")
    
    if count == 0:
        print("No Duty/Tax invoices found. Make sure you're on the invoice list page.")
        print(f"Current URL: {page.url}")
        return
    
    # Iterate by index to handle navigation/DOM updates
    for i in range(count):
        print(f"\n{'='*60}")
        print(f"Processing invoice {i+1} of {count}...")
        print(f"{'='*60}")
        
        # Re-query to get fresh handles
        rows = page.get_by_role("row").filter(has_text="Duty/Tax").all()
        if i >= len(rows):
            print("  Row index out of range (list changed?). Stopping.")
            break
            
        row = rows[i]
        
        try:
            # Click the Invoice Number link
            link = row.get_by_role("link").first
            invoice_number = link.text_content() or "Unknown"
            print(f"  Opening invoice: {invoice_number}")
            link.click()
            
            # Wait for the invoice detail page to load
            time.sleep(3)
            
            # Process the shipments in this invoice
            process_shipments(page)
            
            # Go back to the list
            print("  Returning to Invoice List...")
            page.go_back()
            
            # Wait for the invoice table to reappear
            page.wait_for_selector("table tbody", timeout=30000)
            time.sleep(2)
            
        except Exception as e:
            print(f"  Error processing invoice {i+1}: {e}")
            print("  Attempting to recover...")
            if "billing" not in page.url:
                print("  Going back to invoice list...")
                page.go_back()
                time.sleep(2)

def main():
    print("Starting FedEx Dispute Bot...")
    print("="*60)
    
    with sync_playwright() as p:
        print(f"Launching browser with user data dir: {USER_DATA_DIR}")
        
        # Launch with minimal flags to avoid detection
        context = p.chromium.launch_persistent_context(
            user_data_dir=USER_DATA_DIR,
            headless=HEADLESS,
            channel="chrome",
            args=["--disable-blink-features=AutomationControlled"],
        )
        
        page = context.pages[0]
        
        print(f"Navigating to {FEDEX_URL}...")
        page.goto(FEDEX_URL)
        
        # Login Check
        print("\n" + "="*60)
        print("LOGIN CHECK:")
        print("1. If you see the Login page, log in manually now.")
        print("2. Navigate to the 'Invoice List' page.")
        print("   URL should be: fedex.com/online/billing/cbs/invoices")
        print("   You should see a table with Invoice Number, Invoice Type, etc.")
        print("3. Press ENTER in this terminal when ready.")
        print("="*60 + "\n")
        input("Press Enter to continue...")
        
        print(f"\nCurrent URL: {page.url}")
        
        # Start Automation
        try:
            process_invoices(page)
            print("\n" + "="*60)
            print("SUCCESS! All Duty/Tax invoices have been processed.")
            print("="*60)
        except Exception as e:
            print("\n" + "="*60)
            print(f"ERROR: An error occurred during execution:")
            print(f"{e}")
            print("="*60)
            import traceback
            traceback.print_exc()
        
        print("\nScript finished.")
        input("Press any key to close...")

if __name__ == "__main__":
    main()

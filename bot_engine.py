import time
import re
import threading
import os
import asyncio
import sys
from datetime import datetime
from typing import Callable, Optional, List, Dict
from playwright.sync_api import sync_playwright, Page, BrowserContext

# Fix for Windows asyncio + threading issue
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

class BotState:
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    COMPLETED = "completed"
    ERROR = "error"
    WAITING_FOR_LOGIN = "waiting_for_login"
    ANALYZING = "analyzing"
    READY_TO_PROCESS = "ready_to_process"

class FedExDisputeBot:
    def __init__(self, config: dict):
        self.config = config
        self.state = BotState.IDLE
        self.playwright = None
        self.browser_context = None
        self.page = None
        self.thread = None
        self.stop_event = threading.Event()
        self.pause_event = threading.Event()
        self.pause_event.set()
        
        # Create logs directory
        if not os.path.exists("logs"):
            os.makedirs("logs")
        self.log_file = f"logs/session_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.log"
        
        # Log history for UI sync
        self.log_history = []
        
        # Statistics
        self.stats = {
            "disputed": 0,
            "skipped": 0,
            "errors": 0,
            "invoices_processed": 0,
            "total_invoices": 0,
            "current_invoice": ""
        }
        
        self.found_invoices = [] # List of invoices found during analysis
        
        # Callbacks (optional, may not work with Streamlit threads)
        self.log_callback: Optional[Callable[[str, str], None]] = None
        self.stats_callback: Optional[Callable[[dict], None]] = None
        self.progress_callback: Optional[Callable[[int, int], None]] = None
        self.invoices_callback: Optional[Callable[[list], None]] = None
        self.screenshot_path = "latest_view.png"

    def set_callbacks(self, log_cb=None, stats_cb=None, progress_cb=None, invoices_cb=None):
        self.log_callback = log_cb
        self.stats_callback = stats_cb
        self.progress_callback = progress_cb
        self.invoices_callback = invoices_cb

    def capture_screenshot(self):
        """Captures a screenshot of the current page state"""
        if self.page and not self.page.is_closed():
            try:
                self.page.screenshot(path=self.screenshot_path)
            except Exception as e:
                print(f"Screenshot failed: {e}")

    def log(self, message: str, level: str = "INFO"):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        formatted_msg = f"[{timestamp}] [{level}] {message}"
        
        # Store in log history for UI sync
        self.log_history.append(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")
        # Keep only last 100 entries
        if len(self.log_history) > 100:
            self.log_history = self.log_history[-100:]
        
        # Capture screenshot on important events (Success/Error/Warning) or periodically
        if level in ["SUCCESS", "ERROR", "WARNING"] or "Processing" in message:
            self.capture_screenshot()
        
        # Write to file
        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(formatted_msg + "\n")
        except: pass
        
        # Callback to UI (may not work with Streamlit threads)
        if self.log_callback:
            try:
                self.log_callback(message, level)
            except: pass
        print(formatted_msg)

    def update_stats(self, key: str, value=None, increment=False):
        if increment:
            self.stats[key] = self.stats.get(key, 0) + 1
        else:
            self.stats[key] = value
            
        if self.stats_callback:
            self.stats_callback(self.stats)

    def start_browser(self):
        """Phase 1: Launch browser and wait for login"""
        if self.state == BotState.RUNNING or self.state == BotState.WAITING_FOR_LOGIN:
            return
        
        self.stop_event.clear()
        self.pause_event.set()
        self.state = BotState.WAITING_FOR_LOGIN
        
        self.thread = threading.Thread(target=self._launch_and_wait)
        self.thread.daemon = True
        self.thread.start()

    def start_analysis(self):
        """Phase 2: Navigate to invoices and analyze list"""
        if self.state != BotState.WAITING_FOR_LOGIN:
            return
        
        # Just change state - the main loop running in _launch_and_wait will pick this up
        self.state = BotState.ANALYZING

    def start_processing(self):
        """Phase 3: Process the found invoices"""
        if self.state != BotState.READY_TO_PROCESS:
            return
        
        # Just change state - the main loop will pick this up
        self.state = BotState.RUNNING

    def _launch_and_wait(self):
        try:
            self.log("Starting FedEx Dispute Bot...", "INFO")
            
            with sync_playwright() as p:
                # Launch browser
                self.log(f"Launching browser...", "INFO")
                
                self.browser_context = p.chromium.launch_persistent_context(
                    user_data_dir=self.config.get('user_data_dir'),
                    headless=self.config.get('headless', False),
                    channel="chrome",
                    args=["--disable-blink-features=AutomationControlled"],
                    viewport={"width": 1280, "height": 720} # Explicit viewport
                )
                
                self.page = self.browser_context.pages[0]
                self.log("Browser context created.", "INFO")
                
                # TAKE INITIAL SCREENSHOT IMMEDIATELY
                self.capture_screenshot()
                
                # Navigation
                fedex_url = self.config.get('fedex_url', "https://www.fedex.com/en-ca/logged-in-home.html")
                self.log(f"Navigating to {fedex_url}...", "INFO")
                
                # Use domcontentloaded to return faster, don't wait for full network idle
                try:
                    self.page.goto(fedex_url, timeout=60000, wait_until="domcontentloaded")
                except Exception as nav_err:
                    self.log(f"Navigation warning: {nav_err}", "WARNING")
                
                self.capture_screenshot()
                
                self.log("Browser launched. Please log in manually if needed.", "WARNING")
                self.log("Waiting for user to click 'Analyze Invoices'...", "INFO")
                
                # Keep browser open and update screenshots while waiting
                while self.state == BotState.WAITING_FOR_LOGIN and not self.stop_event.is_set():
                    self.capture_screenshot()
                    time.sleep(1)
                    
                # If state changed to ANALYZING, we keep the browser open but exit this thread loop
                # The actual Playwright context needs to be kept alive.
                # We can't close the context here if we want to continue.
                # Ideally, we run one persistent thread that handles messages/states.
                
                # REFACTOR: We need a single main loop that handles state transitions
                # to keep the playwright context alive in one thread.
                self._main_loop()
                
        except Exception as e:
            self.log(f"Bot crashed: {e}", "ERROR")
            self.state = BotState.ERROR
            import traceback
            traceback.print_exc()
        finally:
            if self.browser_context:
                try:
                    self.browser_context.close()
                except: pass
            self.thread = None

    def _main_loop(self):
        """Main loop that runs inside the Playwright context"""
        while not self.stop_event.is_set():
            if self.state == BotState.ANALYZING:
                self._navigate_to_invoices()
                self._scan_invoices()
                self.state = BotState.READY_TO_PROCESS
                self.log("Analysis complete. Ready to process.", "SUCCESS")
                
            elif self.state == BotState.RUNNING: # Processing phase
                self._process_invoices_loop()
                self.state = BotState.COMPLETED
                self.log("All tasks completed.", "SUCCESS")
                break # Exit loop when done
                
            elif self.state == BotState.WAITING_FOR_LOGIN:
                self.capture_screenshot()
                time.sleep(1)
                
            elif self.state == BotState.PAUSED:
                self.capture_screenshot()
                time.sleep(1)
            
            elif self.state == BotState.READY_TO_PROCESS:
                self.capture_screenshot()
                time.sleep(1)
                
            else:
                time.sleep(0.5)

    def _check_control_signals(self):
        """Check for pause/stop signals"""
        if self.stop_event.is_set():
            raise Exception("Bot stopped by user")
        
        while not self.pause_event.is_set():
            self.capture_screenshot()
            time.sleep(0.5)
            if self.stop_event.is_set():
                raise Exception("Bot stopped by user")

    def _navigate_to_invoices(self):
        """Navigate from logged-in page to invoices list"""
        page = self.page
        self.log("Navigating to invoices...", "INFO")
        self.capture_screenshot()
        
        try:
            # Try clicking "PAY A BILL" or similar
            pay_bill = page.locator("text=PAY A BILL").first
            if pay_bill.is_visible(timeout=3000):
                pay_bill.click()
                time.sleep(2)
                self.capture_screenshot()
        except:
            pass
        
        try:
            # Try clicking "FedEx Billing Online"
            billing_link = page.locator("text=FedEx Billing Online").first
            if billing_link.is_visible(timeout=3000):
                billing_link.click()
                time.sleep(3)
                self.capture_screenshot()
        except:
            pass
        
        try:
            # Handle any popups
            close_btn = page.locator("button:has-text('Close'), button:has-text('CLOSE')").first
            if close_btn.is_visible(timeout=1000):
                close_btn.click()
                time.sleep(1)
        except:
            pass
        
        try:
            # Click INVOICES
            invoices_link = page.locator("text=INVOICES").first
            if invoices_link.is_visible(timeout=5000):
                invoices_link.click()
                time.sleep(3)
                self.capture_screenshot()
        except:
            pass
        
        # If we're still not on invoices page, try direct URL
        if "invoices" not in page.url.lower():
            self.log("Trying direct navigation to invoices...", "INFO")
            page.goto("https://www.fedex.com/online/billing/cbs/invoices", wait_until="domcontentloaded")
            time.sleep(3)
            self.capture_screenshot()
        
        self.log("Navigation complete.", "INFO")

    def pause(self):
        """Pause the bot"""
        self.pause_event.clear()
        self.state = BotState.PAUSED
        self.log("Bot paused.", "WARNING")

    def resume(self):
        """Resume the bot"""
        self.pause_event.set()
        self.state = BotState.RUNNING
        self.log("Bot resumed.", "INFO")

    def stop(self):
        """Stop the bot"""
        self.stop_event.set()
        self.pause_event.set()  # Unblock if paused
        self.state = BotState.STOPPED
        self.log("Bot stopped.", "WARNING")

    def _scan_invoices(self):
        self._check_control_signals()
        page = self.page
        
        self.log("Scanning invoice list...", "INFO")
        self.capture_screenshot()
        
        try:
            page.wait_for_selector("table tbody", timeout=30000)
            time.sleep(2)
        except Exception as e:
            self.log(f"Error waiting for table: {e}", "ERROR")
            return

        # Scan rows
        all_rows = page.locator("tbody tr").all()
        self.found_invoices = []
        
        for row in all_rows:
            row_text = row.text_content() or ""
            invoice_match = re.search(r'\d-\d{3}-\d{5}', row_text)
            invoice_num = invoice_match.group() if invoice_match else "Unknown"
            
            status = "Unknown"
            if "Transportation" in row_text: status = "Transportation"
            elif "OPEN IN DISPUTE" in row_text: status = "Disputed"
            elif "Duty/Tax" in row_text: status = "Duty/Tax"
            
            self.found_invoices.append({
                "invoice": invoice_num,
                "type": status,
                "text": row_text
            })
            
        if self.invoices_callback:
            self.invoices_callback(self.found_invoices)
            
        duty_tax_count = sum(1 for inv in self.found_invoices if inv["type"] == "Duty/Tax")
        self.log(f"Analysis: Found {len(self.found_invoices)} total invoices, {duty_tax_count} to process.", "INFO")
        self.capture_screenshot()

    def _process_invoices_loop(self):
        # Filter for duty/tax only
        to_process = [inv["invoice"] for inv in self.found_invoices if inv["type"] == "Duty/Tax"]
        
        total = len(to_process)
        self.update_stats("total_invoices", total)
        
        for i, invoice_num in enumerate(to_process):
            self._check_control_signals()
            
            self.update_stats("invoices_processed", i + 1)
            self.update_stats("current_invoice", invoice_num)
            
            if self.progress_callback:
                self.progress_callback(i + 1, total)
                
            self.log(f"Processing Invoice {i+1}/{total}: {invoice_num}", "INFO")
            
            try:
                self._process_single_invoice(invoice_num)
            except Exception as e:
                self.log(f"Error processing invoice {invoice_num}: {e}", "ERROR")
                self.update_stats("errors", increment=True)
                try:
                    self.page.goto("https://www.fedex.com/online/billing/cbs/invoices")
                    time.sleep(3)
                except: pass

    def _process_single_invoice(self, invoice_number):
        page = self.page
        
        # Navigate directly
        invoice_no_clean = invoice_number.replace("-", "")
        account_no = self.config.get("account_number", "202744967") # Should be config
        invoice_url = f"https://www.fedex.com/online/billing/cbs/invoices/invoice-details?accountNo={account_no}&countryCode=CA&invoiceNumber={invoice_no_clean}"
        
        page.goto(invoice_url)
        time.sleep(3)
        
        if "invoice-details" not in page.url:
            self.log(f"Failed to load invoice {invoice_number}", "ERROR")
            return

        # Process shipments logic (copied from original bot with improvements)
        self._process_shipments_in_page()
        
        self.log(f"Finished invoice {invoice_number}", "SUCCESS")
        page.go_back()
        time.sleep(2)

    def _process_shipments_in_page(self):
        page = self.page
        
        # 1. Check Dispute Activity
        already_disputed_duty_tax = set()
        try:
            dispute_section = page.locator("text=Dispute Activity").first
            if dispute_section.is_visible(timeout=3000):
                dispute_section.click()
                time.sleep(1)
                
                duty_tax_rows = page.locator("tr:has-text('Duty/Tax')").all()
                for row in duty_tax_rows:
                    row_text = row.text_content() or ""
                    tracking_nums = re.findall(r'\b\d{12}\b', row_text)
                    already_disputed_duty_tax.update(tracking_nums)
        except: pass
        
        # 2. Process rows
        try:
            page.wait_for_selector("tbody tr", timeout=10000)
            time.sleep(2)
            rows = page.locator("tbody tr").all()
            
            for row in rows:
                self._check_control_signals()
                
                row_text = row.text_content() or ""
                tracking_nums = re.findall(r'\b\d{12}\b', row_text)
                
                if not tracking_nums: continue
                tracking_num = tracking_nums[0]
                
                if tracking_num in already_disputed_duty_tax:
                    self.log(f"Skipping {tracking_num} (already disputed for Duty/Tax)", "INFO")
                    self.update_stats("skipped", increment=True)
                    continue
                    
                # Process dispute
                self.log(f"Disputing tracking {tracking_num}...", "INFO")
                try:
                    # Click menu
                    btns = row.locator("button").all()
                    if not btns: continue
                    
                    btns[0].evaluate("element => element.click()")
                    time.sleep(0.5)
                    
                    page.get_by_text("Dispute", exact=True).click()
                    time.sleep(1)
                    
                    if self._handle_dispute_form():
                        self.log(f"Successfully disputed {tracking_num}", "SUCCESS")
                        self.update_stats("disputed", increment=True)
                    else:
                        self.log(f"Failed to dispute {tracking_num}", "ERROR")
                        self.update_stats("errors", increment=True)
                        
                    self._handle_error_popup()
                    
                    # Check if stuck
                    if "create-dispute" in page.url:
                        page.go_back()
                        time.sleep(2)
                        
                except Exception as e:
                    self.log(f"Error disputing {tracking_num}: {e}", "ERROR")
                    self.update_stats("errors", increment=True)
                    continue
                    
        except Exception as e:
            self.log(f"Error processing shipments table: {e}", "ERROR")

    def _handle_dispute_form(self):
        page = self.page
        try:
            # Similar to original handle_dispute_form
            page.wait_for_selector("div[role='dialog'], text=Dispute type", timeout=5000)
            
            # 1. Dispute Type
            try:
                page.click("text=Select >> nth=0")
                time.sleep(0.5)
                page.click("text=Incorrect charge")
                time.sleep(1)
            except: return False
            
            # 2. Dispute Reason
            try:
                page.click("text=Select >> nth=0")
                time.sleep(0.5)
                page.click("text=Duty/Tax")
                time.sleep(1)
            except: return False
            
            # 3. Comment
            comment = self.config.get("dispute_comment", "Dispute per logic")
            try:
                page.locator("textarea").first.fill(comment)
            except:
                page.locator("input[type='text']").last.fill(comment)
                
            # 4. Submit
            page.locator("button:has-text('SUBMIT'), button:has-text('Submit')").first.click()
            time.sleep(3)
            
            return True
        except:
            return False

    def _handle_error_popup(self):
        page = self.page
        try:
            if page.locator("text=ERROR CODE").is_visible(timeout=500):
                self.log("Handling error popup...", "WARNING")
                page.locator("button:has-text('CLOSE')").click()
                time.sleep(1)
        except: pass


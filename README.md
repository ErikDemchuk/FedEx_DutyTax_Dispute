# FedEx Dispute Automation Bot

This bot automates the process of disputing 'Duty/Tax' invoices on FedEx Billing Online using Playwright.

## Prerequisites

1.  **Python 3.8+** installed.
2.  **Playwright** installed.

## Installation

1.  Install dependencies:
    ```bash
    pip install playwright
    playwright install chromium
    ```

## Usage

1.  **Run the script:**
    ```bash
    python fedex_dispute_bot.py
    ```

2.  **First Run (Login):**
    - A browser window will open.
    - **Log in** to your FedEx account manually.
    - Navigate to the **Invoice List** page.
    - Switch back to the terminal window and press **ENTER**.
    - The bot will save your session and start processing.

3.  **Subsequent Runs:**
    - The bot will launch the browser with your saved session.
    - It should be logged in automatically.
    - It will start processing immediately (after you press Enter to confirm).

## Features

- **Persistent Login**: Saves your session so you don't have to log in every time.
- **Smart Navigation**: Finds 'Duty/Tax' invoices automatically.
- **Robust Handling**: Retries if elements are stale and logs errors without crashing.
- **Safe Mode**: Runs with `slow_mo` enabled so you can watch what it does.

## Troubleshooting

- **Bot can't find the '3-dots' menu**:
    - The script looks for a button in the shipment row. If the site design changes, you may need to update the selector in `process_shipments`.
- **Bot gets stuck**:
    - Press `Ctrl+C` in the terminal to stop it.
    - Check the terminal output for error messages.

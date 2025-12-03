# FedEx Duty/Tax Dispute Bot

Automated bot to dispute Duty/Tax charges on FedEx invoices.

## Features

- ✅ Automatically processes all Duty/Tax invoices
- ✅ Skips already disputed tracking IDs (prevents duplicates)
- ✅ Skips Transportation invoices
- ✅ Handles FedEx error popups
- ✅ Web UI dashboard with live progress
- ✅ Detailed logging

## Requirements

- Python 3.10 or higher
- Google Chrome browser installed
- Windows 10/11 (tested)

## Installation

### 1. Clone the repository
```bash
git clone https://github.com/YOUR_USERNAME/FedEx_DutyTax_Dispute.git
cd FedEx_DutyTax_Dispute
```

### 2. Install Python dependencies
```bash
pip install -r requirements.txt
```

### 3. Install Playwright browser
```bash
python -m playwright install chromium
```

## Configuration

Edit `bot_config.json` to set your account details:

```json
{
    "user_data_dir": "./user_data_v6",
    "account_number": "YOUR_FEDEX_ACCOUNT_NUMBER",
    "dispute_comment": "Your dispute reason here",
    "fedex_url": "https://www.fedex.com/en-ca/logged-in-home.html"
}
```

## Usage

### Option 1: Run the Bot Directly
```bash
python browser_worker.py
```

1. A Chrome browser will open
2. Log in to your FedEx account
3. Go back to the terminal and follow the prompts

### Option 2: Run with Web UI
```bash
python -m streamlit run app.py
```

Or use the batch file:
```bash
run_ui.bat
```

1. Open http://localhost:8501 in your browser
2. Click "Launch Browser"
3. Log in to FedEx in the Chrome window
4. Click "Start Processing" in the UI

### Option 3: Test Duplicate Detection
```bash
python test_duplicate_check.py
```

This tests the duplicate detection without submitting any disputes.

## How It Works

1. **Scans Invoice List** - Finds all Duty/Tax invoices
2. **For Each Invoice**:
   - Opens the invoice details page
   - Reads the "Dispute Activity" section to find already-disputed tracking IDs
   - Compares with the shipments table
   - Only disputes tracking IDs NOT already disputed for Duty/Tax
3. **Submits Disputes** - Fills out the dispute form automatically

## Files

| File | Description |
|------|-------------|
| `browser_worker.py` | Main bot logic (runs in separate process) |
| `app.py` | Streamlit web UI |
| `config.py` | Configuration management |
| `bot_config.json` | Your settings (account number, etc.) |
| `test_duplicate_check.py` | Test script for duplicate detection |
| `run_ui.bat` | Windows batch file to start the UI |

## Troubleshooting

### "Playwright not found"
```bash
pip install playwright
python -m playwright install chromium
```

### "Chrome not opening"
Make sure Google Chrome is installed on your system.

### "Session expired"
Delete the `user_data_v6` folder and log in again.

## Notes

- The bot saves your browser session in `user_data_v6/` folder
- First run requires manual login; subsequent runs may auto-login
- Logs are saved in the `logs/` folder

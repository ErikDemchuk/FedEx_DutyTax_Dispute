@echo off
echo ============================================================
echo FedEx Dispute Bot - FULL MODE
echo Processing ALL Duty/Tax invoices
echo ============================================================
echo.
echo Installing dependencies...
python -m pip install -r requirements.txt
echo.
echo Installing Playwright browsers (if needed)...
python -m playwright install chromium
echo.
echo Starting Bot...
python fedex_dispute_bot.py
pause

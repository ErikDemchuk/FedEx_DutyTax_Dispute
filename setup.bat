@echo off
echo ============================================================
echo FedEx Dispute Bot - Setup
echo ============================================================
echo.

echo Step 1: Installing Python packages...
pip install -r requirements.txt
echo.

echo Step 2: Installing Playwright browser (Chromium)...
python -m playwright install chromium
echo.

echo ============================================================
echo Setup Complete!
echo ============================================================
echo.
echo To run the bot:
echo   python browser_worker.py
echo.
echo To run with Web UI:
echo   python -m streamlit run app.py
echo.
pause


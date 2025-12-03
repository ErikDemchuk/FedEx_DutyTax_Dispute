@echo off
echo ============================================================
echo FedEx Dispute Bot - TEST MODE
echo Only processing invoice: 2-700-01643
echo ============================================================
echo.
echo Installing dependencies...
"C:\Users\Admin\AppData\Local\Programs\Python\Python311\python.exe" -m pip install -r requirements.txt
echo.
echo Starting Test Bot...
"C:\Users\Admin\AppData\Local\Programs\Python\Python311\python.exe" fedex_dispute_bot_TEST.py
pause

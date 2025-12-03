@echo off
echo ============================================================
echo FedEx Dispute Bot - Web UI
echo ============================================================
echo.
echo Installing requirements...
python -m pip install -r requirements.txt
echo.
echo Starting Web Dashboard...
echo Opening browser at http://localhost:8501
echo.
python -m streamlit run app.py
pause


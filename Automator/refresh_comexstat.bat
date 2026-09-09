@echo off
setlocal
cd /d "%~dp0"

echo ============================================
echo  Comexstat coffee export refresh
echo ============================================
echo.

python ingest_comexstat.py %*
if errorlevel 1 (
    echo.
    echo  REFRESH FAILED - see error above.
    echo  The existing parquet was left untouched.
    pause
    exit /b 1
)

echo.
echo  Done. Review the numbers, then commit and push
echo  Database\Comexstat\ to send it to Streamlit Cloud.
pause

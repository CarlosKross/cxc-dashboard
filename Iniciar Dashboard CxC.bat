@echo off
cd /d "%~dp0"
echo Iniciando Dashboard CxC...

REM Intentar con python, luego con python3
python --version >nul 2>&1
if errorlevel 1 (
    python3 --version >nul 2>&1
    if errorlevel 1 (
        echo [ERROR] Python no encontrado. Ejecuta primero "Instalar Dashboard CxC.bat"
        pause
        exit /b 1
    )
    python3 -m streamlit run cxc_app.py --server.port 8501 --server.headless true
) else (
    python -m streamlit run cxc_app.py --server.port 8501 --server.headless true
)
pause

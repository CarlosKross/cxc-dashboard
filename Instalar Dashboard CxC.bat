@echo off
cd /d "%~dp0"
echo ============================================
echo   Instalador - Dashboard CxC Kross
echo ============================================
echo.

REM Verificar Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python no esta instalado.
    echo.
    echo Descargalo desde: https://www.python.org/downloads/
    echo IMPORTANTE: Al instalar, marcar la opcion "Add Python to PATH"
    echo.
    pause
    exit /b 1
)

echo [OK] Python encontrado.
echo.
echo Instalando dependencias...
echo.
python -m pip install --upgrade pip
python -m pip install streamlit pandas openpyxl xlrd

echo.
echo ============================================
echo   Instalacion completada con exito!
echo ============================================
echo.
echo Ahora puedes usar: "Iniciar Dashboard CxC.bat"
echo.
pause

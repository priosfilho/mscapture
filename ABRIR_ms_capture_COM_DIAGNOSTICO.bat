@echo off
setlocal
cd /d "%~dp0"

echo Iniciando ms_capture com diagnostico...
echo Pasta: %CD%
echo.

where py >nul 2>nul
if %errorlevel%==0 (
    py -3 "%~dp0ms_capture_v4.py" --gui
    goto end
)

where python >nul 2>nul
if %errorlevel%==0 (
    python "%~dp0ms_capture_v4.py" --gui
    goto end
)

echo Nao encontrei Python pelo comando py nem pelo comando python.
echo Instale o Python 3 para Windows e marque a opcao "Add python.exe to PATH".
echo.

:end
echo.
echo Se apareceu algum erro acima, copie a mensagem e envie para diagnostico.
pause

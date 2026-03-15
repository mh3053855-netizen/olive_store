@echo off
set PYTHON=%LOCALAPPDATA%\Programs\Python\Python313\python.exe
set PROJECT=D:\app\app\olive_store

cd /d "%PROJECT%"

"%PYTHON%" -m pip install flask werkzeug --quiet

if not exist "static" mkdir "static"
if not exist "static\uploads" mkdir "static\uploads"

echo.
echo  Site:   http://localhost:5000
echo  Admin:  http://localhost:5000/admin
echo  User:   admin
echo  Pass:   sulafa2024
echo.

start "" cmd /c "timeout /t 2 > nul && start http://localhost:5000"

"%PYTHON%" app.py
pause

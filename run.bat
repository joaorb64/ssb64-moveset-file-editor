@echo off
cd /d "%~dp0"

echo Checking for pipenv...
python -m pip install --user --upgrade pipenv --quiet

echo Installing/updating dependencies...
python -m pipenv install
if errorlevel 1 (
    echo Failed to install dependencies.
    pause
    exit /b 1
)

echo Launching SSB64 Moveset Editor...
python -m pipenv run python Main.py
if errorlevel 1 (
    pause
)

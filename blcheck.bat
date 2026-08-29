@echo off
REM Chay: blcheck run      (hoac blcheck.bat run)
REM
REM May nay co 2 ban Python. Ban trong PATH la Python310 - KHONG co typer/rich/
REM httpx nen chay se loi ModuleNotFoundError. Bo chi thang vao Python311.
REM Doi may / cai lai Python thi sua dong BLCHECK_PY duoi day.

setlocal
set "BLCHECK_PY=C:\Program Files\Python311\python.exe"

if not exist "%BLCHECK_PY%" (
    REM Khong thay ban da chi dinh -> quay ve 'python' trong PATH.
    set "BLCHECK_PY=python"
)

"%BLCHECK_PY%" "%~dp0src\cli.py" %*
endlocal

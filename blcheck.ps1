# Chay: .\blcheck.ps1 run
#
# May nay co 2 ban Python. Ban trong PATH la Python310 - KHONG co typer/rich/
# httpx nen chay se loi ModuleNotFoundError. Bo chi thang vao Python311.
# Doi may / cai lai Python thi sua dong $BlcheckPy duoi day.

$BlcheckPy = "C:\Program Files\Python311\python.exe"

if (-not (Test-Path $BlcheckPy)) {
    # Khong thay ban da chi dinh -> quay ve 'python' trong PATH.
    $BlcheckPy = "python"
}

& $BlcheckPy "$PSScriptRoot\src\cli.py" @args
exit $LASTEXITCODE

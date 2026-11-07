# Intercept script:
# 1. Run the EXE and click Flash -> wait for P key to flash on keyboard
# 2. Run THIS script (while P key is flashing, BEFORE pressing Fn+P)
# 3. This kills the EXE and starts the QMK flasher
# 4. THEN press Fn+P -> keyboard enters ISP -> QMK gets flashed

$rk71 = Get-Process | Where-Object { $_.ProcessName -match "RK71|Firmware" } | Select-Object -First 1
if ($rk71) {
    Write-Host "[*] Killing EXE: $($rk71.ProcessName) (PID $($rk71.Id))"
    Stop-Process -Id $rk71.Id -Force
    Write-Host "[*] EXE killed. Starting QMK flasher..."
} else {
    Write-Host "[!] RK71 EXE not found - starting flasher anyway"
}

Write-Host "[*] Press Fn+P NOW to trigger ISP..."
Set-Location C:\Users\<user>\Documents\rk71_mod
python flash_qmk.py --hex "qmk_firmware\.build\rk_rk71_noled.hex"

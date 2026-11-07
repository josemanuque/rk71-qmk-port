# ISP Interceptor v3
$WorkDir = "C:\Users\<user>\Documents\rk71_mod"
$Python  = (Get-Command python).Source
$FlashPy = Join-Path $WorkDir "flash_qmk.py"
$CheckISP = Join-Path $WorkDir "check_isp.py"
$ExeName = "RK71 RGB Firmware_V1.12_190603.exe"

function Kill-RKExe {
    taskkill /F /IM $ExeName 2>$null | Out-Null
    Get-Process | Where-Object { $_.MainWindowTitle -match "RK|firmware|update" } |
        ForEach-Object { Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue }
    Write-Host "[!] Kill sent" -ForegroundColor Red
}

function Flash-QMK {
    Write-Host "[*] Running flash_qmk.py..." -ForegroundColor Cyan
    $p = Start-Process $Python -ArgumentList ('"' + $FlashPy + '"') -WorkingDirectory $WorkDir -PassThru -NoNewWindow
    $p.WaitForExit(30000)
    if ($p.ExitCode -eq 0) { Write-Host "[SUCCESS] QMK flashed!" -ForegroundColor Green }
    else { Write-Host "[FAIL] flash_qmk.py exit $($p.ExitCode)" -ForegroundColor Red }
    return $p.ExitCode -eq 0
}

Write-Host "=== ISP Interceptor v3 ===" -ForegroundColor Cyan
Write-Host "Waiting for keyboard to disconnect (EXE trigger)..." -ForegroundColor Yellow

# Step 1: wait for VID_05AC to disappear
$deadline = [DateTime]::Now.AddSeconds(120)
while ([DateTime]::Now -lt $deadline) {
    $kb = Get-PnpDevice -InstanceId "*VID_05AC&PID_024F*" -ErrorAction SilentlyContinue |
          Where-Object { $_.Status -eq 'OK' }
    if (-not $kb) {
        Write-Host "`n[+] Keyboard disconnected! Killing EXE..." -ForegroundColor Green
        Kill-RKExe
        break
    }
    Start-Sleep -Milliseconds 100
}

Write-Host "Step 2: Polling for ISP (VID=0x0C45) every 50ms..." -ForegroundColor Yellow

# Step 2: tight poll for ISP (50ms via Get-PnpDevice + hid check)
$deadline2 = [DateTime]::Now.AddSeconds(20)
$flashed = $false
while ([DateTime]::Now -lt $deadline2 -and -not $flashed) {
    # Fast PnP check
    $isp = Get-PnpDevice -InstanceId "*VID_0C45*" -ErrorAction SilentlyContinue |
           Where-Object { $_.Status -eq 'OK' }
    if ($isp) {
        Write-Host "[+] ISP via PnP: $($isp.InstanceId)" -ForegroundColor Green
        Start-Sleep -Milliseconds 300
        $flashed = Flash-QMK
        break
    }
    # hidapi check
    & $Python $CheckISP 2>$null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "[+] ISP via hidapi!" -ForegroundColor Green
        $flashed = Flash-QMK
        break
    }
    Start-Sleep -Milliseconds 50
}

if (-not $flashed) {
    Write-Host "[FAIL] ISP not found in 20s." -ForegroundColor Red
    Write-Host "  Make sure EXE was open and you pressed Fn+P." -ForegroundColor Yellow
}

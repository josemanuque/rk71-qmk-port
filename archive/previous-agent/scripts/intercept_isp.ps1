# Watches for VID_0C45 (ISP mode) using WMI device insertion events.
# The moment it appears: kill the RK71 EXE, flash QMK.
$WorkDir = "C:\Users\<user>\Documents\rk71_mod"
$Python  = (Get-Command python).Source

Write-Host "=== RK71 ISP Interceptor ===" -ForegroundColor Cyan
Write-Host "Waiting for keyboard to enter ISP mode (VID=0x0C45)..." -ForegroundColor Yellow
Write-Host "Click Flash in the RK71 firmware EXE now." -ForegroundColor Green

$action = {
    $dev = $Event.SourceEventArgs.NewEvent.TargetInstance
    if ($dev.DeviceID -match "VID_0C45") {
        Write-Host "`n[+] ISP detected: $($dev.DeviceID)" -ForegroundColor Green

        # Kill EXE immediately before it can flash
        Get-Process | Where-Object { $_.MainWindowTitle -match "RK|firmware|update" -or $_.ProcessName -match "RK71|firmware" } |
            ForEach-Object { Write-Host "  Killing $($_.ProcessName) ($($_.Id))"; Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue }

        # Also kill by EXE filename
        Get-Process | Where-Object { try { $_.MainModule.FileName -match "RK71" } catch { $false } } |
            ForEach-Object { Write-Host "  Killing $($_.ProcessName) ($($_.Id))"; Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue }

        Start-Sleep -Milliseconds 200

        Write-Host "[*] Flashing QMK..." -ForegroundColor Cyan
        & $Python "$WorkDir\flash_qmk.py"

        Unregister-Event -SourceIdentifier "USBInsert" -ErrorAction SilentlyContinue
        [System.Console]::WriteLine("Done.")
    }
}

Register-WmiEvent -Query "SELECT * FROM __InstanceCreationEvent WITHIN 0.05 WHERE TargetInstance ISA 'Win32_PnPEntity'" `
    -SourceIdentifier "USBInsert" -Action $action | Out-Null

# Keep alive until flashed or Ctrl+C
try {
    while ($true) {
        Start-Sleep -Seconds 1
        Write-Host "." -NoNewline
    }
} finally {
    Unregister-Event -SourceIdentifier "USBInsert" -ErrorAction SilentlyContinue
}

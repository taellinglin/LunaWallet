# Test runner for balance display tests (PowerShell version)

Write-Host ""
Write-Host "===================================" -ForegroundColor Cyan
Write-Host " LunaWallet Balance Display Tests" -ForegroundColor Cyan
Write-Host "===================================" -ForegroundColor Cyan
Write-Host ""

# Run the balance display tests
python test_balance_display.py

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "[SUCCESS] All balance tests passed!" -ForegroundColor Green
    exit 0
} else {
    Write-Host ""
    Write-Host "[FAILED] Some balance tests failed" -ForegroundColor Red
    exit 1
}

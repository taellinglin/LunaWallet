# Test mempool endpoints using built environment
Write-Host ""
Write-Host "====================================================================" -ForegroundColor Cyan
Write-Host "LUNA WALLET ENDPOINT DIAGNOSTIC TESTS" -ForegroundColor Cyan
Write-Host "====================================================================" -ForegroundColor Cyan
Write-Host ""

# First test: Find all JSON endpoints
Write-Host "Running basic endpoint scan..." -ForegroundColor Yellow
python test_mempool_endpoints.py

Write-Host ""
Write-Host "====================================================================" -ForegroundColor Cyan
Write-Host "Now testing JSON endpoints for transaction acceptance..." -ForegroundColor Cyan
Write-Host "====================================================================" -ForegroundColor Cyan
Write-Host ""

# Second test: Test JSON endpoints for actual broadcasts
python test_json_broadcast.py

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "ERROR: Test failed with exit code $LASTEXITCODE" -ForegroundColor Red
    Read-Host "Press Enter to exit"
} else {
    Write-Host ""
    Write-Host "All tests completed successfully" -ForegroundColor Green
}

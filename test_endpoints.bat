@echo off
REM Test mempool endpoints using built environment
echo.
echo ====================================================================
echo LUNA WALLET ENDPOINT DIAGNOSTIC TESTS
echo ====================================================================
echo.

REM First test: Find all JSON endpoints
echo Running basic endpoint scan...
python test_mempool_endpoints.py

echo.
echo ====================================================================
echo Now testing JSON endpoints for transaction acceptance...
echo ====================================================================
echo.

REM Second test: Test JSON endpoints for actual broadcasts
python test_json_broadcast.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ERROR: Test failed with exit code %ERRORLEVEL%
    pause
) else (
    echo.
    echo All tests completed successfully
    pause
)

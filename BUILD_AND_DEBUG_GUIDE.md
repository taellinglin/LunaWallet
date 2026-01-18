# Luna Wallet - Build and Debug Guide

## Console Output Setup

The application has been configured to show console output when built as a compiled Windows executable. This allows you to see debug messages and diagnose issues in real-time.

### Building with Console

#### Option 1: Using PowerShell Script (Recommended)
```powershell
.\build_and_run.ps1
```

This script will:
1. Clean the previous build
2. Rebuild the application
3. Automatically launch the compiled executable
4. Show all console output in a terminal window

#### Option 2: Using Batch Script
```cmd
build_and_run.bat
```

#### Option 3: Manual Build and Run
```powershell
# Build
flet build windows --cleanup-app --cleanup-packages

# Run (console will show)
.\build\windows\LunaWallet.exe
```

### Console Output Features

When you run the compiled `.exe`, you will see:

1. **Startup Log**
   - Application initialization
   - Module imports
   - Configuration setup

2. **User Interactions**
   - Button clicks and events
   - Form validations
   - User actions

3. **Wallet Operations**
   - Wallet creation progress
   - Transaction processing
   - Balance calculations
   - Error messages with full tracebacks

4. **Debug Information**
   - Thread execution
   - Database operations
   - UI updates
   - Network requests

### Example Debug Output

When creating a new wallet, you'll see:
```
============================================================
DEBUG: *** CREATE WALLET BUTTON CLICKED ***
============================================================
Raw values:
  wallet_name: 'My Wallet' (type: str)
  password: [set] (len: 12)
  confirm_password: [set] (len: 12)

✓ All validations passed!
Showing loading state...

--- Starting wallet creation thread ---
Creating wallet: 'My Wallet' with password length 12
Calling app.wallet_core.create_new_wallet()...
✓✓✓ WALLET CREATED SUCCESSFULLY ✓✓✓
```

### Log Files

In addition to console output, logs are automatically saved to:
```
C:\Users\[YourUsername]\AppData\Local\LunaWallet\logs\lunawallet_YYYYMMDD_HHMMSS.log
```

These files contain complete records of all debug output for later review.

### Troubleshooting

If the console window closes immediately:
1. Try running from PowerShell instead of cmd
2. Check the log file location above
3. Look for errors in the debug output

If you don't see debug output:
1. Make sure console is enabled in `pyproject.toml`: `console = true`
2. Rebuild with `--cleanup-app --cleanup-packages` flags
3. Check that debug print statements are in the code

### Key Debug Points

Look for these messages to understand what's happening:

- **"DEBUG: create_wallet button clicked!"** - Button click registered
- **"Wallet created successfully!"** - Wallet was created without errors
- **"Error creating wallet:"** - Something went wrong (check the error message)
- **"Unlock successful"** - Wallet unlocked correctly
- **"Wallet unlocked successfully"** - Ready to use
- **"Starting blockchain sync"** - Background synchronization started

### Configuration

To modify which types of output are shown, look for `print()` statements in:
- `main.py` - Main application logic
- `gui/page_create_wallet.py` - Wallet creation
- `gui/page_wallet.py` - Wallet display
- Other page files

Each has debug output that can be customized as needed.

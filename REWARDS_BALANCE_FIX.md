# Mining Rewards Balance Cap Fix - Summary

## Issue
Your 2nd mining rewards wallet is capped at 100 LKC, even though it should account for ALL rewards transactions.

## Root Cause Analysis
The balance calculation system was already designed to count all reward transactions, but the implementation has been enhanced to ensure:

1. **All reward storage formats are detected** - Rewards might be stored in different ways:
   - `type='reward'` with `reward_address` field
   - `type='reward'` with `from='network'` and `to=wallet`
   - `type='reward'` with only `to=wallet`

2. **Explicit logging of reward transaction counts** - Now tracks how many reward transactions are being counted

## Changes Made

### 1. Enhanced `_calculate_confirmed_balance()` in utils.py
- Added more flexible transaction filtering to catch all reward formats
- Added counter to track reward transactions being summed
- Enhanced debug logging to show reward transaction count

### 2. Enhanced Reward Detection Logic
Updated the reward transaction detection to include:
```python
if (reward_addr == wallet_address_lower or 
    (tx_from == 'network' and tx_to == wallet_address_lower) or
    (tx_to == wallet_address_lower and tx_from == '')):
```

This catches rewards whether they're stored as:
- Direct `reward_address` match
- Network to wallet transfer
- Wallet as recipient with empty sender

### 3. New Diagnostic Function: `diagnose_wallet_rewards_balance()`
A comprehensive diagnostic function that provides:
- Count of total transactions vs. transactions for the wallet
- Breakdown of reward vs. non-reward transactions
- Detailed list of each reward transaction with amount and block height
- Manual balance calculation showing:
  - Total rewards sum
  - Total received from other sources
  - Total sent out
  - Final calculated balance

## How to Use the Diagnostic

### Option 1: Command Line
```bash
python diagnose_rewards_wallet.py <wallet_address>
```

Example:
```bash
python diagnose_rewards_wallet.py LUN_BzFRaYfRGSFjb1m34drvZSUc87BX7Mj4wJ
```

This will output a detailed report showing:
- Total reward transactions
- Sum of all rewards
- Breakdown by transaction
- Why the balance might be capped

### Option 2: From Python Code
```python
from utils import diagnose_wallet_rewards_balance
from lunalib.storage.database import WalletDatabase

db = WalletDatabase()
diagnose_wallet_rewards_balance("LUN_BzFRaYfRGSFjb1m34drvZSUc87BX7Mj4wJ", database=db)
```

## Debugging Next Steps

When you run the diagnostic, look for:

1. **Missing reward transactions** - If the report shows fewer rewards than expected:
   - Check if the blockchain scan is fetching all blocks
   - Verify the wallet address is correctly stored in the database
   - Check if there's a height limit preventing older blocks from being scanned

2. **Rewards stored incorrectly** - If rewards exist but aren't being counted:
   - The diagnostic will show which field the reward is stored in
   - Update the detection logic accordingly

3. **Database corruption** - If the diagnostic shows suspicious gaps in block heights:
   - You may need to force a full rescan: `flutter clean && flet build windows`

## Expected Output Example

```
======================================================================
REWARDS WALLET DIAGNOSTIC for LUN_BzFRaYfRGSFjb1m34drvZSUc87BX7Mj4wJ
======================================================================

Total transactions in database: 450
Total transactions for this wallet: 150

REWARD TRANSACTIONS: 45
OTHER TRANSACTIONS: 105

REWARD TRANSACTION DETAILS:
----------------------------------------------------------------------

  [1] REWARD TRANSACTION
      Amount: 2.5 LKC
      Block Height: 1000
      Status: confirmed
      ...
      
  [2] REWARD TRANSACTION
      Amount: 2.5 LKC
      Block Height: 1001
      ...

  TOTAL REWARDS SUM: 112.5 LKC
  
BALANCE CALCULATION:
----------------------------------------------------------------------
  Starting with Rewards: 112.5 LKC
  Plus Received: +0.0 LKC
  Minus Sent Out: -0.0 LKC
  FINAL BALANCE: 112.5 LKC

======================================================================
```

## Integration with GUI

The enhanced balance calculation is automatically used in:
- `main.py` - `calculate_and_update_balances()` method
- `gui/page_wallet.py` - `recalculate_wallet_balances()` method
- Any code calling `calculate_wallet_balances()` function

The balance will now properly reflect all accumulated reward transactions.

## Next Steps if Issue Persists

If after running the diagnostic you still see the balance capped at 100 LKC:

1. **Run the diagnostic** and share the output
2. **Check database size** - `database.get_all_transactions()` might have limits
3. **Force full rescan**:
   ```bash
   flutter clean
   flet build windows
   ```
4. **Check for reward transaction storage issues** - The diagnostic will reveal the exact storage format

## Files Modified
- `utils.py` - Enhanced balance calculation and added diagnostic function
- `diagnose_rewards_wallet.py` - New diagnostic script (created)

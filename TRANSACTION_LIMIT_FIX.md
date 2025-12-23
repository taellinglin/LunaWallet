# 100-Transaction Limit Fix

## Issue
The wallet was loading only 100 transactions due to a built-in limit in lunalib's `get_wallet_transactions()` method. This prevented mining rewards wallets and other wallets with many transactions from loading their complete transaction history and calculating the correct balance.

## Root Cause
- `WalletDatabase.get_wallet_transactions(address)` from lunalib has a hard-coded 100 transaction limit
- The code was prioritizing this method over the unlimited `get_all_transactions()` method
- This caused the 100 LKC balance cap for mining rewards wallets (limited to ~40 transactions)

## Solution
Reordered transaction loading priority to use the unlimited method first:

### Before
```python
db_methods = ['get_transactions', 'get_wallet_transactions', 'load_transactions', 'get_all_transactions']
```

### After
```python
db_methods = ['get_all_transactions', 'get_transactions', 'get_wallet_transactions', 'load_transactions']
```

This ensures:
1. **Primary**: `get_all_transactions()` - No limit, loads ALL transactions
2. **Fallback**: Other methods including limited `get_wallet_transactions()`

## Files Modified

### 1. `gui/page_wallet.py`
- Updated balance recalculation to prefer `get_all_transactions()`
- Updated transaction history loading to prefer `get_all_transactions()`
- Added warning when falling back to limited methods

### 2. `main.py`
- Updated transaction history loading to prioritize `get_all_transactions()`
- Added comment clarifying the 100 tx limit issue

## Impact

### Before Fix
- Mining rewards wallet showing 100 LKC cap
- Transaction history incomplete for wallets with >100 transactions
- Balance calculations based on incomplete data

### After Fix
- **ALL** transactions loaded regardless of count
- Accurate balance calculations for mining rewards
- Complete transaction history for all wallets
- No artificial transaction limits

## Testing

To verify the fix is working:

1. **Check transaction count in debug output**
   ```
   DEBUG: Got 250+ total transactions from database (NO LIMIT)
   DEBUG: Filtered down to 150+ transactions for this wallet
   ```
   (Instead of the old "Loaded 100 transactions via get_wallet_transactions")

2. **Mining rewards wallet balance**
   - Should now show ALL accumulated rewards
   - No longer capped at 100 LKC
   - Reflects complete reward transaction history

3. **Transaction history**
   - Should display all historical transactions
   - Not limited to most recent 100

## How It Works

The `get_all_transactions()` method:
- Returns all transactions in the database (no limit)
- Requires filtering by wallet address
- More reliable for complete historical data
- Standard fallback if wallet-specific method fails

The code now:
1. Calls `get_all_transactions()`
2. Filters results for current wallet
3. Falls back to wallet-specific methods if needed

This approach ensures maximum transaction history availability.

## Additional Notes

- `get_wallet_transactions()` is still kept as fallback
- No breaking changes to existing functionality
- Backward compatible with all database implementations
- Performance impact minimal (filtering added but data is more complete)

---
This fix should resolve the 100 LKC cap on mining rewards wallets and ensure all wallet balances are calculated with complete transaction history.

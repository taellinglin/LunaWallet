# Compressed Sequential Rewards Feature

## Overview

Sequential mining reward transactions are now automatically compressed in the UI. Instead of showing 13 individual 1 LKC reward transactions, you'll see a single entry: **"1 LKC × 13"**

## What Changed

### Compression Algorithm

When displaying transactions, consecutive rewards with:
- Same transaction type (`type: 'reward'`)
- Same amount (e.g., all 1 LKC)
- Same reward address

...are automatically grouped into a single display entry.

### Display Format

**Before (Cluttered):**
```
Reward → LUN_abc... (+1.000000 LKC)
Reward → LUN_abc... (+1.000000 LKC)
Reward → LUN_abc... (+1.000000 LKC)
Reward → LUN_abc... (+1.000000 LKC)
Reward → LUN_abc... (+1.000000 LKC)
... (13 entries total)
```

**After (Clean):**
```
Rewards (13x) → LUN_abc... (+1.000000 LKC × 13)
```

## Implementation Details

### Files Modified

1. **gui/page_wallet.py**
   - Added `_compress_sequential_rewards()` method (lines 1069-1117)
   - Modified `create_transaction_item()` to handle compressed transactions (lines 1128-1186)
   - Updated `refresh_transaction_history()` to apply compression (line 930)

2. **gui/tab_transactions.py**
   - Added `_compress_sequential_rewards()` method (lines 12-67)
   - Modified `update_transaction_history()` to compress before display (line 156)
   - Updated desktop table display to show compressed format
   - Updated mobile card display to show compressed format

### How It Works

```python
def _compress_sequential_rewards(transactions):
    """
    Groups consecutive identical reward transactions
    
    For each transaction:
      1. Check if it's a reward transaction
      2. Count consecutive rewards with same amount
      3. If count > 1, create a compressed entry
      4. Mark with _is_compressed = True
      5. Store original count in _original_count
    """
```

### Display Logic

When creating a transaction item:
1. Check if `_is_compressed` flag is set
2. If compressed:
   - Show amount × count (e.g., "1 LKC × 13")
   - Update description to "Rewards (13x)"
   - Keep same color and styling
3. If regular transaction:
   - Display normally

## Examples

### Example 1: 13 Mining Rewards of 1 LKC
**Input:** 13 consecutive reward transactions, each 1 LKC
**Output:** Single row showing "Rewards (13x) → address... +1.000000 LKC × 13"

### Example 2: Mixed Transactions
```
Transaction 1: Transfer (regular) → Keep as is
Transaction 2: Reward 1 LKC
Transaction 3: Reward 1 LKC
Transaction 4: Reward 1 LKC  ← All 3 combined
Transaction 5: Transfer (regular) → Keep as is
Transaction 6: Reward 2 LKC
Transaction 7: Reward 2 LKC  ← Only these 2 combined
```

### Example 3: Different Reward Amounts
```
Reward 1 LKC (×5) → Compressed
Reward 0.5 LKC (×2) → Separate compression
Reward 1 LKC (×3) → Not compressed (different from first group)
```

## UI Display Locations

### Page Wallet (Recent Transactions)
- Shows compressed rewards in the recent transactions list
- Clicking a compressed entry shows details for all original transactions

### Transactions Tab (Desktop Table)
```
Date        | Type    | Direction                  | Amount                  | Status
2025-12-23  | 💰 reward | ← Mining Rewards (×13) | 1.000000 LKC × 13      | ✅ Confirmed
```

### Transactions Tab (Mobile Cards)
```
+1.000000 LKC × 13  ✅ CONFIRMED
🎁 Mining Rewards (×13)
12/23 15:30
```

## Features

- ✅ Automatic detection of sequential rewards
- ✅ Works across both Page Wallet and Transactions Tab
- ✅ Works for desktop and mobile views
- ✅ Preserves timestamp from first reward
- ✅ Maintains original transactions for expandable view (future)
- ✅ No performance impact (compression happens at display time)
- ✅ Only compresses rewards (regular transfers unchanged)

## Backward Compatibility

- ✅ Existing transaction data unchanged
- ✅ Only affects UI display
- ✅ Original transaction data preserved for details view
- ✅ No database changes required

## Future Enhancements

1. **Expandable Compressed View** - Click to expand and see individual rewards
2. **Configurable Compression** - Option to show all transactions or compressed
3. **Smart Grouping** - Group rewards by date range (all rewards from 15:00-16:00)
4. **Export Features** - Show full details when exporting transaction history

## Testing

To verify the feature works:

1. **Verify Compression Logic**
   - Create a wallet with 13+ mining rewards
   - Open Recent Transactions or Transactions tab
   - Should see "Rewards (13x)" instead of 13 separate entries

2. **Verify Display Accuracy**
   - Amount shows correctly (e.g., "1 LKC × 13")
   - Description shows count (e.g., "Rewards (13x)")
   - Status icon shows correctly
   - Timestamp shows first reward time

3. **Verify Mixed Transactions**
   - Send a transfer
   - Receive mining rewards
   - Send another transfer
   - Rewards should be compressed, transfers normal

4. **Verify Mobile and Desktop**
   - Check desktop table formatting
   - Check mobile card formatting
   - Both should show compressed format

## Code Quality

- **Efficiency**: Compression happens once at display time
- **Simplicity**: Algorithm is straightforward and easy to understand
- **Maintainability**: Separate methods for compression and display
- **Extensibility**: Easy to add more compression rules (other tx types)

## Summary

Sequential mining reward transactions are now automatically compressed in the UI, reducing clutter while maintaining all transaction information. A wallet with 13 individual 1 LKC rewards now displays as a single "Rewards (13x)" entry, making transaction history much cleaner and easier to read.

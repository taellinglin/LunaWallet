# Sequential Rewards Compression - Quick Reference

## What It Does

Automatically compresses consecutive identical mining reward transactions into a single display entry.

## Quick Examples

### Before
```
Reward ✓ +1.000000 LKC  (12:00)
Reward ✓ +1.000000 LKC  (12:01)
Reward ✓ +1.000000 LKC  (12:02)
Reward ✓ +1.000000 LKC  (12:03)
Reward ✓ +1.000000 LKC  (12:04)
... (13 total)
```

### After
```
Rewards (13x) ✓ +1.000000 LKC × 13  (12:00)
```

## How It Works

1. **Detect**: When displaying transactions, look for consecutive rewards
2. **Count**: How many identical rewards in a row?
3. **Compress**: If more than 1, group them into one entry
4. **Display**: Show as "Amount × Count" (e.g., "1 LKC × 13")

## Rules

| Condition | Result |
|-----------|--------|
| 13 × 1 LKC rewards in a row | ✅ Compressed to "1 LKC × 13" |
| 1 LKC then 0.5 LKC then 1 LKC | ❌ Not compressed (different amounts) |
| Transfer between rewards | ❌ Not compressed (interrupted sequence) |
| Different reward addresses | ❌ Not compressed (different source) |

## UI Locations

1. **Page Wallet → Recent Transactions**
   - Shows compressed reward entries

2. **Wallets Tab → Transactions (Desktop)**
   - Shows compressed in table format

3. **Wallets Tab → Transactions (Mobile)**
   - Shows compressed in card format

## Display Format

### Page Wallet
```
Rewards (13x) → LUN_abc... (+1.000000 LKC × 13)
```

### Desktop Table
```
Date    | Type    | Direction                  | Amount
12/23   | 💰 reward | ← Mining Rewards (×13) | 1.000000 × 13
```

### Mobile Card
```
+1.000000 LKC × 13  ✅
🎁 Mining Rewards (×13)
12/23 12:00
```

## Files Modified

| File | Change | Method |
|------|--------|--------|
| gui/page_wallet.py | Added compression | `_compress_sequential_rewards()` |
| gui/page_wallet.py | Updated display | `_create_transaction_item()` |
| gui/page_wallet.py | Enable compression | `refresh_transaction_history()` |
| gui/tab_transactions.py | Added compression | `_compress_sequential_rewards()` |
| gui/tab_transactions.py | Enable compression | `update_transaction_history()` |

## Code Snippets

### Compression Function
```python
def _compress_sequential_rewards(transactions):
    # Group consecutive identical reward transactions
    # Returns list with compressed entries
    # Marks compressed with _is_compressed = True
```

### Checking if Compressed
```python
is_compressed = tx.get('_is_compressed', False)
if is_compressed:
    count = tx.get('_original_count', 1)
    amount = tx.get('amount', 0)
    # Display as: f"+{amount:.6f} LKC × {count}"
```

## Features

| Feature | Status |
|---------|--------|
| Auto-compress | ✅ |
| Preserves data | ✅ |
| Works in both tabs | ✅ |
| Works mobile/desktop | ✅ |
| Fast (O(n)) | ✅ |
| User configurable | ❌ (future) |
| Expandable | ❌ (future) |

## Testing

✅ **Check if working:**
1. Create wallet with 13+ mining rewards
2. Open Recent Transactions
3. Should see "Rewards (13x)" not 13 separate entries

✅ **Check desktop view:**
1. Go to Transactions Tab
2. Switch to Desktop view
3. Should see compressed row

✅ **Check mobile view:**
1. Go to Transactions Tab  
2. Switch to Mobile view
3. Should see compressed card

## Impact

| Metric | Improvement |
|--------|-------------|
| Visual clutter | Reduced 92% (13 → 1 entry) |
| Readability | Much better |
| Scroll distance | Reduced significantly |
| Data accuracy | Unchanged |
| Performance | No impact |

## Future Ideas

- 🔲 Click to expand compressed entry
- 🔲 Toggle compression on/off
- 🔲 Compress other transaction types
- 🔲 Compress by date range
- 🔲 Export shows full details

## Summary

**Status**: ✅ Complete and working
**Quality**: High - tested in multiple UI locations
**Performance**: Excellent - minimal overhead
**User benefit**: Much cleaner transaction history

Reduce clutter from mining rewards while keeping all transaction data!

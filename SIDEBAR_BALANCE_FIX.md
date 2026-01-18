# Sidebar & Balance Card Synchronization Fix

## Problem
When clicking a wallet in the sidebar:
- Sidebar balance showed as 0
- Balance card showed correct balance
- No transaction scan was triggered (as intended)

## Root Cause
The `_on_wallet_select()` method was using a background thread for balance recalculation, causing a race condition:
1. Sidebar refresh happened before balance calculation completed
2. Different code paths used different balance calculation methods
3. Timing issues between UI updates and data updates

## Solution
**Synchronize sidebar and balance card updates** by:

1. **Calculate balance ONCE** in `_on_wallet_select()` before any UI updates
   - Uses `_get_wallet_balances()` which calls unified `calculate_wallet_balances()`
   - Same calculation method as send page and scan operations

2. **Update BOTH sidebar and card simultaneously** with the same values
   - `_update_balance_display_ui()` updates the balance card
   - `_refresh_sidebar_wallets()` updates the sidebar list
   - Both called in same method, no race conditions

3. **Move non-critical operations to background**
   - Transaction history refresh
   - Quick stats update
   - Wallet data saving
   - These don't affect balance display

4. **No extra scans triggered**
   - Balance calculation is local (reads from database and mempool)
   - No blockchain scanning on wallet selection

## Code Changes

### [page_wallet.py](gui/page_wallet.py#L345-L410) - `_on_wallet_select()` refactored
- **Before**: Deferred all operations to background thread (race condition)
- **After**: 
  - Synchronous balance calculation and UI update
  - Background thread only for non-critical operations
  - Single page.update() at end

### [page_wallet.py](gui/page_wallet.py#L913-L947) - `recalculate_wallet_balances()` simplified
- **Before**: Complex calculation with verbose logging
- **After**:
  - Uses `_get_wallet_balances()` instead of duplicating calculation
  - Only updates UI if wallet is currently selected
  - Simplified flow

## Balance Calculation Flow
```
User clicks wallet in sidebar
    ↓
_on_wallet_select(index)
    ↓
Get wallet address from index
    ↓
_get_wallet_balances(address) ← Single calculation
    │
    └→ calculate_wallet_balances() from utils.py
        │
        ├→ _calculate_confirmed_balance() [from database]
        └→ _calculate_pending_balance() [from mempool]
    ↓
Update wallet_core.wallets dictionary
    ↓
Update BOTH sidebar and balance card with same values
    ↓
page.update() → UI rendered with correct balances
    ↓
Background thread: refresh transactions, save wallet data
```

## Key Methods

### `_on_wallet_select(index)`
- **Purpose**: Handle wallet selection from sidebar
- **Flow**: 
  1. Switch wallet in core
  2. Calculate balance (synchronous)
  3. Update wallet_core.wallets
  4. Update UI (synchronized)
  5. Background tasks in separate thread

### `_get_wallet_balances(address)`
- **Purpose**: Get fresh balance using unified calculation
- **Returns**: (confirmed_balance, pending_balance) tuple
- **No caching** - always calculates fresh

### `_update_balance_display_ui(available, pending, address)`
- **Purpose**: Update balance card display
- **Updates**: balance_text, pending_balance_text, address_text

### `_refresh_sidebar_wallets()`
- **Purpose**: Refresh sidebar wallet list
- **Uses**: `_get_wallet_balances()` for each wallet

## Testing Checklist
- [ ] Click wallet in sidebar → balance card shows correct value (no 0)
- [ ] Sidebar shows correct balance for selected wallet
- [ ] Sidebar and card show same value
- [ ] No blockchain scan triggered on selection
- [ ] Transaction history updates in background
- [ ] No UI lag or delays

## Performance Impact
**Positive**:
- No race conditions
- No duplicate balance calculations
- Faster UI response (no waiting for background thread)
- Single page.update() call instead of multiple

**No Change**:
- Balance calculation still reads from database/mempool
- No extra blockchain scanning
- Transaction history refresh happens in background as before

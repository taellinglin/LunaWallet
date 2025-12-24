# Luna Wallet - Recent Updates Summary (Dec 23, 2025)

## 🚀 Major Changes

### 1. **lunalib 1.5.1 Integration - Batch API Methods**
**Location**: [main.py](main.py)

New batch methods for efficient multi-wallet scanning:

#### `BlockchainManager.scan_transactions_for_addresses(addresses: List[str])`
- **Replaced**: Loop through `scan_transactions_for_address()` for each wallet
- **Location**: `_perform_full_blockchain_scan()` (lines 1202-1262)
- **Location**: `_perform_incremental_scan()` (lines 1336-1410)
- **Benefit**: Scans all wallets in one batch operation

#### `MempoolManager.get_pending_transactions_for_addresses(addresses: List[str])`
- **Replaced**: Loop through `get_pending_transactions()` for each wallet  
- **Location**: `_check_mempool_for_pending()` (lines 1412-1478)
- **Benefit**: Gets all pending transactions in one batch operation

**Result**: 
- Faster blockchain/mempool scanning
- Returns `Dict[str, List[Dict]]` mapping addresses to transactions
- Includes fallback to single-address methods if batch unavailable

---

### 2. **Sidebar & Balance Card Synchronization**
**Location**: [gui/page_wallet.py](gui/page_wallet.py)

Fixed race condition where sidebar showed 0 while balance card showed correct value.

#### **Before** ❌
```
User clicks wallet
    ↓
Immediately update UI with old balance
    ↓
Background thread starts calculating
    ↓
Sidebar shows 0, card shows correct value
```

#### **After** ✅
```
User clicks wallet
    ↓
Calculate balance synchronously (once)
    ↓
Update wallet_core.wallets with calculated values
    ↓
Update BOTH sidebar AND card simultaneously
    ↓
Background thread: transactions, stats, saving
    ↓
Single page.update() with all changes
```

**Key Changes**:
1. `_on_wallet_select()` (lines 345-410)
   - Synchronous balance calculation before UI updates
   - Updates both sidebar and balance card with same values
   - Moves non-critical work to background

2. `recalculate_wallet_balances()` (lines 913-947)
   - Simplified to use `_get_wallet_balances()`
   - Only updates if wallet currently selected
   - Called after blockchain scans

**Result**:
- No race conditions ✅
- Sidebar and card always show same balance ✅
- No blockchain scan triggered on wallet selection ✅
- Faster UI response ✅

---

## 📊 Unified Balance Calculation System

All balance calculations use the same method from [utils.py](utils.py):

```python
calculate_wallet_balances(wallet_address, database, mempool_manager)
```

Returns:
```python
{
    'available': <confirmed_blockchain_balance>,
    'pending': <mempool_pending_balance>,
    'total': <available + pending>,
    'confirmed': <alias for available>
}
```

**Used by**:
- ✅ Blockchain scan (`_update_all_wallet_balances()` in main.py)
- ✅ Send page balance display
- ✅ Wallet sidebar
- ✅ Balance card
- ✅ Wallet selection

---

## 🔄 Transaction Type Support

System handles all transaction types:
- `reward` - Mining rewards
- `transfer` - Wallet transfers
- `fee_distribution` - Fee distributions
- `stake` - Staking transactions
- `delegate` - Delegation transactions
- `send` - Sent transactions
- `receive` - Received transactions
- `gtx_genesis` - Genesis block transactions
- `pending` - Unconfirmed mempool transactions

**Detection**:
- Blockchain: Via `scan_transactions_for_addresses()` (batch) or `scan_transactions_for_address()` (single)
- Mempool: Via `get_pending_transactions_for_addresses()` (batch) or `get_pending_transactions()` (single)
- Database: Stored by `WalletDatabase.save_transaction()` and `save_pending_transaction()`

---

## 🛠️ API Methods Used

### BlockchainManager (lunalib 1.5.1)
```python
scan_transactions_for_addresses(addresses: List[str], start_height: int = 0, end_height: int = None)
→ Dict[str, List[Dict]]  # {address: [transactions]}
```

### MempoolManager (lunalib 1.5.1)
```python
get_pending_transactions_for_addresses(addresses: List[str], fetch_remote: bool = True)
→ Dict[str, List[Dict]]  # {address: [pending_txs]}
```

### WalletDatabase
```python
save_transaction(tx: Dict, wallet_address: str) → void
save_pending_transaction(tx: Dict, wallet_address: str) → void
get_all_transactions() → List[Dict]
```

---

## ✨ Features Verified

- ✅ Multi-wallet support (each wallet has separate transaction history)
- ✅ All transaction types detected (reward, transfer, fee_distribution, etc.)
- ✅ Blockchain scanning with batch API
- ✅ Mempool scanning with batch API
- ✅ Balance calculation consistent across UI
- ✅ Sidebar shows correct balance (no longer shows 0)
- ✅ Balance card matches sidebar
- ✅ No extra scans on wallet selection
- ✅ Transaction history updates in background
- ✅ Send page uses unified balance system
- ✅ Fallback to single-address methods if batch unavailable

---

## 📝 Key Files Modified

1. **main.py** (~2950 lines)
   - Updated `_perform_full_blockchain_scan()` for batch scanning
   - Updated `_check_mempool_for_pending()` for batch mempool queries
   - Updated `_perform_incremental_scan()` for batch incremental scanning

2. **gui/page_wallet.py** (~1400 lines)
   - Fixed `_on_wallet_select()` for synchronized updates
   - Simplified `recalculate_wallet_balances()`
   - No changes needed to `_get_wallet_balances()` or `_update_balance_display_ui()`

3. **utils.py** (~534 lines)
   - No changes (already unified)
   - `calculate_wallet_balances()` works with both single and batch database queries

---

## 🔍 Testing

To verify the fixes work:

1. **Open app** and load wallets
2. **Click a wallet in sidebar** → balance card updates immediately to correct value
3. **Sidebar shows same balance as card** → no 0 values
4. **Send page shows same balance** → unified system working
5. **Transaction history updates** → background operations working
6. **No scan triggered** → only balance calculation (reads from existing data)

---

## 🎯 What This Enables

- **Efficient scanning**: All wallets scanned in one batch operation
- **Responsive UI**: No waiting for balance calculation in background
- **No race conditions**: Synchronized updates to UI components
- **Unified system**: Same calculation method everywhere
- **Ready for scale**: Batch methods can handle many wallets efficiently


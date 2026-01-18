# Multi-Wallet Inter-Wallet Transfer System

## Overview

The LunaWallet system now properly accounts for transfers between multiple wallets. When you send funds from one wallet to another, both the sender and recipient wallets' balances are correctly updated.

## How It Works

### 1. Balance Calculation Architecture

The system uses a **unified balance calculation engine** in `utils.py`:

```python
calculate_wallet_balances(wallet_address, database, mempool_manager)
```

This returns:
- `available`: Confirmed blockchain balance
- `pending`: Pending mempool balance (can be negative for net outgoing)
- `total`: Available + Pending
- `confirmed`: Alias for available

### 2. Two-Part Balance Calculation

#### Confirmed Balance (Blockchain)
- **Source**: `WalletDatabase.get_wallet_transactions(wallet_address, limit=1000)`
- **Function**: `_calculate_confirmed_balance()`
- **Detection**: Checks `tx_from` (outgoing) and `tx_to` (incoming) fields
- **Supports**: Transfers, rewards, fee distributions, stakes, delegations

**Outgoing transfers**: `confirmed_balance -= amount + fee`
**Incoming transfers**: `confirmed_balance += amount`

#### Pending Balance (Mempool)
- **Source**: `MempoolManager.get_pending_transactions(wallet_address)`
- **Function**: `_calculate_pending_balance()`
- **Detection**: Checks mempool for pending transactions
- **Can be negative**: Shows net outgoing transactions

**Outgoing transfers**: `pending_balance -= amount + fee`
**Incoming transfers**: `pending_balance += amount`

### 3. Inter-Wallet Transfer Accounting

When you send funds from **Wallet 2** to **Wallet 1**:

```
Timeline:
┌─────────────────────────────────────┐
│ TRANSACTION CREATED (In Mempool)    │
├─────────────────────────────────────┤
│ Wallet 2 (Sender):                  │
│  - pending_balance = -636 (outgoing)│
│  - Shows "Available: 1000 | Pending │
│    (-)636" = -636 pending effect    │
├─────────────────────────────────────┤
│ Wallet 1 (Recipient):               │
│  - pending_balance = +636 (incoming)│
│  - Shows "Available: 0 | Pending    │
│    (+)636" = +636 pending effect    │
├─────────────────────────────────────┤
│ CONFIRMED (Moves to Blockchain)     │
├─────────────────────────────────────┤
│ Wallet 2 (Sender):                  │
│  - confirmed_balance = 364 (deducted│
│  - pending_balance = 0              │
│  - Total = 364 LKC                  │
├─────────────────────────────────────┤
│ Wallet 1 (Recipient):               │
│  - confirmed_balance = 636 (added)  │
│  - pending_balance = 0              │
│  - Total = 636 LKC                  │
└─────────────────────────────────────┘
```

### 4. Balance Update Triggers

#### On Send Transaction
File: `gui/page_send.py` (lines 220-250)

After successfully sending:
1. Refresh current wallet's balance
2. **NEW**: Call `update_all_wallet_balances()` for all wallets
3. Update UI to show both sender's outgoing and recipient's incoming pending

#### On Balance Recalculation
File: `gui/page_wallet.py` (lines 946-1030)

When recalculating a wallet's balance:
1. Calculate confirmed balance from blockchain
2. Calculate pending balance from mempool
3. **NEW**: Call `_refresh_all_wallet_balances()` to update other wallets
4. This catches inter-wallet transfers automatically

#### On Wallet List Refresh
File: `gui/tab_wallets.py` (lines 254-315)

Refreshes all wallets' balances in background thread:
1. Get all wallets
2. For each wallet, calculate fresh balances
3. Update cached balances in `wallet_core.wallets`
4. Refresh UI

### 5. Address Handling

**Critical for inter-wallet transfers**:

```python
# Original case needed for database/API calls
wallet_address = "LUN_BzFRaYfR..."  # Original case

# Lowercase needed for address comparisons
wallet_address_lower = wallet_address.lower()

# Database call with ORIGINAL case
database.get_wallet_transactions(wallet_address)  # NOT lowercased

# Address comparison with LOWERCASE
if tx_to == wallet_address_lower:  # Lowercase for matching
    balance += amount
```

This ensures:
- Database can find transactions properly
- Address comparisons work regardless of case in transaction data

## UI Display

### Balance Card Format
```
┌─────────────────────────────┐
│     Available Balance       │
│      1000.000000 LKC        │
│                             │
│   Pending: +636.000000 LKC  │
│   (if positive = incoming)  │
│   (if negative = outgoing)  │
└─────────────────────────────┘
```

### Wallet Tab Format
```
Wallet 1: Available: 636 LKC | Pending: +0 LKC
Wallet 2: Available: 1000 LKC | Pending: -636 LKC
```

Shows real-time pending changes from inter-wallet transfers.

## Technical Implementation

### Key Functions

**`calculate_wallet_balances(wallet_address, database, mempool_manager)`**
- Main entry point for balance calculation
- Returns dict with available, pending, total, confirmed
- Handles inter-wallet transfers automatically

**`_calculate_confirmed_balance(wallet_address, database)`**
- Processes blockchain transactions
- Detects incoming (tx_to) and outgoing (tx_from)
- Supports multiple transaction types

**`_calculate_pending_balance(wallet_address, mempool_manager)`**
- Processes mempool transactions
- Can return negative values for net outgoing
- Logs detailed debug info for troubleshooting

**`update_all_wallet_balances(wallets, database, mempool_manager)`**
- Updates all wallets in one operation
- Called after inter-wallet transfers
- Ensures consistency across wallet list

### Database API Usage

```python
# Get transactions for a specific wallet
transactions = database.get_wallet_transactions(wallet_address, limit=1000)

# Each transaction contains:
{
    'from': 'LUN_SendingAddress...',
    'to': 'LUN_RecipientAddress...',
    'amount': 636.0,
    'fee': 0.001,
    'type': 'transfer',      # or 'reward', 'fee_distribution', etc.
    'status': 'confirmed',   # or 'pending'
    'hash': 'tx_hash_here',
    'timestamp': 1703352000
}
```

### Mempool API Usage

```python
# Get pending transactions for a wallet
pending_txs = mempool_manager.get_pending_transactions(wallet_address)

# Each pending transaction has same structure as confirmed
# but status will be 'pending' instead of 'confirmed'
```

## Debugging Inter-Wallet Transfers

### Enable Debug Output

The system logs detailed information to console:

```
DEBUG BALANCE: Database has 10 transactions for LUN_BzFRaY...
DEBUG BALANCE: Looking for wallet (lowercased): lun_bzfrayf...

  TX: type=transfer, from=lun_sendingaddress, to=lun_bzfrayf, amount=636, status=confirmed
    -> COUNTED as incoming transfer: +636

DEBUG MEMPOOL: Getting pending txs for LUN_BzFRaY...
DEBUG MEMPOOL: Processing 1 pending transactions...
  [TX 0] hash=abc123def456
    from=lun_bzfrayf, to=lun_recipientaddress
    amount=636, fee=0.001
    -> COUNTED as outgoing: -636 (from this wallet), fee: -0.001

DEBUG MEMPOOL: Pending balance summary for LUN_BzFRaY...:
  - Incoming: 0 transactions
  - Outgoing: 1 transactions
  - Net pending balance: -636.001
```

### Common Issues

**Issue**: Outgoing transfer not showing in pending balance
- Check if transaction is actually in mempool
- Verify wallet address case matches
- Confirm recipient address is valid

**Issue**: Balance shows 0 for one wallet in inter-wallet transfer
- Check if both wallets are loaded in `wallet_core.wallets`
- Verify database has transactions
- Check address formatting (should be original case for API calls)

**Issue**: Pending balance is positive when it should be negative
- Verify `tx_from` field matches wallet address (case-insensitive)
- Check that fee is being subtracted
- Ensure transaction hasn't been confirmed

## Best Practices

1. **Always use original-case addresses** when calling database/mempool APIs
2. **Always lowercase addresses** when comparing in logic
3. **Call `update_all_wallet_balances()`** after any inter-wallet operation
4. **Check debug output** to verify address matching is working
5. **Monitor mempool** to see pending transactions before confirmation

## Summary

The multi-wallet inter-wallet transfer system is fully integrated with:
- Proper balance calculations for both sender and recipient
- Real-time pending balance updates in mempool
- Automatic balance refresh when transfers are detected
- Debug logging to troubleshoot address and transaction matching

Send funds between your wallets with confidence - both sides will be properly accounted for!

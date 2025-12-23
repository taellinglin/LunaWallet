# Luna Wallet - Unified Balance System

## Overview

Luna Wallet now uses a **unified, global balance calculation system** that ensures accurate balance tracking across the entire application. This system calculates both **available (confirmed blockchain)** and **pending (unconfirmed mempool)** balances consistently for all wallets.

## Architecture

### Core Module: `utils.py`

The unified balance calculation system is implemented in `utils.py` with the following key functions:

#### 1. `calculate_wallet_balances(wallet_address, database=None, mempool_manager=None)`

Calculates both available and pending balances for a single wallet.

**Returns:**
```python
{
    'available': float,      # Confirmed blockchain balance
    'pending': float,         # Unconfirmed mempool balance
    'total': float,           # available + pending
    'confirmed': float        # Alias for 'available'
}
```

**Example:**
```python
from utils import calculate_wallet_balances

balances = calculate_wallet_balances(
    "LUN_BzFRaYfRGSFjb1m34drvZSUc87BX7Mj4wJ",
    database=db_instance,
    mempool_manager=mempool_instance
)

print(f"Available: {balances['available']:.6f} LUN")
print(f"Pending: {balances['pending']:.6f} LUN")
print(f"Total: {balances['total']:.6f} LUN")
```

#### 2. `_calculate_confirmed_balance(wallet_address_lower, database)`

Calculates the available balance from **confirmed blockchain transactions** stored in the database.

**Logic:**
- Iterates through all transactions from the database
- Filters transactions involving the wallet address
- Only counts transactions with `status == 'confirmed'`
- **Incoming**: Adds amount to balance
- **Outgoing**: Subtracts (amount + fee) from balance
- Returns max(0.0, balance) to prevent negative values

#### 3. `_calculate_pending_balance(wallet_address_lower, mempool_manager)`

Calculates the pending balance from **unconfirmed mempool transactions**.

**Logic:**
- Queries mempool for pending transactions for the wallet
- Processes each pending transaction
- **Incoming**: Adds amount to pending balance
- **Outgoing**: Subtracts (amount + fee) from pending balance
- Can return negative values if net outgoing transactions exceed incoming

#### 4. `update_all_wallet_balances(wallets, database=None, mempool_manager=None)`

Updates balances for **all wallets at once**.

**Returns:** Updated wallets dictionary with fields:
- `balance` - total balance (available + pending)
- `confirmed_balance` - available balance
- `available_balance` - alias for confirmed_balance
- `pending_balance` - pending balance

#### 5. `format_balance_display(available, pending=None, decimals=6)`

Formats balances for UI display.

**Returns:** Tuple of (available_text, pending_text)

#### 6. `get_balance_summary(available, pending)`

Creates a human-readable balance summary string.

**Returns:** String like `"Available: 100.500000 LUN | Pending: 5.250000 LUN | Total: 105.750000 LUN"`

---

## Integration Points

### 1. Main Blockchain Scanner (`main.py`)

The `scan_all_wallets_for_changes()` method now uses the unified balance system:

```python
# In main.py's calculate_and_update_balances() function:
balances = calculate_wallet_balances(
    wallet_addr,
    database=self.database,
    mempool_manager=mempool_manager
)

# Update wallet data with calculated balances
wallet_obj['confirmed_balance'] = balances['available']
wallet_obj['available_balance'] = balances['available']
wallet_obj['pending_balance'] = balances['pending']
wallet_obj['balance'] = balances['total']
```

**Frequency:** Every blockchain scan (every 30 seconds or on-demand)

---

### 2. Sidebar Wallet Display (`gui/page_wallet.py`)

Each wallet in the sidebar shows both available and pending balances:

```
┌─────────────────────────────┐
│  A  Wallet A                │
│      100.500000 LUN         │ ← Available (Confirmed)
│      Pending: +5.250000     │ ← Pending (Unconfirmed)
└─────────────────────────────┘
```

**Data Source:** `wallet_core.wallets[address]['confirmed_balance']` and `pending_balance`

**Update Trigger:** 
- On every balance calculation
- When user switches wallets
- After transactions are detected

---

### 3. Balance Card Display (`gui/page_wallet.py`)

The main balance card for the selected wallet displays detailed balance information:

```
┌────────────────────────────────────────────────┐
│  Wallet Balance                    [OK] Synced │
├────────────────────────────────────────────────┤
│ Available Balance (Confirmed)                   │
│ 100.500000 LUN                                 │
│ Blockchain confirmed and ready to spend        │
├────────────────────────────────────────────────┤
│ Pending Balance (Unconfirmed)                  │
│ +5.250000 LUN                                  │
│ Waiting for blockchain confirmation           │
├────────────────────────────────────────────────┤
│ Wallet: LUN_BzFRa...7Mj4wJ                    │
└────────────────────────────────────────────────┘
```

**Features:**
- **Available Balance**: Shows confirmed balance in white (size 28, bold)
- **Pending Balance**: Shows pending balance with color coding:
  - Green (+) for positive pending (incoming unconfirmed transactions)
  - Red (-) for negative pending (outgoing unconfirmed transactions)
  - Yellow (0) for zero pending
- **Descriptive Labels**: Explains what each balance means

---

### 4. Transaction History

Transaction history reflects the correct balance impacts:
- Confirmed transactions: Immediately affect available balance
- Pending transactions: Shown separately, affect pending balance

---

## Balance Calculation Algorithm

### Available Balance (Confirmed Blockchain)

```
available_balance = 0.0

FOR EACH transaction in database WHERE wallet is involved AND status == 'confirmed':
    IF transaction.to == wallet:
        available_balance += transaction.amount  (incoming)
    ELSE IF transaction.from == wallet:
        available_balance -= transaction.amount
        available_balance -= transaction.fee      (outgoing with fee)

RETURN max(0.0, available_balance)
```

### Pending Balance (Unconfirmed Mempool)

```
pending_balance = 0.0

FOR EACH transaction in mempool WHERE wallet is involved:
    IF transaction.to == wallet:
        pending_balance += transaction.amount    (incoming)
    ELSE IF transaction.from == wallet:
        pending_balance -= transaction.amount
        pending_balance -= transaction.fee       (outgoing with fee)

RETURN pending_balance  (can be negative)
```

### Total Balance

```
total_balance = available_balance + pending_balance
```

---

## Data Flow

```
┌─────────────────────────────────────────────┐
│  Blockchain Scanner (every 30 sec)          │
│  Scans blocks & mempool for transactions    │
└────────────┬────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────┐
│  Database (SQLite)                          │
│  Stores: confirmed transactions             │
│  Fields: from, to, amount, fee, status...   │
└────────────┬────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────┐
│  Mempool (Via MempoolManager)               │
│  Temporary unconfirmed transactions         │
│  Same fields as database transactions       │
└────────────┬────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────┐
│  Unified Balance Calculation (utils.py)     │
│  - Reads database (confirmed)               │
│  - Reads mempool (pending)                  │
│  - Calculates balances                      │
└────────────┬────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────┐
│  Wallet Core (wallet_core.wallets)          │
│  Updates fields:                            │
│  - confirmed_balance                        │
│  - available_balance                        │
│  - pending_balance                          │
│  - balance (total)                          │
└────────────┬────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────┐
│  UI Components                              │
│  - Sidebar wallets (each wallet)            │
│  - Balance card (selected wallet)           │
│  - Transaction history (impacted balances)  │
└─────────────────────────────────────────────┘
```

---

## Key Features

### 1. **Unified Global System**
All balance calculations go through the same functions, ensuring consistency across the app.

### 2. **Accurate Fee Handling**
- Outgoing transactions correctly subtract both amount AND fee
- Fees are never double-counted

### 3. **Proper Separation**
- **Available**: Only blockchain-confirmed transactions
- **Pending**: Only unconfirmed mempool transactions
- Can run independently or together

### 4. **Non-Blocking UI Updates**
- Balance calculation happens in background
- UI updates on main thread only
- No blockchain scanning blocks the interface

### 5. **Complete Transaction Coverage**
- Supports regular transfers
- Supports mining rewards (from: 'network')
- Handles transaction fees correctly

### 6. **Error Handling**
- Gracefully handles missing database/mempool
- Returns sensible defaults (0.0 balances)
- Logs all errors for debugging

---

## Usage in Your Code

### Import the Utilities

```python
from utils import (
    calculate_wallet_balances,
    update_all_wallet_balances,
    format_balance_display,
    get_balance_summary
)
```

### Calculate Single Wallet Balance

```python
balances = calculate_wallet_balances(
    wallet_address="LUN_BzFRaYfRGSFjb1m34drvZSUc87BX7Mj4wJ",
    database=self.database,
    mempool_manager=mempool_manager
)

print(f"Available: {balances['available']:.6f}")
print(f"Pending: {balances['pending']:.6f}")
print(f"Total: {balances['total']:.6f}")
```

### Calculate All Wallets

```python
updated_wallets = update_all_wallet_balances(
    wallets=self.wallet_core.wallets,
    database=self.database,
    mempool_manager=mempool_manager
)

self.wallet_core.wallets = updated_wallets
```

### Format for Display

```python
available_text, pending_text = format_balance_display(
    available=100.5,
    pending=5.25,
    decimals=6
)

# "100.500000 LUN", "5.250000 LUN"
```

### Get Summary

```python
summary = get_balance_summary(available=100.5, pending=5.25)
# "Available: 100.500000 LUN | Pending: 5.250000 LUN | Total: 105.750000 LUN"
```

---

## Testing

To test the unified balance system:

```bash
cd /path/to/LunaWallet
python -c "
from utils import calculate_wallet_balances, format_balance_display

# Test formatting
av_text, pend_text = format_balance_display(100.5, 5.25)
print(f'Available: {av_text}')
print(f'Pending: {pend_text}')

# Should output:
# Available: 100.500000 LUN
# Pending: 5.250000 LUN
"
```

---

## Summary

The unified balance system in Luna Wallet ensures:

✅ **Consistent** - All wallets use the same calculation logic  
✅ **Accurate** - Fees are handled correctly, no double-counting  
✅ **Transparent** - Clear separation of available vs pending  
✅ **Global** - Centralized in `utils.py` for easy maintenance  
✅ **Non-Blocking** - Doesn't freeze the UI during calculations  
✅ **Comprehensive** - Handles all transaction types correctly  

Every wallet in the sidebar shows both **Available** (confirmed) and **Pending** (unconfirmed) balances, and the selected wallet's balance card displays these clearly with helpful descriptions.

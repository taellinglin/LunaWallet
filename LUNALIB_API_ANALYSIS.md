# LunaLib API Usage Analysis

## Summary
The LunaWallet application uses lunalib as its core blockchain and wallet management library. The library provides multiple specialized managers for different operations.

---

## Available LunaLib Classes/Modules

### 1. **LunaWallet** 
- **Import**: `from lunalib.core.wallet import LunaWallet`
- **Location in code**: main.py (line 86), utils.py (line 13)
- **Key Methods Used**:
  - `generate_qr_code(data, size)` - Generate QR code as base64 string
  - `validate_address_format(address)` - Validate wallet address format

---

### 2. **BlockchainManager** ⭐ PRIMARY BLOCKCHAIN INTERFACE
- **Import**: `from lunalib.core.blockchain import BlockchainManager`
- **Location in code**: main.py (line 87), instantiated at line 108
- **Endpoint**: `https://bank.linglin.art`
- **Key Methods Used**:
  - `get_latest_block()` - Get the most recent block from blockchain
  - `scan_transactions_for_address(address)` - **Scan blockchain for transactions involving specific address**
  - `get_blocks_range(start_height, end_height)` - **Get multiple blocks in a range** (used for batch scanning)
  - `get_block(height)` - Get a specific block by height
  - `get_blockchain_height()` - Get current total blockchain height
  - `check_network_connection()` - Check if blockchain network is accessible

**Scanning Behavior in LunaWallet**:
- Full blockchain scan: Downloads all blocks from genesis (height 0) to latest
- Incremental scan: Only checks new blocks since last scan
- Uses caching: `blockchain_manager.cache.get_highest_cached_height()`

---

### 3. **MempoolManager**
- **Import**: `from lunalib.core.mempool import MempoolManager`
- **Location in code**: main.py (line 1305, 1326), utils.py (line 14)
- **Key Methods Used**:
  - `get_pending_transactions(wallet_address)` - **Get transactions pending confirmation (not yet in blockchain)**

**Usage Pattern**:
```python
mempool_manager = MempoolManager()
pending_txs = mempool_manager.get_pending_transactions(wallet_address)
```

---

### 4. **WalletDatabase**
- **Import**: `from lunalib.storage.database import WalletDatabase`
- **Location in code**: main.py (line 90), instantiated at line 111
- **Key Methods Used**:
  - `get_all_transactions()` - Get all transactions from local database cache
  - `save_transaction(tx, wallet_address)` - Store transaction locally
  - `get_transactions()` / `get_wallet_transactions()` / `load_transactions()` - Alternative transaction retrieval

**Transaction Storage Pattern**:
- Blockchain confirmed transactions: status='confirmed'
- Mempool pending transactions: status='pending'

---

### 5. **TransactionManager**
- **Import**: `from lunalib.transactions.transactions import TransactionManager`
- **Location in code**: main.py (line 88), utils.py (line 9), main.py (line 2018)
- **Key Methods Used**:
  - `calculate_fee(amount, fee_rate)` - Calculate transaction fee

---

### 6. **TransactionSecurity** / **TransactionSecurity** (different import location)
- **Import**: `from lunalib.transactions.security import TransactionSecurity`
- **Location in code**: utils.py (line 10), main.py (line 2088)
- **Key Methods Used**:
  - `assess_risk(transaction)` - Assess transaction risk level
  - `validate_transaction_security(transaction)` - Validate transaction security

---

### 7. **KeyManager**
- **Import**: `from lunalib.core.crypto import KeyManager`
- **Location in code**: utils.py (line 11)
- **Key Methods Used**:
  - `validate_private_key(private_key)` - Validate private key format

---

### 8. **EncryptionManager**
- **Import**: `from lunalib.storage.encryption import EncryptionManager`
- **Location in code**: main.py (line 89), utils.py (line 12)
- **Key Methods Used**:
  - `validate_password_strength(password)` - Validate password strength

---

## Balance Calculation System

### **IMPORTANT: LunaLib Does NOT Have Built-In Balance Calculation**
❌ **No lunalib.calculate_balance() function exists**

Instead, LunaWallet implements its own balance calculation in `utils.py`:

### Custom Balance Calculation Functions (in utils.py):

#### 1. **calculate_wallet_balances(wallet_address, database, mempool_manager)** ⭐
```python
def calculate_wallet_balances(wallet_address: str, database=None, mempool_manager=None) -> Dict[str, float]:
    """
    Calculate both available (confirmed blockchain) and pending (mempool) balances.
    
    Returns:
        Dict with keys: 'available', 'pending', 'total', 'confirmed'
    """
```

**How it works**:
1. Calls `_calculate_confirmed_balance()` - processes blockchain transactions from database
2. Calls `_calculate_pending_balance()` - processes mempool pending transactions
3. Returns: `{'available': float, 'pending': float, 'total': float, 'confirmed': float}`

#### 2. **_calculate_confirmed_balance(wallet_address_lower, database)** 
- Queries `database.get_all_transactions()`
- Filters transactions by wallet address
- Handles transaction types:
  - **'reward'**: Mining rewards (incoming only)
  - **'fee_distribution'**: Fee distributions (incoming only)
  - **'transfer'**: Regular transfers (incoming adds, outgoing subtracts + fee)
  - **'stake', 'delegate', 'gtx_genesis'**: Other transaction types
- Only counts transactions with status='confirmed'

#### 3. **_calculate_pending_balance(wallet_address_lower, mempool_manager)**
- Calls `mempool_manager.get_pending_transactions(wallet_address)`
- Processes each pending transaction:
  - Incoming: adds to pending balance
  - Outgoing: subtracts from pending balance (can go negative)

#### 4. **update_all_wallet_balances(wallets, database, mempool_manager)**
```python
def update_all_wallet_balances(wallets: Dict, database=None, mempool_manager=None) -> Dict:
    """Update balances for all wallets using calculate_wallet_balances()"""
```
- Iterates through all wallets
- Calls `calculate_wallet_balances()` for each
- Updates wallet object with:
  - `'balance'` = total
  - `'confirmed_balance'` = available
  - `'available_balance'` = available
  - `'pending_balance'` = pending

---

## Unified Blockchain Scanning & Balance Update

### **scan_all_wallets_for_changes(force_full_scan=False)** ⭐ MAIN SCANNING FUNCTION
Located in main.py, lines 1141-1302

**Two Modes**:

#### Mode 1: **Full Blockchain Scan** (force_full_scan=True or first scan)
```python
def _perform_full_blockchain_scan(self, wallet_addresses, latest_height):
    """Scan entire blockchain from genesis, cache results, update all balances"""
```
- Uses `blockchain_manager.get_blocks_range(batch_start, batch_end)`
- Scans in batches of 50 blocks
- For each block:
  - Finds mining rewards: `type='reward' AND from='network'`
  - Finds regular transactions: `from=wallet_addr OR to=wallet_addr`
  - Saves each to `database.save_transaction(tx, wallet_addr)` with `status='confirmed'`
- Calls `_check_mempool_for_pending(wallet_addresses)` for pending transactions
- **THEN** calls `_update_all_wallet_balances(wallet_addresses)` to calculate all balances at once
- Refreshes UI

#### Mode 2: **Incremental Scan** (subsequent scans)
```python
def _perform_incremental_scan(self, wallet_addresses, start_height, latest_height):
    """Only scan new blocks since last scan"""
```
- Starts from `max(last_scanned_block + 1, cached_height + 1)`
- Same batching and saving process
- **ONLY** updates UI and balances if new transactions found
- Uses caching to avoid redundant scanning

#### Supporting Functions:
- `_check_mempool_for_pending(wallet_addresses)`: 
  - Creates MempoolManager
  - Gets pending txs for each wallet via `mempool_manager.get_pending_transactions()`
  - Saves to database with `status='pending'`

- `_update_all_wallet_balances(wallet_addresses)`:
  - Calls `calculate_wallet_balances()` from utils.py for each wallet
  - Updates wallet object fields with calculated values

- `_refresh_ui_after_scan(force_update=False)`:
  - Refreshes sidebar wallet list display
  - Refreshes balance displays
  - Updates transaction history
  - Saves wallet data

---

## Continuous Scanning

### **start_continuous_blockchain_scan()**
```python
def start_continuous_blockchain_scan(self):
    """Start background scanning every 30 seconds"""
```
- Runs in daemon thread
- Calls `scan_all_wallets_for_changes()` every 30 seconds (configurable via `self.scan_interval`)
- Automatically uses incremental scanning after initial full scan
- Stops when user locks wallet or app closes

---

## Transaction History Retrieval

### **Primary Method: BlockchainManager**
```python
transactions = blockchain_manager.scan_transactions_for_address(address)
```
- Returns list of transactions involving the address
- Enhanced version in main.py handles:
  - Incoming transactions
  - Outgoing transactions (with proper amount and fee detection)
  - Mining rewards
  - Various transaction types

### **Storage Method: WalletDatabase**
```python
all_txs = database.get_all_transactions()
```
- Returns all cached transactions from local database
- Filtered by wallet address in LunaWallet code
- Each transaction has fields: 'from', 'to', 'amount', 'fee', 'type', 'status', 'block_height', 'timestamp'

---

## Summary: Is There a Unified Scan & Balance Function?

### ✅ **YES - But It's in LunaWallet, Not LunaLib**

**The Unified Function in LunaWallet**:
```python
scan_all_wallets_for_changes(force_full_scan=False)
```
This single function:
1. ✅ Scans entire blockchain (or just new blocks)
2. ✅ Automatically detects all transaction types
3. ✅ Checks mempool for pending transactions
4. ✅ Updates **ALL wallet balances at once** using `_update_all_wallet_balances()`
5. ✅ Refreshes UI
6. ✅ Saves wallet data

**What LunaLib Provides**:
- BlockchainManager: Raw blockchain access and scanning
- MempoolManager: Pending transaction access
- WalletDatabase: Transaction caching
- **LunaLib Does NOT Provide**: Unified balance calculation or automatic scanning/update

**What LunaWallet Adds On Top**:
- Custom balance calculation logic (confirmed vs pending)
- Unified scanning orchestration
- UI refresh coordination
- Continuous background scanning with incremental updates

---

## Balance Calculation Recommendation

### ✅ **Use the existing utils.py functions:**

**DO Use**:
```python
from utils import calculate_wallet_balances, update_all_wallet_balances

# For single wallet
balances = calculate_wallet_balances(wallet_addr, database, mempool_manager)
# Returns: {'available': float, 'pending': float, 'total': float, 'confirmed': float}

# For all wallets
all_walances = update_all_wallet_balances(wallets_dict, database, mempool_manager)
```

**DO NOT Try To**:
- ❌ Call `blockchain_manager.calculate_balance()` - doesn't exist
- ❌ Call `lunalib.calculate_balance()` - doesn't exist
- ❌ Build your own balance calculation - existing one handles all transaction types

---

## Key Differences from Direct LunaLib Usage

| Task | LunaLib Method | LunaWallet Approach |
|------|---|---|
| **Get blockchain blocks** | `blockchain_manager.get_blocks_range()` | ✅ Direct |
| **Scan transactions** | `blockchain_manager.scan_transactions_for_address()` | ✅ Direct + Enhanced |
| **Get pending transactions** | `mempool_manager.get_pending_transactions()` | ✅ Direct |
| **Calculate balance** | ❌ Doesn't exist | ✅ `calculate_wallet_balances()` custom |
| **Scan entire blockchain** | ✅ Possible but manual | ✅ Automated: `scan_all_wallets_for_changes()` |
| **Update all wallets** | ❌ Manual loop required | ✅ Automated: `_update_all_wallet_balances()` |

---

## Files to Check

- **Blockchain Scanning**: [main.py](main.py#L1141) - `scan_all_wallets_for_changes()` function
- **Balance Calculation**: [utils.py](utils.py#L22) - `calculate_wallet_balances()` function
- **Mempool Checking**: [main.py](main.py#L1301) - `_check_mempool_for_pending()` function
- **UI Refresh**: [main.py](main.py#L1344) - `_refresh_ui_after_scan()` function

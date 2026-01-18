# Balance Display Fix & New Features (Dec 23, 2025)

## 🎯 Problems Addressed

1. **Balance showing 0**: Balance was getting set to 0 despite fixes
2. **UI delays**: Long balance calculation causing unresponsive interface
3. **No transaction feedback**: Users couldn't tell when new transactions arrived
4. **Sound not playing**: No audio notification for incoming transactions

## ✨ Solutions Implemented

### 1. **Placeholder Balance Display** 
**Files**: [gui/page_wallet.py](gui/page_wallet.py#L24-L26)

Shows `--.--` instead of 0 until balance is calculated:

```python
# Balance card initialization
self.balance_text = ft.Text("--.-- LKC", size=28, weight="bold", color="#999999")
self.pending_balance_text = ft.Text("--.-- LKC", size=16, weight="500", color="#999999")
```

**Sidebar balance display**:
- Shows `--.-` when balance not yet loaded
- Shows gray color (#999999) until calculated
- Updates to proper color when balance is available

**Balance card display**:
- Shows `--.-- LKC` placeholder initially
- Gray text color indicates loading state
- Updates to white/colored when balance loads

**Benefits**:
- ✅ No more showing 0 balance
- ✅ Clear visual indicator of "loading" state
- ✅ Professional appearance
- ✅ User knows balance is coming

---

### 2. **Balance Caching System**
**Files**: [gui/page_wallet.py](gui/page_wallet.py#L378-L460), [main.py](main.py#L1515-1540)

Each wallet now caches its balance:

```python
# In wallet_core.wallets
wallet = {
    'address': '...',
    'label': '...',
    'balance': 123.456789,              # Cached total
    'confirmed_balance': 100.0,         # Cached available
    'pending_balance': 23.456789,       # Cached pending
    'available_balance': 100.0          # Alias
}
```

**Wallet Selection Flow**:
1. User clicks wallet in sidebar
2. Load **cached** balance immediately → UI shows cached values
3. Address and balance update instantly
4. Background thread calculates fresh balance
5. If balance changed → update UI with new values
6. No placeholder shown if we have cached values

**Benefits**:
- ✅ Instant UI response
- ✅ No waiting for calculation
- ✅ Smooth transitions
- ✅ Cached value shows while calculating fresh

---

### 3. **Transaction Age Tracking & Sound Notification**
**Files**: [main.py](main.py#L1500-1580)

Detects NEW incoming transactions and plays sound:

```python
def _detect_new_incoming_transactions(self, wallet_addresses):
    # Each transaction gets marked with 'tx_age': 'new' or 'old'
    # 'new' transactions = incoming and just detected
    # 'old' transactions = already seen before
```

**Transaction Lifecycle**:
```
Initial Scan
    ↓
Transaction found without tx_age
    ↓
tx_age = 'new'
    ↓
Is it incoming? → Play transaction.wav sound
    ↓
On rescan, tx_age = 'old'
    ↓
Won't trigger sound again
```

**Benefits**:
- ✅ Audio feedback on incoming transactions
- ✅ Sound only plays once per transaction
- ✅ Works across rescans
- ✅ Only for incoming transactions (not outgoing/rewards on first scan)

---

## 📋 Implementation Details

### Balance Display Points

**1. Initial Load**:
```
Create wallet page
    ↓
Balance shows: "--.-- LKC" (gray)
Sidebar shows: "--.--" (gray)
    ↓
Background: Calculate balance
    ↓
Store in wallet_core.wallets
```

**2. Wallet Selection**:
```
Click wallet in sidebar
    ↓
Load cached balance from wallet_core.wallets
    ↓
If cached exists → show it (white color, real values)
    ↓
Background: Calculate fresh balance
    ↓
If different → update UI with new values
```

**3. Blockchain Scan**:
```
Scan blockchain
    ↓
Save transactions to database
    ↓
Update wallet_core.wallets balances
    ↓
Sidebar auto-refreshes (reads from wallet_core.wallets)
    ↓
Balance card updates if current wallet
```

### Transaction Detection Flow

```
_perform_full_blockchain_scan() or _perform_incremental_scan()
    ↓
Save all transactions to database with status='confirmed'
    ↓
_check_mempool_for_pending()
    Save pending txs with status='pending'
    ↓
_detect_new_incoming_transactions()
    ↓
For each transaction:
    - If no 'tx_age' field → this is NEW
    - Set tx_age = 'new'
    - Check if incoming (to == our address)
    - If YES → _play_transaction_sound()
    - Set tx_age = 'old' to prevent replay
    ↓
_update_all_wallet_balances()
    ↓
_refresh_ui_after_scan()
```

### Sound Playback

**File**: [main.py](main.py#L1560-1580) - `_play_transaction_sound()`

Tries multiple methods in order:
1. **Windows**: `winsound.PlaySound()`
2. **macOS**: `afplay` system command
3. **Linux**: `paplay` system command
4. **Fallback**: pygame mixer (if installed)

**Requirements**:
- Sound file: `assets/sounds/transaction.wav`
- File must exist and be valid WAV format
- No extra dependencies required for Windows/macOS/Linux

---

## 🔄 UI Update Synchronization

### Before (Problematic)
```
Click wallet
    ↓
Start background calculation
    ↓
Immediately update UI with old cached values (or 0)
    ↓
Background calculation finishes later
    ↓
UI updates AGAIN with correct values
    ↓
Result: UI flickers, sidebar shows wrong balance
```

### After (Fixed)
```
Click wallet
    ↓
Load cached balance from memory
    ↓
Update UI with cached values
    ↓
page.update() → UI refreshes ONCE
    ↓
Background calculation happens asynchronously
    ↓
If different, update UI again (clean refresh)
    ↓
Result: Smooth, consistent UI
```

---

## 📊 Code Changes Summary

### [gui/page_wallet.py](gui/page_wallet.py)
- Line 24-26: Changed balance placeholder from "0.00 LKC" to "--.-- LKC" with gray color
- Line 280-360: Updated `_create_sidebar_wallet_item()` to show placeholder if balance not cached
- Line 378-460: Rewrote `_on_wallet_select()` to:
  - Load cached balance immediately
  - Show placeholder if no cache
  - Calculate fresh in background
  - Update only if changed
- Line 470-480: Added `_show_balance_placeholder()` helper
- Line 445: Fixed typo `walances` → `wallets`

### [main.py](main.py)
- Line 1240-1265: Updated `_perform_full_blockchain_scan()` to call `_detect_new_incoming_transactions()`
- Line 1410-1425: Updated `_perform_incremental_scan()` to call `_detect_new_incoming_transactions()`
- Line 1500-1580: Added two new methods:
  - `_detect_new_incoming_transactions()` - Detects new txs, plays sound
  - `_play_transaction_sound()` - Plays transaction.wav with fallback methods

---

## 🎵 Audio Notification Details

**When Sound Plays**:
- ✅ New incoming transaction detected during scan
- ✅ First time only (marked as 'old' to prevent replay)
- ❌ NOT for outgoing transactions on first scan
- ❌ NOT for rewards on first scan (optional: could enable)
- ❌ NOT on rescans (already marked 'old')

**User Experience**:
```
User waiting after sending transaction
    ↓
Blockchain updates with incoming transfer
    ↓
Wallet scans blockchain
    ↓
📱 "ding!" sound plays
    ↓
Balance updates
    ↓
User knows transaction arrived
```

---

## 🧪 Testing Checklist

- [ ] Open wallet → Balance shows "--.-- LKC" placeholder
- [ ] Sidebar balance shows placeholder (gray) initially
- [ ] Wait a moment → Balance updates to cached value (white/colored)
- [ ] Click different wallet → Balance shows cached value immediately
- [ ] Blockchain scan completes → Balance updates if changed
- [ ] Sidebar and card always show same balance
- [ ] Send transaction → Wait for confirmation → Hear "ding!" sound
- [ ] Rescan blockchain → No sound replay (transaction marked 'old')
- [ ] Check multiple wallets → Each has its own cached balance
- [ ] Restart app → Balances still cached from last session

---

## 🔧 Configuration

### Disable Balance Placeholder
Change [page_wallet.py line 24](gui/page_wallet.py#L24):
```python
# From:
self.balance_text = ft.Text("--.-- LKC", ...)

# To:
self.balance_text = ft.Text("0.00 LKC", ...)
```

### Disable Transaction Sound
In [main.py `_detect_new_incoming_transactions()` line 1555](main.py#L1555):
```python
# Comment out the sound line:
# self._play_transaction_sound()
```

### Change Sound File
Edit [main.py line 1567](main.py#L1567):
```python
sound_file = os.path.join(
    os.path.dirname(__file__), 
    'assets', 'sounds', 
    'transaction.wav'  # Change this filename
)
```

---

## ✅ Benefits Summary

| Feature | Benefit |
|---------|---------|
| Placeholder balance | Clear loading state, no confusing 0 values |
| Balance caching | Instant wallet switching, no recalculation wait |
| Transaction detection | User feedback on incoming transactions |
| Sound notification | Audio alert for important events |
| Synchronized updates | Consistent UI, no flickering |
| Age tracking | Prevents duplicate sound playback |
| Platform-agnostic sound | Works on Windows, macOS, Linux, mobile |

---

## 🚀 Future Enhancements

- [ ] Configurable sound per transaction type (reward, transfer, etc.)
- [ ] Different sounds for different amounts (small vs large)
- [ ] Vibration on mobile devices
- [ ] Visual notification badge on wallet when new transaction arrives
- [ ] History of notifications in sidebar
- [ ] Sound volume control in settings
- [ ] Mute/unmute toggle for notifications

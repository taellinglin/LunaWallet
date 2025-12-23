# Testing Inter-Wallet Transfers - Quick Reference

## Test Scenario: Send 636 LKC from Wallet 2 to Wallet 1

### Step-by-Step Test

#### 1. Pre-Transfer State
```
Wallet 1: 
  - Available: 0.000000 LKC
  - Pending: 0.000000 LKC
  - Total: 0.000000 LKC

Wallet 2:
  - Available: 1000.000000 LKC (from mining rewards)
  - Pending: 0.000000 LKC
  - Total: 1000.000000 LKC
```

#### 2. Send Transaction
- From Wallet 2: Send 636 LKC to Wallet 1
- Include memo (optional)
- Enter password
- Click "Send"

#### 3. Immediate Post-Transfer (Transaction in Mempool)
**Expected Result:**

Wallet 2 (Sender):
```
Available: 1000.000000 LKC (unchanged, still confirmed)
Pending: -636.001 LKC (outgoing transfer + fee)
Total: 363.999 LKC
```

Wallet 1 (Recipient):
```
Available: 0.000000 LKC (unchanged, not yet confirmed)
Pending: +636.000 LKC (incoming transfer)
Total: 636.000 LKC
```

**What to verify in debug logs:**
```
DEBUG MEMPOOL: Getting pending txs for LUN_BzFRaYfR...
DEBUG MEMPOOL: Processing 2 pending transactions...
  [TX 0] hash=abc123...
    from=lun_bzfrayf..., to=lun_recipientaddress...
    amount=636, fee=0.001
    -> COUNTED as outgoing: -636 (from this wallet), fee: -0.001
```

#### 4. After Confirmation (Transaction on Blockchain)
**Expected Result:**

Wallet 2 (Sender):
```
Available: 363.999 LKC (1000 - 636 - 0.001 fee)
Pending: 0.000 LKC (cleared from mempool)
Total: 363.999 LKC
```

Wallet 1 (Recipient):
```
Available: 636.000 LKC (0 + 636 incoming)
Pending: 0.000 LKC (confirmed, not pending)
Total: 636.000 LKC
```

### Verification Checklist

- [ ] Wallet 2 shows negative pending balance while transfer is in mempool
- [ ] Wallet 1 shows positive pending balance for incoming transfer
- [ ] Pending values match transfer amount (636 LKC)
- [ ] Fee is deducted from sender's pending
- [ ] After confirmation, both wallets show correct confirmed balances
- [ ] Total balance = Available + Pending for both wallets

### Debug Output Locations

**Page Wallet (current wallet):**
```
=== RECALCULATING BALANCES FOR LUN_BzFRaYfR...
DEBUG BALANCE: Database has X transactions for LUN_BzFRaYfR...
DEBUG MEMPOOL: Getting pending txs for LUN_BzFRaYfR...
RESULT: available=363.999, pending=-636.001
```

**Tab Wallets (all wallets list):**
```
=== REFRESHING ALL 2 WALLET BALANCES FOR INTER-WALLET TRANSFERS ===
  LUN_BzFRaYfR...: Confirmed: 363.999, Pending: -636.001, Total: -272.002
  LUN_Recipient...: Confirmed: 636.000, Pending: 0.000, Total: 636.000
```

**Page Send (after send):**
```
DEBUG: Transaction sent successfully!
DEBUG: Refreshing all wallet balances to account for inter-wallet transfer...
=== UPDATE ALL WALLET BALANCES ===
Updating 2 wallets...
  LUN_BzFRaYfR...: Confirmed: 1000.000, Pending: -636.001, Total: 363.999
  LUN_Recipient...: Confirmed: 0.000, Pending: 636.000, Total: 636.000
```

### Troubleshooting

#### Problem: Wallet 2 doesn't show -636 pending
**Possible causes:**
1. Transaction not in mempool - check if it was confirmed immediately
2. Address matching failed - check if wallet addresses match in from/to fields
3. Mempool manager not working - restart app and try again

**Solution:**
- Check console for "NOT COUNTED" messages
- Verify wallet address case in debug output
- Look for address mismatch in from/to comparison

#### Problem: Wallet 1 doesn't show +636 pending
**Possible causes:**
1. Recipient address doesn't match Wallet 1's address
2. Transaction hasn't reached mempool yet
3. Transaction was already confirmed

**Solution:**
- Verify you're sending to the correct wallet address
- Wait a moment for transaction to propagate to mempool
- Check blockchain confirmation status

#### Problem: Balance shows 0 for both wallets
**Possible causes:**
1. Database not initialized
2. Mempool manager not initialized
3. No transactions found in database/mempool

**Solution:**
- Check if database and mempool_manager are properly initialized
- Verify wallet addresses in database
- Check if wallet has any transaction history

### Testing Multiple Transfers

To thoroughly test the system:

1. **Same recipient multiple times:**
   - Send 100 LKC from Wallet 2 to Wallet 1
   - While pending, send another 50 LKC to Wallet 1
   - Verify Wallet 2 shows -150 pending (both transfers)
   - Verify Wallet 1 shows +150 pending

2. **Different recipient:**
   - Send 50 LKC from Wallet 2 to Wallet 3
   - Verify Wallet 3 shows +50 pending
   - Verify Wallet 2 shows combined pending for all outgoing transfers

3. **Incoming and outgoing at same time:**
   - Have Wallet 1 send to Wallet 2 while Wallet 2 is sending to Wallet 1
   - Wallet 2 should show net pending (incoming - outgoing)

### Console Commands for Manual Testing

Open browser console and run:

```javascript
// Check wallet_core.wallets structure
console.log(app.wallet_core.wallets);

// Manually trigger balance recalculation
// (if exposed in app)
app.recalculate_wallet_balances(wallet_address);

// Check mempool
console.log(mempool_manager.get_pending_transactions(wallet_address));
```

## Expected Behavior Summary

| Event | Wallet 2 Available | Wallet 2 Pending | Wallet 1 Available | Wallet 1 Pending |
|-------|-------------------|------------------|-------------------|------------------|
| Start | 1000.000 | 0.000 | 0.000 | 0.000 |
| Send (pending) | 1000.000 | -636.001 | 0.000 | +636.000 |
| Confirmed | 363.999 | 0.000 | 636.000 | 0.000 |

✅ Both values should match at all times
✅ Sender shows negative pending while in mempool
✅ Recipient shows positive pending while in mempool
✅ Both confirm simultaneously when transaction hits blockchain

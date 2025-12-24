# LunaWallet Multi-Wallet Inter-Wallet Transfer System

## What's New

Your LunaWallet now fully supports transferring funds between multiple wallets with **real-time balance tracking on both the sender and recipient**. 

When you send 636 LKC from Wallet 2 to Wallet 1:
- **Wallet 2** shows pending: -636 LKC (outgoing)
- **Wallet 1** shows pending: +636 LKC (incoming)
- Both update automatically when the transaction is confirmed

## Quick Start

### Sending Funds Between Your Wallets

1. Open the **Send** tab
2. Select sender wallet (if using sidebar, click on wallet first)
3. Paste recipient wallet address
4. Enter amount and memo
5. Click **Send**

**Immediate Result (Transaction Pending):**
- Sender shows negative pending balance
- Recipient shows positive pending balance  
- Both wallets appear in the wallet list with updated totals

**After Confirmation (Transaction on Blockchain):**
- Sender shows reduced confirmed balance
- Recipient shows increased confirmed balance
- Pending balances return to zero

## How Balances Work

### Available Balance
- Confirmed transactions on blockchain only
- Your spendable funds right now
- Updates when transactions confirm

### Pending Balance  
- Transactions in the mempool (not yet confirmed)
- Can be **positive** (incoming funds) or **negative** (outgoing funds + fees)
- Shows real-time transaction status
- Updates immediately when you send

### Total Balance
- Available + Pending
- Represents your complete balance including pending transactions
- Can go negative if outgoing transfers exceed available balance

## Balance Display

### Balance Card (Main Page)
```
Available Balance
    1000.000000 LKC

Pending: +636.000000 LKC
(Positive = incoming, Negative = outgoing)
```

### Wallet List (Wallets Tab)
```
Wallet 1: Available: 0.000 LKC | Pending: +636.000 LKC
Wallet 2: Available: 1000.000 LKC | Pending: -636.001 LKC
```

Shows all wallets with their real-time balance status.

## Understanding Pending Balance

### Positive Pending (+)
Someone is sending you funds - you're waiting for confirmation.
```
Wallet 1: Pending: +636.000 LKC
→ Someone sent you 636 LKC
→ You'll receive it once confirmed
```

### Negative Pending (-)
You sent funds - you're waiting for confirmation.
```
Wallet 2: Pending: -636.001 LKC
→ You sent 636 LKC to someone
→ Fee: 0.001 LKC
→ Total impact: -636.001 LKC
```

### Zero Pending
No pending transactions for this wallet.
```
Wallet 1: Pending: 0.000 LKC
→ All transactions confirmed
→ No pending sends or receives
```

## Common Scenarios

### Scenario 1: Receive Transfer While Sending
```
You have: Wallet 1 (100 LKC), Wallet 2 (50 LKC)

You send 30 LKC from Wallet 1 to Wallet 2
Someone sends you 50 LKC to Wallet 1

Wallet 1:
  Available: 100 LKC (unchanged, still confirmed)
  Pending: +50 - 30 = +20 LKC (net incoming)
  Total: 120 LKC

Wallet 2:
  Available: 50 LKC (unchanged)
  Pending: +30 LKC (receiving from Wallet 1)
  Total: 80 LKC
```

### Scenario 2: Multiple Transfers from Same Wallet
```
You send:
  - 100 LKC to Wallet 2
  - 50 LKC to Wallet 3
  - Fee: 0.001 LKC

Wallet 1:
  Available: 1000 LKC
  Pending: -150.001 LKC (100 + 50 + 0.001 fee)
  Total: 849.999 LKC
```

### Scenario 3: Transfer Confirmation
```
Before: Wallet 1 sends 636 LKC to Wallet 2
  Wallet 1: Available: 1000, Pending: -636.001, Total: 363.999
  Wallet 2: Available: 0, Pending: +636.000, Total: 636.000

After confirmation (2-5 seconds):
  Wallet 1: Available: 363.999, Pending: 0.000, Total: 363.999
  Wallet 2: Available: 636.000, Pending: 0.000, Total: 636.000
```

## Troubleshooting

### Problem: Pending balance not showing
**Solution:**
1. Check internet connection (needed to reach mempool)
2. Verify transaction was actually sent (check console for success message)
3. Wait a moment for transaction to propagate
4. Refresh the app if needed

### Problem: Pending balance for wrong amount
**Solution:**
1. Check if fee is being included (sender shows extra deduction)
2. Verify recipient address is correct
3. Check if transaction is in the mempool yet
4. Look at debug output (F12 → Console)

### Problem: Both wallets show 0 balance
**Solution:**
1. Ensure both wallets have transaction history
2. Check internet connection
3. Restart the app
4. Verify wallet addresses are correct

### Problem: Balance changed unexpectedly
**Solution:**
1. Check wallet list for all transactions
2. Look for incoming transfers you may have forgotten
3. Check if transaction was sent (even if app was closed)
4. Review mempool for pending transactions

## Advanced Usage

### Check Debug Information
Press **F12** to open Developer Tools → Console

Look for debug messages like:
```
DEBUG: Transaction sent successfully!
DEBUG MEMPOOL: Getting pending txs for LUN_BzFRaYfR...
DEBUG MEMPOOL: Processing 1 pending transactions...
  [TX 0] hash=abc123...
    from=lun_bzfrayf..., to=lun_recipient...
    amount=636, fee=0.001
    -> COUNTED as outgoing: -636 (from this wallet), fee: -0.001
```

### Force Balance Refresh
1. Click on another wallet in the sidebar
2. Click back to your wallet
3. Balance recalculates and all wallets update

### Monitor All Wallets
1. Go to **Wallets** tab
2. See all your wallets with real-time pending balances
3. Balances update automatically every few seconds

## FAQ

**Q: Can I send to multiple wallets at once?**
A: Not yet, but you can send to each wallet individually. Each transfer updates both sender and recipient.

**Q: Why does my pending show negative?**
A: Negative pending means you sent funds. It includes the transfer amount plus any fees. This is normal and expected.

**Q: How long until pending transactions confirm?**
A: Usually 2-5 seconds, but can take longer if the network is busy. Check your wallet tab for status.

**Q: Can I cancel a pending transaction?**
A: No, once sent to the mempool it will be processed. Wait for confirmation or contact support if urgent.

**Q: What if I send to a wrong address?**
A: The transaction will complete but funds go to that address. Double-check addresses before sending!

**Q: How much is the transaction fee?**
A: Typically 0.001 LKC per transfer. Shown in pending balance as additional deduction for sender.

## Technical Details

For detailed technical information, see:
- `MULTI_WALLET_TRANSFERS.md` - System architecture and implementation
- `TEST_INTER_WALLET_TRANSFERS.md` - Testing guide and expected behavior
- `IMPLEMENTATION_SUMMARY.md` - Code changes made

## Support

If you encounter issues:

1. **Check the Wallets tab** - See all wallet statuses
2. **Open Developer Console** (F12) - Check for error messages
3. **Review debug output** - Look for transaction processing details
4. **Wait for confirmation** - Transactions usually complete quickly
5. **Restart the app** - Clear any stale state

## Summary

You now have a complete multi-wallet system with:
- ✅ Real-time pending balance tracking
- ✅ Automatic inter-wallet transfer detection
- ✅ Both sender and recipient balance updates
- ✅ Fee tracking and accounting
- ✅ Confirmation status monitoring
- ✅ Multi-wallet balance display
- ✅ Debug logging for troubleshooting

**Enjoy seamless inter-wallet transfers!** 🎉

---

Last Updated: December 23, 2025
LunaWallet v1.0 - Multi-Wallet Transfer Support

# Sequential Rewards Compression - Visual Guide

## Before and After

### Before (Cluttered Transaction List)
```
📊 Recent Transactions
├─ 12/23 15:30  Reward ✓      +1.000000 LKC
├─ 12/23 15:29  Reward ✓      +1.000000 LKC
├─ 12/23 15:28  Reward ✓      +1.000000 LKC
├─ 12/23 15:27  Reward ✓      +1.000000 LKC
├─ 12/23 15:26  Reward ✓      +1.000000 LKC
├─ 12/23 15:25  Reward ✓      +1.000000 LKC
├─ 12/23 15:24  Reward ✓      +1.000000 LKC
├─ 12/23 15:23  Reward ✓      +1.000000 LKC
├─ 12/23 15:22  Reward ✓      +1.000000 LKC
├─ 12/23 15:21  Reward ✓      +1.000000 LKC
├─ 12/23 15:20  Reward ✓      +1.000000 LKC
├─ 12/23 15:19  Reward ✓      +1.000000 LKC
├─ 12/23 15:18  Reward ✓      +1.000000 LKC
├─ 12/23 16:00  Transfer ✓    -50.000000 LKC
└─ 12/23 12:00  Transfer ✓    +100.000000 LKC
```
**Result**: 13 identical entries make it hard to see actual transfers

### After (Clean Transaction List)
```
📊 Recent Transactions
├─ 12/23 15:30  Rewards (13x) ✓  +1.000000 LKC × 13
├─ 12/23 16:00  Transfer ✓       -50.000000 LKC
└─ 12/23 12:00  Transfer ✓       +100.000000 LKC
```
**Result**: Much cleaner! 13 rewards in 1 entry, easy to find transfers

## Transaction Tab - Desktop Table

### Before
```
┌─────────────────────────────────────────────────────────────────┐
│ Date        │ Type    │ Direction              │ Amount          │
├─────────────────────────────────────────────────────────────────┤
│ 12/23 15:30 │ 💰 reward │ ← Mining Reward       │ 1.000000 LKC   │
│ 12/23 15:29 │ 💰 reward │ ← Mining Reward       │ 1.000000 LKC   │
│ 12/23 15:28 │ 💰 reward │ ← Mining Reward       │ 1.000000 LKC   │
│ 12/23 15:27 │ 💰 reward │ ← Mining Reward       │ 1.000000 LKC   │
│ ... 9 more reward entries ...                                    │
│ 12/23 16:00 │ 🔄 transfer │ → To: LUN_abc...   │ 50.000000 LKC  │
└─────────────────────────────────────────────────────────────────┘
```

### After
```
┌────────────────────────────────────────────────────────────────────┐
│ Date        │ Type    │ Direction                  │ Amount         │
├────────────────────────────────────────────────────────────────────┤
│ 12/23 15:30 │ 💰 reward │ ← Mining Rewards (×13) │ 1.000000 × 13 │
│ 12/23 16:00 │ 🔄 transfer │ → To: LUN_abc...    │ 50.000000 LKC  │
└────────────────────────────────────────────────────────────────────┘
```

## Transaction Tab - Mobile Cards

### Before (13 Cards)
```
┌──────────────────────────┐
│ +1.000000 LKC  ✅        │
│ 🎁 Mining Reward         │
│ 12/23 15:30              │
└──────────────────────────┘
┌──────────────────────────┐
│ +1.000000 LKC  ✅        │
│ 🎁 Mining Reward         │
│ 12/23 15:29              │
└──────────────────────────┘
┌──────────────────────────┐
│ +1.000000 LKC  ✅        │
│ 🎁 Mining Reward         │
│ 12/23 15:28              │
└──────────────────────────┘
... (10 more cards)
```

### After (1 Compressed Card)
```
┌──────────────────────────────────┐
│ +1.000000 LKC × 13  ✅           │
│ 🎁 Mining Rewards (×13)          │
│ 12/23 15:30                      │
└──────────────────────────────────┘
```

## Compression Rules

### ✅ Compressed (Consecutive)
```
Reward 1: 1 LKC, timestamp 15:30
Reward 2: 1 LKC, timestamp 15:29
Reward 3: 1 LKC, timestamp 15:28
            ↓
    Display as: 1 LKC × 3
```

### ❌ Not Compressed (Different Amounts)
```
Reward 1: 1 LKC, timestamp 15:30
Reward 2: 1 LKC, timestamp 15:29
Reward 3: 0.5 LKC, timestamp 15:28  ← Different amount
            ↓
    Reward 1 & 2 compressed: 1 LKC × 2
    Reward 3 separate: 0.5 LKC × 1
```

### ❌ Not Compressed (Different Address)
```
Reward 1: 1 LKC to LUN_addr1, timestamp 15:30
Reward 2: 1 LKC to LUN_addr1, timestamp 15:29
Reward 3: 1 LKC to LUN_addr2, timestamp 15:28  ← Different address
            ↓
    Rewards 1 & 2 compressed: 1 LKC × 2
    Reward 3 separate: 1 LKC × 1
```

### ❌ Not Compressed (Other Transaction Type)
```
Reward 1: 1 LKC, timestamp 15:30
Reward 2: 1 LKC, timestamp 15:29
Transfer: 50 LKC, timestamp 15:28  ← Not a reward
Reward 3: 1 LKC, timestamp 15:27
            ↓
    Rewards 1 & 2 compressed: 1 LKC × 2
    Transfer: 50 LKC × 1
    Reward 3 separate: 1 LKC × 1
```

## Display Examples

### Example 1: 13 Identical 1 LKC Rewards
```
Entry:   Rewards (13x) → LUN_BzFRaY...
Amount:  +1.000000 LKC × 13 (13 consecutive mining rewards)
Date:    12/23 15:30 (timestamp of first reward)
Status:  ✓ Confirmed
```

### Example 2: 5 Rewards of 2.5 LKC Each
```
Entry:   Rewards (5x) → LUN_abc...
Amount:  +2.500000 LKC × 5 (5 consecutive mining rewards)
Date:    12/23 14:15
Status:  ✓ Confirmed
```

### Example 3: Mixed 2 and 3 Reward Groups
```
Entry 1: Rewards (2x) → LUN_abc...
Amount:  +1.000000 LKC × 2
Date:    12/23 15:30

Entry 2: Transfer
Amount:  -50.000000 LKC
Date:    12/23 14:00

Entry 3: Rewards (3x) → LUN_xyz...
Amount:  +1.000000 LKC × 3
Date:    12/23 13:30
```

## Interaction Features

### Clicking Compressed Entry
```
User clicks: "Rewards (13x) → LUN_abc..."
             ↓
System shows:
  - Total amount: 13 LKC
  - Individual rewards:
    * 1 LKC @ 15:30
    * 1 LKC @ 15:29
    * 1 LKC @ 15:28
    ... (all 13 listed)
```

### Details View
When viewing transaction details:
- Shows that it's a compressed entry
- Lists all original transactions
- Shows timestamp range
- Shows total combined amount

## Color Coding

### Amount Colors
- **Green (#00ff00)**: Incoming (rewards, transfers to you)
- **Red (#ff4444)**: Outgoing (transfers from you)

### Compressed Rewards
- Always show in **Green** (they're incoming)
- Indicator: 💰 or 🎁 icon
- Status: ✅ Confirmed or ⏳ Pending

## Smart Compression Logic

```
Algorithm:
  1. Start with first transaction
  2. If it's a reward:
     a. Look ahead for identical rewards
     b. Count consecutive matches
     c. If count > 1:
        - Create compressed entry
        - Store original transactions
        - Mark as _is_compressed = True
     d. Skip ahead past compressed rewards
  3. If not a reward or not consecutive:
     - Keep as individual entry
  4. Display result
```

## Performance

- **Time**: O(n) - single pass through transactions
- **Memory**: Minimal - reuses original transaction data
- **Impact**: Negligible - happens at display time, not storage
- **Result**: Faster scrolling with 13 rewards shown as 1 entry

## Summary

Sequential mining reward transactions are automatically compressed for cleaner UI:

| Metric | Before | After |
|--------|--------|-------|
| Visual Entries | 13 | 1 |
| Screen Clutter | High | Low |
| Scrollable Content | Large | Small |
| Data Accuracy | Same | Same |
| User Experience | Cluttered | Clean |

**Result**: Better readability while maintaining complete transaction history! ✨

# Expandable Compressed Rewards - Feature Documentation

## Overview

Compressed reward transactions can now be clicked/tapped to expand and show all individual rewards. Additionally, compressed reward entries do NOT link to a transaction details page (unlike regular transactions).

## What Changed

### Before
- Compressed rewards showed: "Rewards (13x) +1.000000 LKC × 13"
- Clicking would open transaction details (wrong behavior for compressed)
- No way to see individual rewards

### After
- Compressed rewards show with expand/collapse icon: ▼
- Clicking/tapping toggles expansion to show individual rewards
- Does NOT link to transaction details page
- Icon changes from ▼ (expanded) to ▶ (collapsed)

## User Experience

### Page Wallet - Recent Transactions

**Collapsed View:**
```
💰 +1.000000 LKC × 13  ✓        ▼
   12/23 15:30  Rewards (13x) → LUN_abc...
```

**Expanded View:**
```
💰 +1.000000 LKC × 13  ✓        ▲
   12/23 15:30  Rewards (13x) → LUN_abc...
   ─────────────────────────────────────
   💰 +1.000000 LKC     12/23 15:30
   💰 +1.000000 LKC     12/23 15:29
   💰 +1.000000 LKC     12/23 15:28
   ... (10 more)
```

### Transactions Tab - Mobile View

**Collapsed Card:**
```
┌─────────────────────────────┐
│ +1.000000 LKC × 13    ✅    │
│ 🎁 Mining Rewards (×13)  ▼  │
│ 12/23 15:30                 │
└─────────────────────────────┘
```

**Expanded Card:**
```
┌─────────────────────────────┐
│ +1.000000 LKC × 13    ✅    │
│ 🎁 Mining Rewards (×13)  ▲  │
│ 12/23 15:30                 │
├─────────────────────────────┤
│ 💰 +1.000000 LKC  12/23 15:30
│ 💰 +1.000000 LKC  12/23 15:29
│ 💰 +1.000000 LKC  12/23 15:28
│ ... (more rewards)
└─────────────────────────────┘
```

## Implementation

### Files Modified

1. **gui/page_wallet.py**
   - Updated `_create_transaction_item()` method for compressed rewards
   - Added expandable Column component with stored references
   - Created `toggle_expand()` function to handle expansion
   - Icon changes: EXPAND_MORE (▼) ↔ EXPAND_LESS (▲)

2. **gui/tab_transactions.py**
   - Updated mobile transaction card display for compressed rewards
   - Created `create_toggle_handler()` factory function
   - Uses GestureDetector for tap/click handling
   - Icon changes on expand/collapse

### Key Features

✅ **Click/Tap to Expand**
- Page Wallet: Click on the ListTile
- Mobile: Tap the card header
- Icon rotates to indicate state

✅ **No Transaction Details Link**
- Compressed rewards don't navigate to details page
- Regular transactions still link normally

✅ **Animated Expansion**
- Icon rotates to show expand/collapse state
- Individual rewards appear below main entry
- Smooth visual feedback

✅ **Individual Reward Display**
- Shows each original reward amount
- Shows individual timestamps
- Uses same formatting as regular rewards
- Green color for incoming

## Technical Details

### Page Wallet Implementation

```python
def toggle_expand(e):
    # Toggle expansion state
    expanded_state['is_expanded'] = not expanded_state['is_expanded']
    
    # Update icon
    expand_icon.current.name = (ft.Icons.EXPAND_LESS if expanded_state['is_expanded'] 
                                else ft.Icons.EXPAND_MORE)
    
    # Update content
    if expanded_state['is_expanded']:
        # Add individual reward items
    else:
        # Clear expansion content
```

**UI Structure:**
```
Container
  └─ Column
      ├─ ListTile
      │  ├─ leading: Icon(ATTACH_MONEY)
      │  ├─ title: Row(amount, status)
      │  ├─ subtitle: Row(date, description)
      │  ├─ trailing: Icon(EXPAND_MORE/LESS) ← Changes on toggle
      │  └─ on_click: toggle_expand
      └─ Column(ref=expansion_container)  ← Populated on expand
         ├─ Divider
         ├─ Reward Item 1
         ├─ Reward Item 2
         └─ ...
```

### Mobile Implementation

Uses `GestureDetector` with `on_tap` handler for better mobile responsiveness:

```python
def create_toggle_handler(expanded_dict, exp_col_ref, exp_icon_ref, orig_txs):
    def toggle_expand(e):
        # Same expansion logic as Page Wallet
        # But with mobile-optimized layout
    return toggle_expand

GestureDetector(
    content=Container(header_content),
    on_tap=create_toggle_handler(...)  ← Tap to expand
)
```

## User Interactions

### Desktop (Page Wallet)
```
User clicks on compressed reward entry
         ↓
toggle_expand() called
         ↓
Icon changes to EXPAND_LESS
         ↓
Individual rewards appear below
         ↓
User clicks again (or clicks other entry)
         ↓
Collapses and hides individual rewards
```

### Mobile (Transactions Tab)
```
User taps compressed reward card
         ↓
on_tap handler called (GestureDetector)
         ↓
Icon rotates/changes
         ↓
Individual rewards expand below card header
         ↓
User taps card again or another card
         ↓
Collapses back to summary
```

## Display Details

### Expanded Individual Rewards

**Page Wallet:**
```
Container (margin: 5px)
  └─ ListTile
      ├─ leading: Icon(ATTACH_MONEY, #00ff00)
      ├─ title: "+1.000000 LKC" (#00ff00, bold, 12pt)
      └─ subtitle: "12/23 15:30" (#888888, 10pt)
```

**Mobile:**
```
Row (padding: 10px, margin: 5px, bgcolor: #1a0f0f)
  ├─ Icon(ATTACH_MONEY, #00ff00, 14pt)
  ├─ Text("+1.000000 LKC", #00ff00, 11pt, bold)
  └─ Text("12/23 15:30", #888888, 10pt)
```

## Styling

### Colors & Icons
- **Green (#00ff00)**: Reward amounts (incoming)
- **Blue (#a8a8a8)**: Timestamps and secondary info
- **Icon EXPAND_MORE**: Collapsed state (▼)
- **Icon EXPAND_LESS**: Expanded state (▲)

### Layout
- Main entry maintains full width
- Divider separates main from expanded
- Individual items indented/offset for hierarchy
- Compact display to save vertical space

## State Management

### State Tracking
```python
expanded_state = {'is_expanded': False}  # Tracks expansion state per entry
```

Uses dictionary for mutable state in lambda/closure context.

### UI References
```python
expansion_container = ft.Ref[ft.Column]()  # Reference to expansion content
expand_icon = ft.Ref[ft.Icon]()            # Reference to icon for rotation
```

Refs allow updating specific UI elements without rebuilding entire transaction list.

## No Click Navigation

### Removed
```python
# OLD (compressed rewards):
on_click=lambda e, tx=tx_data: self._show_transaction_details(tx)
```

### New
```python
# NEW (compressed rewards):
on_click=toggle_expand  # Only expands/collapses, doesn't navigate
```

Regular (non-compressed) transactions still have `on_click=lambda e, tx=tx_data: self._show_transaction_details(tx)` and will navigate to details page when clicked.

## Benefits

✅ **Better Organization**: See all rewards without separate page
✅ **User Control**: Expand only when interested
✅ **Clean UI**: Collapsed view stays minimal
✅ **Mobile Friendly**: Tap to expand, gesture-based
✅ **No Confusion**: Not clickable to wrong page
✅ **Preserves Data**: All individual timestamps visible when expanded
✅ **Visual Feedback**: Icon indicates state

## Future Enhancements

1. **Persistent State**: Remember expanded state across views
2. **Animation**: Smooth slide-down animation on expand
3. **Export**: Include all expanded details in export
4. **Search**: Make individual expanded rewards searchable
5. **Other Types**: Extend to other transaction types (transfers, fees)

## Summary

Compressed reward transactions now provide an intuitive expand/collapse interface showing all individual rewards without cluttering the main transaction list. They are NOT linked to transaction details (unlike regular transactions), keeping the behavior appropriate for compressed summary entries.

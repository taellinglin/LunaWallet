import flet as ft
from gui.icon_utils import feather_icon
from datetime import datetime
from typing import List, Dict
import time
from utils import format_amount, format_amount_with_unit

class TabTransactions:
    def __init__(self, wallet_core, is_mobile=False):
        self.wallet_core = wallet_core
        self.is_mobile = is_mobile
        self.refs = {}
    
    def _compress_sequential_rewards(self, transactions):
        """
        Compress sequential reward transactions of the same amount into a single entry.
        E.g., 13 consecutive 1 LKC rewards become one entry showing "1 LKC x 13"
        
        Args:
            transactions: List of transaction dicts
            
        Returns:
            Compressed list of transactions
        """
        if not transactions:
            return transactions
        
        compressed = []
        i = 0
        
        while i < len(transactions):
            tx = transactions[i]
            
            # Only compress reward transactions
            if tx.get('type') != 'reward':
                compressed.append(tx)
                i += 1
                continue
            
            # Count consecutive rewards with same amount
            amount = tx.get('amount', 0)
            count = 1
            j = i + 1
            
            # Look ahead for same amount rewards
            while j < len(transactions):
                next_tx = transactions[j]
                if (next_tx.get('type') == 'reward' and 
                    next_tx.get('amount') == amount and
                    next_tx.get('reward_address') == tx.get('reward_address')):
                    count += 1
                    j += 1
                else:
                    break
            
            # If multiple consecutive rewards, compress them
            if count > 1:
                # Create compressed transaction entry
                compressed_tx = tx.copy()
                compressed_tx['_is_compressed'] = True
                compressed_tx['_original_count'] = count
                compressed_tx['_original_transactions'] = transactions[i:i+count]
                # Use the timestamp of the first reward
                compressed_tx['timestamp'] = tx.get('timestamp', time.time())
                compressed.append(compressed_tx)
                i += count
            else:
                compressed.append(tx)
                i += 1
        
        return compressed
        
    def create_tab_content(self):
        if self.is_mobile:
            return self.create_mobile_content()
        else:
            return self.create_desktop_content()
    
    def create_mobile_content(self):
        self.refs['mobile_transactions_list'] = ft.Ref[ft.ListView]()
        
        return ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Text("Transactions", size=24, color="#f8d7da", weight="bold"),
                    ft.IconButton(
                        icon=ft.Icons.REFRESH,
                        on_click=lambda _: self.update_transaction_history(),
                        icon_color="#dc3545",
                        icon_size=30
                    )
                ]),
                ft.Container(
                    content=ft.ListView(
                        ref=self.refs['mobile_transactions_list'],
                        expand=True,
                        spacing=10,
                        padding=10
                    ),
                    expand=True,
                    border=ft.border.all(2, "#5c2e2e"),
                    border_radius=10,
                    bgcolor="#1a0f0f"
                )
            ], expand=True),
            padding=20,
            bgcolor="#2c1a1a",
            expand=True
        )
    
    def create_desktop_content(self):
        self.refs['transactions_table'] = ft.Ref[ft.DataTable]()
        data_table = ft.DataTable(
            ref=self.refs['transactions_table'],
            columns=[
                ft.DataColumn(ft.Text("Date", color="#f8d7da", size=14)),
                ft.DataColumn(ft.Text("Type", color="#f8d7da", size=14)),
                ft.DataColumn(ft.Text("From/To", color="#f8d7da", size=14)),
                ft.DataColumn(ft.Text("Amount", color="#f8d7da", size=14)),
                ft.DataColumn(ft.Text("Status", color="#f8d7da", size=14)),
                ft.DataColumn(ft.Text("Memo", color="#f8d7da", size=14)),
            ],
            rows=[],
            vertical_lines=ft.BorderSide(2, "#5c2e2e"),
            horizontal_lines=ft.BorderSide(2, "#5c2e2e"),
            bgcolor="#1a0f0f",
        )
        
        return ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Text("Transaction History", size=20, color="#f8d7da"),
                    ft.IconButton(
                        icon=ft.Icons.REFRESH,
                        on_click=lambda _: self.update_transaction_history(),
                        icon_color="#dc3545",
                        icon_size=24
                    )
                ]),
                ft.Container(
                    content=ft.ListView([data_table], expand=True),
                    expand=True,
                    border=ft.border.all(2, "#5c2e2e"),
                    border_radius=10
                )
            ], expand=True),
            padding=15,
            bgcolor="#2c1a1a"
        )
    
    def update_transaction_history(self):
        if not self.wallet_core.is_unlocked:
            return
            
        transactions = self.wallet_core.get_transaction_history()
        
        # Compress sequential reward transactions
        transactions = self._compress_sequential_rewards(transactions)
        
        # Update desktop table
        if 'transactions_table' in self.refs and self.refs['transactions_table'].current:
            table = self.refs['transactions_table'].current
            table.rows = []
            
            for tx in transactions[:50]:
                date_str = datetime.fromtimestamp(tx.get('timestamp', 0)).strftime("%Y-%m-%d %H:%M")
                tx_type = tx.get('type', 'transfer')
                
                # Handle compressed rewards
                is_compressed = tx.get('_is_compressed', False)
                if is_compressed:
                    original_count = tx.get('_original_count', 1)
                    amount = tx.get('amount', 0)
                    type_icon_name = "award"
                    direction = f"← Mining Rewards (×{original_count})"
                    amount_text = f"{format_amount_with_unit(amount)} × {original_count}"
                else:
                    type_icon_name = "award" if tx_type == "reward" else "repeat"
                    from_addr = tx.get('from', 'Network')
                    to_addr = tx.get('to', 'Unknown')
                    
                    is_incoming = False
                    if tx_type == "reward":
                        is_incoming = True
                        direction = f"← Mining Reward"
                    else:
                        our_addresses = [w['address'].lower() for w in self.wallet_core.wallets]
                        if to_addr and to_addr.lower() in our_addresses:
                            is_incoming = True
                            direction = f"← From: {from_addr}"
                        else:
                            direction = f"→ To: {to_addr}"
                    
                    amount = tx.get('amount', 0)
                    amount_text = format_amount_with_unit(amount)
                
                amount_color = "#00ff00" if (is_compressed or tx.get('type') == 'reward' or 
                                              (not is_compressed and to_addr.lower() in [w['address'].lower() for w in self.wallet_core.wallets])) else "#ff0000"
                status = tx.get('status', 'unknown')
                status_icon_name = "check-circle" if status == "confirmed" else "clock" if status == "pending" else "x-circle"
                memo = tx.get('memo', '')
                
                table.rows.append(
                    ft.DataRow(cells=[
                        ft.DataCell(ft.Text(date_str, size=12, color="#f8d7da")),
                        ft.DataCell(
                            ft.Row(
                                [
                                    feather_icon(type_icon_name, size=14, color="#f8d7da"),
                                    ft.Text(tx_type, size=12, color="#f8d7da"),
                                ],
                                spacing=6,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            )
                        ),
                        ft.DataCell(ft.Text(direction, size=12, color="#f8d7da")),
                        ft.DataCell(ft.Text(amount_text, size=12, color=amount_color)),
                        ft.DataCell(
                            ft.Row(
                                [
                                    feather_icon(status_icon_name, size=14, color="#f8d7da"),
                                    ft.Text(status, size=12, color="#f8d7da"),
                                ],
                                spacing=6,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            )
                        ),
                        ft.DataCell(ft.Text(memo, size=12, color="#f8d7da")),
                    ])
                )
                
            table.update()
        
        # Update mobile list with enhanced cards
        if 'mobile_transactions_list' in self.refs and self.refs['mobile_transactions_list'].current:
            mobile_list = self.refs['mobile_transactions_list'].current
            mobile_list.controls.clear()
            
            for tx in transactions[:50]:  # Show more transactions on mobile
                date_str = datetime.fromtimestamp(tx.get('timestamp', 0)).strftime("%m/%d %H:%M")
                tx_type = tx.get('type', 'transfer')
                
                # Handle compressed rewards
                is_compressed = tx.get('_is_compressed', False)
                original_count = tx.get('_original_count', 1)
                amount = tx.get('amount', 0)
                original_transactions = tx.get('_original_transactions', [])
                
                if is_compressed:
                    # Compressed reward transaction - create expandable card
                    expanded_state = {'is_expanded': False}
                    expansion_column = ft.Ref[ft.Column]()
                    expand_icon = ft.Ref[ft.Icon]()
                    
                    def create_toggle_handler(expanded_dict, exp_col_ref, exp_icon_ref, orig_txs):
                        def toggle_expand(e):
                            expanded_dict['is_expanded'] = not expanded_dict['is_expanded']
                            
                            # Update icon
                            if exp_icon_ref.current:
                                exp_icon_ref.current.name = (ft.Icons.EXPAND_LESS if expanded_dict['is_expanded'] 
                                                            else ft.Icons.EXPAND_MORE)
                                exp_icon_ref.current.update()
                            
                            # Update expanded content
                            if exp_col_ref.current:
                                exp_col_ref.current.controls.clear()
                                
                                if expanded_dict['is_expanded']:
                                    # Show individual rewards
                                    for i, orig_tx in enumerate(orig_txs, 1):
                                        orig_timestamp = orig_tx.get('timestamp', time.time())
                                        try:
                                            orig_date_str = datetime.fromtimestamp(orig_timestamp).strftime("%m/%d %H:%M")
                                        except:
                                            orig_date_str = "Unknown"
                                        
                                        reward_item = ft.Container(
                                            content=ft.Row([
                                                ft.Icon(ft.Icons.ATTACH_MONEY, color="#00ff00", size=14),
                                                ft.Text(format_amount_with_unit(orig_tx.get('amount', 0)), 
                                                    color="#00ff00", size=11, expand=True),
                                                ft.Row(
                                                    [
                                                        ft.Icon(
                                                            ft.Icons.CHECK_CIRCLE if orig_tx.get('status', 'unknown') == 'confirmed'
                                                            else ft.Icons.SCHEDULE if orig_tx.get('status', 'unknown') == 'pending'
                                                            else ft.Icons.HELP_OUTLINE,
                                                            color="#00ff00" if orig_tx.get('status', 'unknown') == 'confirmed'
                                                            else "#ffa500" if orig_tx.get('status', 'unknown') == 'pending'
                                                            else "#a8a8a8",
                                                            size=12,
                                                        ),
                                                        ft.Text(
                                                            orig_tx.get('status', 'unknown'),
                                                            size=10,
                                                            color="#00ff00" if orig_tx.get('status', 'unknown') == 'confirmed'
                                                            else "#ffa500" if orig_tx.get('status', 'unknown') == 'pending'
                                                            else "#a8a8a8",
                                                        ),
                                                    ],
                                                    spacing=4,
                                                ),
                                                ft.Text(orig_date_str, size=10, color="#888888"),
                                            ]),
                                            padding=10,
                                            margin=ft.margin.symmetric(vertical=2, horizontal=5),
                                            bgcolor="#1a0f0f",
                                            border_radius=6,
                                        )
                                        exp_col_ref.current.controls.append(reward_item)
                                
                                exp_col_ref.current.update()
                        return toggle_expand
                    
                    # Create expandable card for compressed rewards
                    transaction_card = ft.Container(
                        content=ft.Column([
                            # Header - clickable to expand
                            ft.GestureDetector(
                                content=ft.Container(
                                    content=ft.Row([
                                        ft.Icon(ft.Icons.ACCOUNT_BALANCE_WALLET, color="#00ff00", size=20),
                                        ft.Column([
                                            ft.Text(
                                                f"{format_amount_with_unit(amount)} × {original_count}",
                                                size=16,
                                                color="#00ff00",
                                                weight="bold",
                                            ),
                                            ft.Text(
                                                f"Mining Rewards (×{original_count})",
                                                size=12,
                                                color="#f8d7da",
                                            ),
                                        ], expand=True),
                                        ft.Column([
                                            ft.Icon(
                                                ft.Icons.EXPAND_MORE,
                                                color="#a8a8a8",
                                                size=20,
                                                ref=expand_icon
                                            ),
                                            ft.Text(date_str, size=10, color="#a8a8a8"),
                                        ]),
                                    ], spacing=10),
                                    padding=10,
                                ),
                                on_tap=create_toggle_handler(expanded_state, expansion_column, expand_icon, original_transactions),
                            ),
                            # Expanded individual rewards
                            ft.Column([], ref=expansion_column, spacing=0),
                        ], spacing=0),
                        
                        bgcolor="#2c1a1a",
                        padding=5,
                        border=ft.border.all(1, "#5c2e2e"),
                        border_radius=12,
                        margin=ft.margin.symmetric(vertical=2)
                    )
                    
                    mobile_list.controls.append(transaction_card)
                else:
                    # Regular transaction card
                    is_incoming = False
                    if tx_type == "reward":
                        is_incoming = True
                        direction_text = "Mining Reward"
                        icon = ft.Icons.ACCOUNT_BALANCE_WALLET
                    else:
                        our_addresses = [w['address'].lower() for w in self.wallet_core.wallets]
                        to_addr = tx.get('to', '')
                        if any(to_addr.lower() == w.lower() for w in our_addresses if to_addr):
                            is_incoming = True
                            direction_text = f"From: {tx.get('from', 'Unknown')[:12]}..."
                            icon = ft.Icons.ARROW_DOWNWARD
                        else:
                            direction_text = f"To: {tx.get('to', 'Unknown')[:12]}..."
                            icon = ft.Icons.ARROW_UPWARD
                    
                    amount_text = format_amount_with_unit(abs(amount))
                    amount_color = "#00ff00" if is_incoming else "#ff0000"
                    status = tx.get('status', 'unknown')
                    
                    # Status styling
                    if status == "confirmed":
                        status_color = "#00ff00"
                        status_icon = ft.Icons.CHECK_CIRCLE
                    elif status == "pending":
                        status_color = "#ffa500"
                        status_icon = ft.Icons.SCHEDULE
                    else:
                        status_color = "#ff4444"
                        status_icon = ft.Icons.ERROR
                    
                    # Create transaction card
                    transaction_card = ft.Container(
                        content=ft.Column([
                            # First row: Amount and Status
                            ft.Row([
                                ft.Text(
                                    amount_text,
                                    size=18,
                                    color=amount_color,
                                    weight="bold",
                                    expand=True
                                ),
                                ft.Icon(
                                    status_icon,
                                    color=status_color,
                                    size=20
                                ),
                                ft.Text(
                                    status.upper(),
                                    size=12,
                                    color=status_color,
                                    weight="bold"
                                )
                            ]),
                            
                            # Second row: Direction and Date
                            ft.Row([
                                ft.Icon(
                                    icon,
                                    color=amount_color,
                                    size=16
                                ),
                                ft.Text(
                                    direction_text,
                                    size=14,
                                    color="#f8d7da",
                                    expand=True
                                ),
                                ft.Text(
                                    date_str,
                                    size=12,
                                    color="#a8a8a8"
                                )
                            ]),
                            
                            # Third row: Type and Memo (if available)
                            ft.Row([
                                ft.Container(
                                    content=ft.Text(
                                        tx_type.upper(),
                                        size=10,
                                        color="#f8d7da",
                                        weight="bold"
                                    ),
                                    bgcolor="#5c2e2e",
                                    padding=ft.padding.symmetric(horizontal=8, vertical=4),
                                    border_radius=8
                                ),
                                ft.Text(
                                    tx.get('memo', ''),
                                    size=12,
                                    color="#a8a8a8",
                                    expand=True,
                                    max_lines=1,
                                    overflow="ellipsis"
                                ) if tx.get('memo') else ft.Container()
                            ])
                        ], spacing=8),
                        
                        # Card styling
                        bgcolor="#2c1a1a",
                        padding=15,
                        border=ft.border.all(1, "#5c2e2e"),
                        border_radius=12,
                        margin=ft.margin.symmetric(vertical=2)
                    )
                    
                    mobile_list.controls.append(transaction_card)
            
            # Add empty state if no transactions
            if not transactions:
                mobile_list.controls.append(
                    ft.Container(
                        content=ft.Column([
                            ft.Icon(ft.Icons.RECEIPT_LONG, size=48, color="#5c2e2e"),
                            ft.Text("No transactions yet", size=16, color="#f8d7da"),
                            ft.Text("Your transaction history will appear here", size=12, color="#a8a8a8"),
                        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=10),
                        padding=40,
                        alignment=ft.Alignment(0, 0)
                    )
                )
            
            mobile_list.update()
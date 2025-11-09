import flet as ft
from datetime import datetime
from typing import List, Dict

class TransactionsTab:
    def __init__(self, wallet_core, is_mobile=False):
        self.wallet_core = wallet_core
        self.is_mobile = is_mobile
        self.refs = {}
        
    def create_tab_content(self):
        if self.is_mobile:
            return self.create_mobile_content()
        else:
            return self.create_desktop_content()
    
    def create_mobile_content(self):
        self.refs['mobile_transactions_list'] = ft.Ref[ft.Column]()
        transactions_list = ft.Column([], ref=self.refs['mobile_transactions_list'])
        
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
                    content=ft.ListView([transactions_list], expand=True),
                    expand=True,
                    border=ft.border.all(2, "#5c2e2e"),
                    border_radius=10
                )
            ], expand=True),
            padding=20,
            bgcolor="#2c1a1a"
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
        
        # Update desktop table
        if 'transactions_table' in self.refs and self.refs['transactions_table'].current:
            table = self.refs['transactions_table'].current
            table.rows = []
            
            for tx in transactions[:50]:
                date_str = datetime.fromtimestamp(tx.get('timestamp', 0)).strftime("%Y-%m-%d %H:%M")
                tx_type = tx.get('type', 'transfer')
                type_icon = "💰" if tx_type == "reward" else "🔄"
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
                amount_color = "#00ff00" if is_incoming else "#ff0000"
                status = tx.get('status', 'unknown')
                status_icon = "✅" if status == "confirmed" else "⏳" if status == "pending" else "❌"
                memo = tx.get('memo', '')
                
                table.rows.append(
                    ft.DataRow(cells=[
                        ft.DataCell(ft.Text(date_str, size=12, color="#f8d7da")),
                        ft.DataCell(ft.Text(f"{type_icon} {tx_type}", size=12, color="#f8d7da")),
                        ft.DataCell(ft.Text(direction, size=12, color="#f8d7da")),
                        ft.DataCell(ft.Text(f"{amount:.6f} LUN", size=12, color=amount_color)),
                        ft.DataCell(ft.Text(f"{status_icon} {status}", size=12, color="#f8d7da")),
                        ft.DataCell(ft.Text(memo, size=12, color="#f8d7da")),
                    ])
                )
                
            table.update()
        
        # Update mobile list
        if 'mobile_transactions_list' in self.refs and self.refs['mobile_transactions_list'].current:
            mobile_list = self.refs['mobile_transactions_list'].current
            mobile_list.controls.clear()
            
            for tx in transactions[:20]:
                date_str = datetime.fromtimestamp(tx.get('timestamp', 0)).strftime("%m/%d %H:%M")
                tx_type = tx.get('type', 'transfer')
                type_icon = "💰" if tx_type == "reward" else "🔄"
                
                is_incoming = tx_type == "reward" or any(
                    w['address'].lower() == tx.get('to', '').lower() 
                    for w in self.wallet_core.wallets
                )
                
                amount = tx.get('amount', 0)
                amount_color = "#00ff00" if is_incoming else "#ff0000"
                status = tx.get('status', 'unknown')
                status_icon = "✅" if status == "confirmed" else "⏳" if status == "pending" else "❌"
                
                mobile_list.controls.append(
                    ft.ListTile(
                        leading=ft.Icon(
                            ft.Icons.ARROW_UPWARD if not is_incoming else ft.Icons.ARROW_DOWNWARD,
                            color=amount_color,
                            size=30
                        ),
                        title=ft.Text(f"{amount:.6f} LUN", color=amount_color, size=16),
                        subtitle=ft.Text(f"{date_str} • {status_icon} {status}", color="#f8d7da", size=14),
                        trailing=ft.Text(type_icon, size=20),
                    )
                )
            
            mobile_list.update()
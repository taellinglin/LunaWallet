import flet as ft
import threading
from datetime import datetime

class WalletPage:
    def __init__(self, app, on_send, on_receive, on_export_key, on_lock, on_create_wallet, on_import_wallet):
        self.app = app
        self.on_send = on_send
        self.on_receive = on_receive
        self.on_export_key = on_export_key
        self.on_lock = on_lock
        self.on_create_wallet = on_create_wallet
        self.on_import_wallet = on_import_wallet
        
        # UI elements
        self.balance_text = ft.Text("0.00", size=32, weight="bold", color="#ffffff")
        self.address_text = ft.Text("", size=14, color="#f8d7da")
        self.sync_status = ft.Text("Syncing...", size=12, color="#ffd700")
        self.blockchain_stats = ft.Column()
        
        # Preloader state
        self.is_loading = True
        self.preloader = self.create_preloader()
        self.main_content = self.create_main_content()
        
    def create(self):
        # Return a Stack with preloader and main content
        return ft.Container(
            content=ft.Stack([
                self.main_content,
                self.preloader
            ]),
            expand=True,
            bgcolor="#2c1a1a"
        )
    
    def create_preloader(self):
        return ft.Container(
            content=ft.Column([
                ft.Container(expand=True),
                ft.ProgressRing(width=50, height=50, color="#dc3545"),
                ft.Text("Loading wallet data...", color="#f8d7da", size=16),
                ft.Container(expand=True),
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            expand=True,
            bgcolor="#2c1a1a",
            visible=self.is_loading
        )
    
    def create_main_content(self):
        return ft.Container(
            content=ft.Column([
                self.create_header(),
                ft.ResponsiveRow([
                    # Stats panels - will be sidebar in landscape, top in portrait
                    ft.Container(
                        content=ft.Column([
                            self.create_wallet_stats_section(),
                            self.create_network_stats_section(),
                        ]),
                        col={"sm": 12, "md": 4},
                        padding=10
                    ),
                    
                    # Transaction History - will be main content in landscape, bottom in portrait
                    ft.Container(
                        content=self.create_transaction_history(),
                        col={"sm": 12, "md": 8},
                        padding=10
                    ),
                ]),
                self.create_action_buttons(),
            ]),
            expand=True,
            padding=20,
            visible=not self.is_loading
        )
    
    def create_header(self):
        return ft.Container(
            content=ft.Row([
                ft.Image(
                    src="./wallet_icon.svg",
                    width=24,
                    height=24,
                    fit=ft.ImageFit.CONTAIN,
                    error_content=ft.Icon(ft.Icons.ACCOUNT_BALANCE_WALLET, size=24, color="#f8d7da")
                ),
                ft.Text("Luna Wallet", size=14, weight="bold", color="#f8d7da"),
                ft.Container(expand=True),
                ft.Row([
                    ft.IconButton(
                        icon=ft.Icons.REFRESH,
                        icon_color="#f8d7da",
                        on_click=self.manual_sync,
                        tooltip="Sync with Blockchain"
                    ),
                    ft.Container(width=10),
                    ft.IconButton(
                        icon=ft.Icons.LOCK,
                        icon_color="#f8d7da", 
                        on_click=self.on_lock,
                        tooltip="Lock Wallet"
                    ),
                ]),
            ]),
            padding=ft.padding.only(right=20)
        )
    
    def create_wallet_stats_section(self):
        # Don't try to access wallet data here - wait until after unlock
        return ft.Container(
            content=ft.Column([
                ft.Container(
                    content=ft.Column([
                        ft.Text("Total Balance", size=14, color="#f8d7da"),
                        self.balance_text,
                        self.address_text,
                        ft.Row([self.sync_status], alignment=ft.MainAxisAlignment.CENTER)
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                    padding=15,
                    bgcolor="#1a0f0f",
                    border_radius=10,
                )
            ]),
            padding=5
        )
    
    def create_network_stats_section(self):
        # Initialize with empty stats, will update after unlock
        self.update_blockchain_stats()
        return ft.Container(
            content=ft.Column([
                ft.Container(
                    content=self.blockchain_stats,
                    padding=15,
                    bgcolor="#1a0f0f",
                    border_radius=10,
                )
            ]),
            padding=5
        )
    
    def create_action_buttons(self):
        buttons = [
            ft.ElevatedButton(
                "📤 Send",
                on_click=lambda e: self.on_send(),
                style=ft.ButtonStyle(
                    color="#ffffff",
                    bgcolor="#dc3545",
                    padding=10
                ),
                height=40
            ),
            ft.ElevatedButton(
                "📥 Receive",
                on_click=lambda e: self.on_receive(),
                style=ft.ButtonStyle(
                    color="#ffffff",
                    bgcolor="#dc3545",
                    padding=10
                ),
                height=40
            ),
            ft.ElevatedButton(
                "🔑 Export",
                on_click=lambda e: self.on_export_key(),
                style=ft.ButtonStyle(
                    color="#ffffff",
                    bgcolor="#dc3545",
                    padding=10
                ),
                height=40
            )
        ]
        
        return ft.Container(
            content=ft.ResponsiveRow([
                ft.Container(
                    content=button,
                    col={"sm": 6, "md": 4},
                    padding=5
                ) for button in buttons
            ]),
            padding=10,
            margin=ft.margin.only(top=10)
        )
    
    def update_blockchain_stats(self):
        stats = []
        
        try:
            # Only try to get stats if wallet core is available and unlocked
            if hasattr(self.app, 'wallet_core') and self.app.wallet_core and self.app.wallet_core.is_unlocked:
                height = self.app.wallet_core._get_current_blockchain_height()
                stats.append(ft.Text(f"📦 Block Height: {height}", color="#f8d7da", size=14))
                
                if self.app.wallet_core.check_network_connection():
                    stats.append(ft.Text("🟢 Network: Connected", color="#90EE90", size=14))
                else:
                    stats.append(ft.Text("🔴 Network: Disconnected", color="#FF6B6B", size=14))
                    
                wallet_count = len(self.app.wallet_core.wallets) if self.app.wallet_core.wallets else 0
                stats.append(ft.Text(f"👛 Wallets: {wallet_count}", color="#f8d7da", size=14))
                
                last_sync = "Never"
                if hasattr(self.app.wallet_core, 'scan_state'):
                    for wallet_state in self.app.wallet_core.scan_state.get('wallets', {}).values():
                        if wallet_state.get('last_scan_time'):
                            last_sync = datetime.fromtimestamp(wallet_state['last_scan_time']).strftime("%H:%M:%S")
                            break
                stats.append(ft.Text(f"🕐 Last Sync: {last_sync}", color="#f8d7da", size=14))
            else:
                stats.append(ft.Text("Please unlock wallet...", color="#f8d7da", size=14))
            
        except Exception as e:
            stats.append(ft.Text(f"❌ Error loading stats: {str(e)}", color="#FF6B6B", size=14))
        
        self.blockchain_stats.controls = stats
    
    def create_transaction_history(self):
        self.transactions_list = ft.Column()
        self.update_transaction_history()
        
        return ft.Container(
            content=ft.Column([
                ft.Text("📊 Recent Transactions", size=18, weight="bold", color="#f8d7da"),
                ft.Divider(color="#5c2e2e"),
                self.transactions_list
            ]),
            padding=15,
            margin=10,
            bgcolor="#1a0f0f", 
            border_radius=10
        )
    
    def update_transaction_history(self):
        self.transactions_list.controls.clear()
        
        # Only try to get transactions if wallet is unlocked
        if hasattr(self.app, 'wallet_core') and self.app.wallet_core and self.app.wallet_core.is_unlocked:
            transactions = self.app.wallet_core.get_transaction_history()
            
            if not transactions:
                self.transactions_list.controls.append(
                    ft.Text("No transactions found", color="#f8d7da", italic=True)
                )
                return
            
            for tx in transactions[:10]:
                tx_type = tx.get('type', 'transfer')
                amount = tx.get('amount', 0)
                address = tx.get('to') if tx_type == 'received' else tx.get('from')
                status = tx.get('status', 'confirmed')
                
                color = "#90EE90" if tx_type == 'received' else "#FF6B6B"
                icon = "📥" if tx_type == 'received' else "📤"
                
                self.transactions_list.controls.append(
                    ft.ListTile(
                        leading=ft.Text(icon, size=20),
                        title=ft.Text(f"{amount:.6f} LUNA", color="#ffffff"),
                        subtitle=ft.Text(f"{address[:16]}...", color="#f8d7da"),
                        trailing=ft.Text(status.title(), color=color),
                    )
                )
        else:
            self.transactions_list.controls.append(
                ft.Text("Please unlock wallet to view transactions", color="#f8d7da", italic=True)
            )
    
    def manual_sync(self, e=None):
        """Manual blockchain sync"""
        self.sync_status.value = "🔄 Syncing..."
        if self.app.page:
            self.app.page.update()
        
        def sync_thread():
            try:
                if hasattr(self.app, 'wallet_core') and self.app.wallet_core:
                    success = self.app.wallet_core.scan_blockchain(force_full_scan=True)
                    if success:
                        self.sync_status.value = "✅ Synced"
                        if hasattr(self.app, 'show_snackbar'):
                            self.app.show_snackbar("Blockchain sync completed", "success")
                    else:
                        self.sync_status.value = "❌ Sync Failed"
                        if hasattr(self.app, 'show_snackbar'):
                            self.app.show_snackbar("Blockchain sync failed", "error")
                        
                    # Update UI
                    self.update_blockchain_stats()
                    self.update_transaction_history()
                    
                    if self.app.page:
                        self.app.page.update()
                
            except Exception as e:
                self.sync_status.value = "❌ Sync Error"
                if hasattr(self.app, 'show_snackbar'):
                    self.app.show_snackbar(f"Sync error: {str(e)}", "error")
                if self.app.page:
                    self.app.page.update()
        
        threading.Thread(target=sync_thread, daemon=True).start()
    
    def show_loading(self):
        """Show the preloader"""
        self.is_loading = True
        self.preloader.visible = True
        self.main_content.visible = False
        if hasattr(self.app, 'page'):
            self.app.page.update()
    
    def hide_loading(self):
        """Hide the preloader and show main content - CALL THIS AFTER UNLOCK"""
        self.is_loading = False
        self.preloader.visible = False
        self.main_content.visible = True
        
        # Now that we're unlocked, update all the wallet data
        self.update_wallet_data()
        
        if hasattr(self.app, 'page'):
            self.app.page.update()
    
    def update_wallet_data(self):
        """Update all wallet data after unlock"""
        if hasattr(self.app, 'wallet_core') and self.app.wallet_core and self.app.wallet_core.is_unlocked:
            # Update balance and address
            wallet_info = self.app.wallet_core.get_wallet_info()
            if wallet_info:
                self.balance_text.value = f"{wallet_info.get('balance', 0):.2f}"
                self.address_text.value = wallet_info.get('address', 'No wallet')
            
            # Update blockchain stats and transactions
            self.update_blockchain_stats()
            self.update_transaction_history()
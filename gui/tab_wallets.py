import flet as ft
from typing import List, Dict
from utils import calculate_wallet_balances
from lunalib.core.mempool import MempoolManager

class WalletsTab:
    def __init__(self, wallet_core, is_mobile=False, selected_wallet_index=0, on_wallet_select=None, on_create_wallet=None, on_import_wallet=None, page=None):
        self.wallet_core = wallet_core
        self.is_mobile = is_mobile
        self.selected_wallet_index = selected_wallet_index
        self.on_wallet_select = on_wallet_select
        self.on_create_wallet = on_create_wallet
        self.on_import_wallet = on_import_wallet
        self.page = page
        self.refs = {}
        
    def create_tab_content(self):
        if self.is_mobile:
            return self.create_mobile_content()
        else:
            return self.create_desktop_content()
    
    def create_mobile_content(self):
        self.refs['mobile_wallets_list'] = ft.Ref[ft.Column]()
        wallets_list = ft.Column([], ref=self.refs['mobile_wallets_list'])
        
        action_buttons = ft.Column([
            ft.ElevatedButton(
                "🆕 Create New Wallet",
                on_click=self._handle_create_wallet,
                style=ft.ButtonStyle(
                    color="#ffffff",
                    bgcolor="#dc3545",
                    padding=ft.padding.symmetric(horizontal=20, vertical=15),
                    shape=ft.RoundedRectangleBorder(radius=8)
                ),
                height=55
            ),
            ft.ElevatedButton(
                "📁 Import Wallet",
                on_click=self._handle_import_wallet,
                style=ft.ButtonStyle(
                    color="#ffffff",
                    bgcolor="#dc3545",
                    padding=ft.padding.symmetric(horizontal=20, vertical=15),
                    shape=ft.RoundedRectangleBorder(radius=8)
                ),
                height=55
            ),
        ], spacing=15)
        
        return ft.Column([
            ft.Container(
                content=ft.Column([
                    ft.Text("My Wallets", size=24, weight=ft.FontWeight.BOLD, color="#ffffff"),
                    wallets_list,
                    ft.Divider(color="#444444", height=20),
                    ft.Text("Wallet Actions", size=18, weight=ft.FontWeight.BOLD, color="#ffffff"),
                    action_buttons
                ], spacing=20),
                padding=20,
                expand=True
            )
        ])
    
    def create_desktop_content(self):
        self.refs['desktop_wallets_list'] = ft.Ref[ft.Column]()
        wallets_list = ft.Column([], ref=self.refs['desktop_wallets_list'])
        
        action_buttons = ft.Column([
            ft.ElevatedButton(
                "🆕 Create New Wallet",
                on_click=self._handle_create_wallet,
                style=ft.ButtonStyle(
                    color="#ffffff",
                    bgcolor="#dc3545",
                    padding=ft.padding.symmetric(horizontal=20, vertical=15),
                    shape=ft.RoundedRectangleBorder(radius=8)
                ),
                height=55
            ),
            ft.ElevatedButton(
                "📁 Import Wallet",
                on_click=self._handle_import_wallet,
                style=ft.ButtonStyle(
                    color="#ffffff",
                    bgcolor="#dc3545",
                    padding=ft.padding.symmetric(horizontal=20, vertical=15),
                    shape=ft.RoundedRectangleBorder(radius=8)
                ),
                height=55
            ),
        ], spacing=15)
        
        return ft.Row([
            # Left panel - Wallets list
            ft.Container(
                content=ft.Column([
                    ft.Text("My Wallets", size=20, weight=ft.FontWeight.BOLD, color="#ffffff"),
                    wallets_list
                ], spacing=15),
                width=300,
                padding=20,
                bgcolor="#1e1e1e",
                border_radius=8,
                margin=ft.margin.only(right=10)
            ),
            # Right panel - Actions
            ft.Container(
                content=ft.Column([
                    ft.Text("Wallet Actions", size=20, weight=ft.FontWeight.BOLD, color="#ffffff"),
                    action_buttons
                ], spacing=20),
                padding=20,
                expand=True,
                bgcolor="#1e1e1e",
                border_radius=8,
                margin=ft.margin.only(left=10)
            )
        ])
    
    def _handle_create_wallet(self, e):
        """Handle create wallet button click"""
        if self.on_create_wallet:
            self.on_create_wallet()
        else:
            # Fallback: show a simple create wallet dialog
            self._show_create_wallet_dialog()
    
    def _handle_import_wallet(self, e):
        """Handle import wallet button click"""
        if self.on_import_wallet:
            self.on_import_wallet()
        else:
            # Fallback: show a simple import wallet dialog
            self._show_import_wallet_dialog()
    
    def _show_create_wallet_dialog(self):
        """Show a simple create wallet dialog"""
        wallet_name_field = ft.TextField(
            label="Wallet Name",
            hint_text="Enter wallet name",
            width=300
        )
        
        def create_wallet_click(e):
            wallet_name = wallet_name_field.value.strip()
            if wallet_name:
                # Create the wallet using wallet_core
                try:
                    wallet = self.wallet_core.create_wallet(wallet_name)
                    self.page.snack_bar = ft.SnackBar(
                        content=ft.Text(f"Wallet '{wallet_name}' created successfully!"),
                        bgcolor="#4CAF50"
                    )
                    self.page.snack_bar.open = True
                    self.page.close(dialog)
                    self.refresh_wallets_list()
                    self.page.update()
                except Exception as ex:
                    self.page.snack_bar = ft.SnackBar(
                        content=ft.Text(f"Error creating wallet: {str(ex)}"),
                        bgcolor="#f44336"
                    )
                    self.page.snack_bar.open = True
                    self.page.update()
        
        def close_dialog(e):
            self.page.close(dialog)
            self.page.update()
        
        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Create New Wallet"),
            content=ft.Column([
                wallet_name_field,
                ft.Text("A new wallet will be created with a generated seed phrase.", size=12, color="#888888")
            ], tight=True),
            actions=[
                ft.TextButton("Cancel", on_click=close_dialog),
                ft.TextButton("Create", on_click=create_wallet_click, style=ft.ButtonStyle(color="#dc3545")),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        
        self.page.dialog = dialog
        dialog.open = True
        self.page.update()
    
    def _show_import_wallet_dialog(self):
        """Show a simple import wallet dialog"""
        wallet_name_field = ft.TextField(
            label="Wallet Name",
            hint_text="Enter wallet name",
            width=300
        )
        
        seed_phrase_field = ft.TextField(
            label="Seed Phrase",
            hint_text="Enter your 12 or 24 word seed phrase",
            multiline=True,
            min_lines=3,
            max_lines=4,
            width=300
        )
        
        def import_wallet_click(e):
            wallet_name = wallet_name_field.value.strip()
            seed_phrase = seed_phrase_field.value.strip()
            
            if wallet_name and seed_phrase:
                try:
                    # Import the wallet using wallet_core
                    wallet = self.wallet_core.import_wallet(wallet_name, seed_phrase)
                    self.page.snack_bar = ft.SnackBar(
                        content=ft.Text(f"Wallet '{wallet_name}' imported successfully!"),
                        bgcolor="#4CAF50"
                    )
                    self.page.snack_bar.open = True
                    self.page.close(dialog)
                    self.refresh_wallets_list()
                    self.page.update()
                except Exception as ex:
                    self.page.snack_bar = ft.SnackBar(
                        content=ft.Text(f"Error importing wallet: {str(ex)}"),
                        bgcolor="#f44336"
                    )
                    self.page.snack_bar.open = True
                    self.page.update()
        
        def close_dialog(e):
            self.page.close(dialog)
            self.page.update()
        
        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Import Wallet"),
            content=ft.Column([
                wallet_name_field,
                seed_phrase_field,
                ft.Text("Enter your existing seed phrase to import your wallet.", size=12, color="#888888")
            ], tight=True, spacing=15),
            actions=[
                ft.TextButton("Cancel", on_click=close_dialog),
                ft.TextButton("Import", on_click=import_wallet_click, style=ft.ButtonStyle(color="#dc3545")),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        
        self.page.dialog = dialog
        dialog.open = True
        self.page.update()
    
    def refresh_wallets_list(self):
        """Refresh the wallets list display with cached balances"""
        wallets = self.wallet_core.get_wallets()
        
        # Update mobile list
        if 'mobile_wallets_list' in self.refs:
            mobile_list = self.refs['mobile_wallets_list'].current
            mobile_list.controls.clear()
            
            for i, wallet in enumerate(wallets):
                wallet_card = self._create_wallet_card(wallet, i)
                mobile_list.controls.append(wallet_card)
        
        # Update desktop list
        if 'desktop_wallets_list' in self.refs:
            desktop_list = self.refs['desktop_wallets_list'].current
            desktop_list.controls.clear()
            
            for i, wallet in enumerate(wallets):
                wallet_card = self._create_wallet_card(wallet, i)
                desktop_list.controls.append(wallet_card)
        
        # Refresh balances in background for all wallets
        if self.page:
            def update_balances():
                try:
                    from lunalib.storage.database import WalletDatabase
                    database = WalletDatabase()
                    mempool_manager = MempoolManager()
                    
                    for wallet in wallets:
                        wallet_address = wallet.get('address') if isinstance(wallet, dict) else str(wallet)
                        
                        # Calculate fresh balances using lunalib
                        balances = calculate_wallet_balances(
                            wallet_address,
                            database=database,
                            mempool_manager=mempool_manager
                        )
                        
                        # Store in wallet_core for caching
                        if hasattr(self.wallet_core, 'wallets') and wallet_address in self.wallet_core.wallets:
                            self.wallet_core.wallets[wallet_address]['confirmed_balance'] = balances.get('available', 0.0)
                            self.wallet_core.wallets[wallet_address]['pending_balance'] = balances.get('pending', 0.0)
                            self.wallet_core.wallets[wallet_address]['available_balance'] = balances.get('available', 0.0)
                            self.wallet_core.wallets[wallet_address]['balance'] = balances.get('total', 0.0)
                            
                            print(f"Updated balance for {wallet_address[:12]}: confirmed={balances.get('available')}, pending={balances.get('pending')}")
                    
                    # Refresh UI after balances are calculated
                    if self.page:
                        self.page.run_thread(lambda: self.refresh_wallets_list_ui())
                        
                except Exception as e:
                    print(f"Error updating wallet balances: {e}")
            
            import threading
            threading.Thread(target=update_balances, daemon=True).start()
    
    def refresh_wallets_list_ui(self):
        """Refresh just the UI with updated balances"""
        wallets = self.wallet_core.get_wallets()
        
        # Update mobile list
        if 'mobile_wallets_list' in self.refs:
            mobile_list = self.refs['mobile_wallets_list'].current
            mobile_list.controls.clear()
            
            for i, wallet in enumerate(wallets):
                wallet_card = self._create_wallet_card(wallet, i)
                mobile_list.controls.append(wallet_card)
        
        # Update desktop list
        if 'desktop_wallets_list' in self.refs:
            desktop_list = self.refs['desktop_wallets_list'].current
            desktop_list.controls.clear()
            
            for i, wallet in enumerate(wallets):
                wallet_card = self._create_wallet_card(wallet, i)
                desktop_list.controls.append(wallet_card)
        
        if self.page:
            self.page.update()
    
    def _create_wallet_card(self, wallet, index):
        """Create a wallet card for display with balances"""
        is_selected = index == self.selected_wallet_index
        
        # Get wallet address and cached balances
        wallet_address = wallet.get('address') if isinstance(wallet, dict) else str(wallet)
        cached_confirmed = wallet.get('confirmed_balance') if isinstance(wallet, dict) else None
        cached_pending = wallet.get('pending_balance') if isinstance(wallet, dict) else None
        wallet_name = wallet.get('name', wallet.get('label', 'Unknown Wallet')) if isinstance(wallet, dict) else 'Unknown Wallet'
        
        # Format balance display
        if cached_confirmed is not None and cached_pending is not None:
            confirmed_str = f"{cached_confirmed:.6f}"
            pending_str = f"{cached_pending:.6f}"
            balance_display = f"Available: {confirmed_str} LKC | Pending: {pending_str} LKC"
        else:
            balance_display = "Balance: Loading..."
        
        return ft.Container(
            content=ft.Column([
                ft.Text(wallet_name, size=16, weight=ft.FontWeight.BOLD, color="#ffffff"),
                ft.Text(f"Address: {wallet_address[:12]}...", size=12, color="#aaaaaa"),
                ft.Text(balance_display, size=11, color="#cccccc"),
            ]),
            padding=15,
            bgcolor="#dc3545" if is_selected else "#2a2a2a",
            border_radius=8,
            on_click=lambda e, idx=index: self._on_wallet_click(idx),
            data=index
        )
    
    def _on_wallet_click(self, index):
        """Handle wallet selection"""
        self.selected_wallet_index = index
        if self.on_wallet_select:
            self.on_wallet_select(index)
        self.refresh_wallets_list()
        if self.page:
            self.page.update()
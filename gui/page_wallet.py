import flet as ft
import threading
from datetime import datetime
import time

class WalletPage:
    def __init__(self, app, on_send, on_receive, on_export_key, on_lock, on_create_wallet, on_import_wallet, on_settings):
        self.app = app
        self.on_send = on_send
        self.on_receive = on_receive
        self.on_export_key = on_export_key
        self.on_lock = on_lock
        self.on_create_wallet = on_create_wallet
        self.on_import_wallet = on_import_wallet
        self.on_settings = on_settings
        
        # Sidebar state
        self.sidebar_collapsed = False
        self.sidebar_width = 280
        self.sidebar_collapsed_width = 60
        
        # Refs for UI elements
        self.refs = {}
        
        # Transaction history state
        self.transaction_history = []
        
        # UI elements
        self.balance_text = ft.Text("0.00", size=28, weight="bold", color="#ffffff")
        self.address_text = ft.Text("", size=12, color="#f8d7da")
        self.sync_status = ft.Text("Syncing...", size=11, color="#ffd700")
        
        # Preloader state - start with loading FALSE so main content shows
        self.is_loading = False
        self.preloader = self.create_preloader()
        self.main_content = self.create_main_content()
        
    def create(self):
        # Auto-hide loading after a short delay to ensure data is loaded
        def auto_hide_loading():
            import time
            time.sleep(0.5)  # Short delay to ensure wallet data is ready
            self.hide_loading()
        
        threading.Thread(target=auto_hide_loading, daemon=True).start()
        
        return ft.Container(
            content=ft.Stack([self.main_content, self.preloader]),
            expand=True,
            bgcolor="#2c1a1a",
            padding=0
        )
    
    def create_preloader(self):
        return ft.Container(
            content=ft.Column([
                ft.Container(expand=True),
                ft.ProgressRing(width=40, height=40, color="#dc3545"),
                ft.Text("Loading...", color="#f8d7da", size=14),
                ft.Container(expand=True),
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            expand=True,
            bgcolor="#2c1a1a",
            visible=self.is_loading
        )
    
    def create_main_content(self):
        # Create sidebar
        sidebar = self._create_sidebar()
        
        # Create main wallet content
        wallet_content = self._create_wallet_content()
        
        return ft.Row([
            sidebar,
            ft.VerticalDivider(width=1, color="#5c2e2e"),
            wallet_content
        ], spacing=0, expand=True)
    
    def _create_sidebar(self):
        """Create collapsible sidebar with wallets list and actions"""
        # Sidebar header with toggle button
        sidebar_header = ft.Container(
            content=ft.Row([
                ft.IconButton(
                    icon=ft.Icons.MENU if self.sidebar_collapsed else ft.Icons.CHEVRON_LEFT,
                    icon_color="#f8d7da",
                    icon_size=20,
                    on_click=self._toggle_sidebar,
                    tooltip="Collapse/Expand"
                ),
                ft.Text("Wallets", 
                       size=16, 
                       weight="bold", 
                       color="#f8d7da",
                       visible=not self.sidebar_collapsed)
            ], spacing=10),
            padding=ft.padding.symmetric(vertical=15, horizontal=15),
            border=ft.border.only(bottom=ft.BorderSide(1, "#5c2e2e"))
        )
        
        # Wallets list
        self.refs['sidebar_wallets_list'] = ft.Ref[ft.Column]()
        wallets_list = ft.Column([], ref=self.refs['sidebar_wallets_list'])
        
        # Action buttons
        action_buttons = ft.Column([
            # Create Wallet button
            ft.Container(
                content=ft.Row([
                    ft.Icon(ft.Icons.ADD, size=20, color="#ffffff"),
                    ft.Text("Create Wallet", 
                           size=14, 
                           color="#ffffff",
                           visible=not self.sidebar_collapsed)
                ], spacing=12),
                padding=ft.padding.symmetric(vertical=12, horizontal=15),
                bgcolor="#dc3545",
                border_radius=8,
                on_click=lambda e: self.on_create_wallet(),
                tooltip="Create New Wallet" if self.sidebar_collapsed else None
            ),
            # Import Wallet button
            ft.Container(
                content=ft.Row([
                    ft.Icon(ft.Icons.IMPORT_EXPORT, size=20, color="#ffffff"),
                    ft.Text("Import Wallet", 
                           size=14, 
                           color="#ffffff",
                           visible=not self.sidebar_collapsed)
                ], spacing=12),
                padding=ft.padding.symmetric(vertical=12, horizontal=15),
                bgcolor="#28a745",
                border_radius=8,
                on_click=lambda e: self.on_import_wallet(),
                tooltip="Import Wallet" if self.sidebar_collapsed else None
            ),
        ], spacing=10)
        
        sidebar_content = ft.Column([
            sidebar_header,
            # Wallets section
            ft.Container(
                content=ft.Column([
                    ft.Text("My Wallets", 
                           size=14, 
                           color="#f8d7da",
                           weight="bold",
                           visible=not self.sidebar_collapsed),
                    ft.Container(height=10),
                    wallets_list,
                ]),
                padding=15,
                expand=True
            ),
            # Actions section
            ft.Container(
                content=action_buttons,
                padding=15
            )
        ], spacing=0)
        
        return ft.Container(
            content=sidebar_content,
            width=self.sidebar_collapsed_width if self.sidebar_collapsed else self.sidebar_width,
            bgcolor="#1a0f0f",
            animate=ft.Animation(300, "easeOut"),
            padding=0
        )
    
    def _create_wallet_content(self):
        """Create main wallet content area"""
        return ft.Container(
            content=ft.Column([
                self.create_header(),
                self.create_balance_card(),
                self.create_action_buttons(),
                self.create_transaction_history(),
            ], spacing=15),
            expand=True,
            padding=20,
            bgcolor="#2c1a1a"
        )
    
    def _toggle_sidebar(self, e):
        """Toggle sidebar collapsed state"""
        self.sidebar_collapsed = not self.sidebar_collapsed
        self._refresh_sidebar_wallets()
        if hasattr(self.app, 'page'):
            self.app.page.update()
    
    def _refresh_sidebar_wallets(self):
        """Refresh the wallets list in the sidebar"""
        if 'sidebar_wallets_list' not in self.refs:
            return
            
        sidebar_list = self.refs['sidebar_wallets_list'].current
        if not sidebar_list:
            return
            
        sidebar_list.controls.clear()
        
        try:
            if hasattr(self.app, 'wallet_core') and self.app.wallet_core:
                # Get wallets from wallet core
                wallets = []
                if hasattr(self.app.wallet_core, 'wallets'):
                    if isinstance(self.app.wallet_core.wallets, dict):
                        # Convert dictionary to list, including address for selection
                        for address, wallet_data in self.app.wallet_core.wallets.items():
                            wallets.append({
                                'address': address,  # Include address for selection
                                'label': wallet_data.get('label', 'Wallet'),
                                'balance': wallet_data.get('balance', 0)
                            })
                    elif isinstance(self.app.wallet_core.wallets, list):
                        # Include address from list wallets
                        for wallet in self.app.wallet_core.wallets:
                            wallets.append({
                                'address': wallet.get('address', ''),
                                'label': wallet.get('label', 'Wallet'),
                                'balance': wallet.get('balance', 0)
                            })
                
                for i, wallet in enumerate(wallets):
                    wallet_item = self._create_sidebar_wallet_item(wallet, i)
                    sidebar_list.controls.append(wallet_item)
                    
        except Exception as e:
            print(f"Error refreshing sidebar wallets: {e}")
    
    def _create_sidebar_wallet_item(self, wallet, index):
        """Create wallet item for sidebar"""
        # Determine if this wallet is currently selected
        is_selected = False
        try:
            if hasattr(self.app.wallet_core, 'current_wallet_address'):
                current_address = self.app.wallet_core.current_wallet_address
                if isinstance(wallet, dict) and wallet.get('address') == current_address:
                    is_selected = True
                elif hasattr(self.app, 'selected_wallet_index') and index == self.app.selected_wallet_index:
                    is_selected = True
        except:
            is_selected = index == getattr(self.app, 'selected_wallet_index', 0)
        
        if self.sidebar_collapsed:
            # Collapsed view - just icon and first letter
            return ft.Container(
                content=ft.Column([
                    ft.Container(
                        content=ft.Text(wallet['label'][0].upper(), 
                                    size=12, 
                                    color="#ffffff",
                                    weight="bold"),
                        width=30,
                        height=30,
                        bgcolor="#dc3545" if is_selected else "#5c2e2e",
                        border_radius=15,
                        alignment=ft.alignment.center
                    ),
                    ft.Text(wallet['label'], 
                        size=10, 
                        color="#f8d7da",
                        text_align="center",
                        max_lines=1,
                        overflow="ellipsis")
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=5),
                padding=10,
                on_click=lambda e, idx=index: self._on_wallet_select(idx),
                tooltip=f"{wallet['label']}\nBalance: {wallet.get('balance', 0):.6f} LUN",
                data=index
            )
        else:
            # Expanded view - full info
            return ft.Container(
                content=ft.Column([
                    ft.Row([
                        ft.Container(
                            content=ft.Text(wallet['label'][0].upper(), 
                                        size=12, 
                                        color="#ffffff",
                                        weight="bold"),
                            width=30,
                            height=30,
                            bgcolor="#dc3545" if is_selected else "#5c2e2e",
                            border_radius=15,
                            alignment=ft.alignment.center
                        ),
                        ft.Column([
                            ft.Text(wallet['label'], 
                                size=14, 
                                color="#ffffff",
                                weight="bold"),
                            ft.Text(f"{wallet.get('balance', 0):.6f} LUN", 
                                size=10, 
                                color="#f8d7da"),
                        ], spacing=2, expand=True)
                    ], spacing=10),
                ]),
                padding=10,
                bgcolor="#2c1a1a" if is_selected else "transparent",
                border=ft.border.all(1, "#dc3545" if is_selected else "transparent"),
                border_radius=8,
                on_click=lambda e, idx=index: self._on_wallet_select(idx),
                data=index
            )
    def _sync_selected_wallet(self, wallet_address):
        """Sync blockchain data for the selected wallet only"""
        try:
            print(f"DEBUG: Starting sync for selected wallet: {wallet_address}")
            
            # Update sync status
            self.sync_status.value = "🔄 Syncing wallet..."
            if hasattr(self.app, 'page'):
                self.app.page.update()
            
            # Store the current address before sync
            original_address = getattr(self.app.wallet_core, 'current_wallet_address', None)
            
            # Ensure we're syncing the correct wallet
            if wallet_address != original_address:
                print(f"DEBUG: Address mismatch during sync: {wallet_address} vs {original_address}")
                return
            
            # Use the blockchain manager to scan for this specific wallet
            if hasattr(self.app, 'blockchain_manager'):
                try:
                    # Scan transactions for the selected wallet
                    transactions = self.app.blockchain_manager.scan_transactions_for_address(wallet_address)
                    print(f"DEBUG: Found {len(transactions)} transactions for {wallet_address}")
                    
                    # Update the database with transactions for this wallet
                    if hasattr(self.app, 'database'):
                        for tx in transactions:
                            self.app.database.save_transaction(tx, wallet_address)
                    
                    # Calculate balance for this wallet
                    balance = 0.0
                    for tx in transactions:
                        direction = tx.get('direction', 'unknown')
                        amount = float(tx.get('amount', 0))
                        fee = float(tx.get('fee', 0))
                        
                        if direction == 'incoming':
                            balance += amount
                        elif direction == 'outgoing':
                            balance -= (amount + fee)
                    
                    # Update the wallet balance in the core
                    if hasattr(self.app.wallet_core, 'update_balance'):
                        self.app.wallet_core.update_balance(balance)
                    
                    # Update the specific wallet's balance in the wallets dict
                    if wallet_address in self.app.wallet_core.wallets:
                        self.app.wallet_core.wallets[wallet_address]['balance'] = balance
                    
                    # Save the updated wallet data
                    self.app.save_wallet_data(force_save=True)
                    
                    # Update UI
                    def update_ui():
                        self.sync_status.value = "✅ Synced"
                        self.update_wallet_data()
                        self.refresh_transaction_history()
                        
                        if hasattr(self.app, 'show_snackbar'):
                            self.app.show_snackbar(f"Synced wallet: {wallet_address[:8]}...", "success")
                        
                        if hasattr(self.app, 'page'):
                            self.app.page.update()
                    
                    if hasattr(self.app, 'page'):
                        self.app.page.run_thread(update_ui)
                    
                except Exception as e:
                    print(f"DEBUG: Sync error for {wallet_address}: {e}")
                    
                    def show_error():
                        self.sync_status.value = "❌ Sync failed"
                        if hasattr(self.app, 'show_snackbar'):
                            self.app.show_snackbar(f"Sync failed: {str(e)[:50]}", "error")
                        if hasattr(self.app, 'page'):
                            self.app.page.update()
                    
                    if hasattr(self.app, 'page'):
                        self.app.page.run_thread(show_error)
            
        except Exception as e:
            print(f"DEBUG: Error in _sync_selected_wallet: {e}")
    def _on_wallet_select(self, index):
        """Handle wallet selection from sidebar"""
        try:
            if hasattr(self.app, 'selected_wallet_index'):
                self.app.selected_wallet_index = index
                
            # Get the selected wallet address
            if hasattr(self.app, 'wallet_core') and self.app.wallet_core:
                if isinstance(self.app.wallet_core.wallets, dict):
                    wallet_addresses = list(self.app.wallet_core.wallets.keys())
                    if index < len(wallet_addresses):
                        selected_address = wallet_addresses[index]
                        
                        # Switch to the selected wallet in the core
                        if hasattr(self.app.wallet_core, 'switch_wallet'):
                            # Try to switch without password first (if already unlocked)
                            success = self.app.wallet_core.switch_wallet(selected_address)
                            if not success and hasattr(self.app.wallet_core, 'unlock_wallet'):
                                # If switching failed, the wallet might be locked
                                # We'll need to prompt for password, but for now just update display
                                pass
                        
                        # Update current wallet address in app
                        self.app.wallet_core.current_wallet_address = selected_address
                        
                        # Save the wallet selection
                        self.app.save_wallet_data(force_save=True)
                        
                        print(f"DEBUG: Switched to wallet: {selected_address}")
                
            # Refresh all UI components
            self._refresh_sidebar_wallets()
            self.update_wallet_data()
            
            if hasattr(self.app, 'page'):
                self.app.page.update()
                
        except Exception as e:
            print(f"Error selecting wallet: {e}")
    
    def create_header(self):
        return ft.Container(
            content=ft.Row([
                ft.Container(
                    content=ft.Image(
                        src="./wallet_icon.svg",
                        width=20,
                        height=20,
                        color="#dc3545",
                        error_content=ft.Icon(ft.Icons.ACCOUNT_BALANCE_WALLET, size=20, color="#dc3545")
                    ),
                    padding=5
                ),
                ft.Text("Luna Wallet", size=16, weight="bold", color="#f8d7da"),
                ft.Container(expand=True),
                ft.Row([
                    ft.IconButton(
                        icon=ft.Icons.REFRESH,
                        icon_color="#f8d7da",
                        icon_size=18,
                        on_click=self.manual_sync,
                        tooltip="Sync",
                        style=ft.ButtonStyle(padding=5)
                    ),
                    ft.IconButton(
                        icon=ft.Icons.LOCK,
                        icon_color="#f8d7da",
                        icon_size=18,
                        on_click=self.app.lock_wallet,
                        tooltip="Lock",
                        style=ft.ButtonStyle(padding=5)
                    ),
                ], spacing=5),
            ]),
            padding=ft.padding.symmetric(vertical=5)
        )
    
    def create_balance_card(self):
        return ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Text("Total Balance", size=14, color="#f8d7da", expand=True),
                    ft.Container(
                        content=self.sync_status,
                        padding=5,
                        bgcolor="#1a0f0f",
                        border_radius=8
                    )
                ]),
                self.balance_text,
                ft.Container(
                    content=self.address_text,
                    padding=8,
                    bgcolor="#1a0f0f",
                    border_radius=8,
                    width=300
                ),
                self.create_quick_stats()
            ], spacing=8),
            padding=15,
            bgcolor="#1a0f0f",
            border_radius=12
        )
    
    def create_quick_stats(self):
        self.stats_row = ft.Row([], scroll=ft.ScrollMode.ADAPTIVE)
        self.update_quick_stats()
        return self.stats_row
    
    def create_action_buttons(self):
        return ft.Container(
            content=ft.Row([
                ft.ElevatedButton(
                    "📤 Send",
                    on_click=lambda e: self.on_send(),
                    style=ft.ButtonStyle(
                        color="#ffffff",
                        bgcolor="#dc3545",
                        padding=ft.padding.symmetric(horizontal=12, vertical=8),
                        shape=ft.RoundedRectangleBorder(radius=8)
                    ),
                    height=36,
                    expand=True
                ),
                ft.ElevatedButton(
                    "📥 Receive",
                    on_click=lambda e: self.on_receive(),
                    style=ft.ButtonStyle(
                        color="#ffffff",
                        bgcolor="#dc3545",
                        padding=ft.padding.symmetric(horizontal=12, vertical=8),
                        shape=ft.RoundedRectangleBorder(radius=8)
                    ),
                    height=36,
                    expand=True
                ),
                ft.ElevatedButton(
                    "🔑 Key",
                    on_click=lambda e: self.on_export_key(),
                    style=ft.ButtonStyle(
                        color="#ffffff",
                        bgcolor="#dc3545",
                        padding=ft.padding.symmetric(horizontal=12, vertical=8),
                        shape=ft.RoundedRectangleBorder(radius=8)
                    ),
                    height=36,
                    expand=True
                ),
            ], spacing=8),
            padding=ft.padding.symmetric(vertical=5)
        )
    
    def create_transaction_history(self):
        self.transactions_list = ft.ListView(
            spacing=5, 
            height=250, 
            expand=True,
            auto_scroll=False
        )
        
        # Load initial transactions
        self.refresh_transaction_history()
        
        return ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Text("📊 Recent Transactions", size=16, weight="bold", color="#f8d7da", expand=True),
                    ft.IconButton(
                        icon=ft.Icons.REFRESH,
                        icon_color="#f8d7da",
                        icon_size=16,
                        on_click=lambda e: self.refresh_transaction_history(),
                        tooltip="Refresh Transactions",
                        style=ft.ButtonStyle(padding=3)
                    )
                ]),
                ft.Container(
                    content=self.transactions_list,
                    padding=10,
                    bgcolor="#1a0f0f",
                    border_radius=12,
                    height=250,
                    expand=True
                )
            ], spacing=8),
            expand=True
        )
    
    def refresh_transaction_history(self):
        """Load and display transaction history"""
        try:
            # Clear current list
            self.transactions_list.controls.clear()
            
            # Get current wallet address
            current_address = None
            if hasattr(self.app.wallet_core, 'current_wallet_address'):
                current_address = self.app.wallet_core.current_wallet_address
            elif hasattr(self.app.wallet_core, 'address'):
                current_address = self.app.wallet_core.address
            
            if not current_address:
                self._show_no_wallet_message()
                return
            
            # Try to get transactions from various sources
            transactions = []
            
            # Method 1: Try blockchain manager
            if hasattr(self.app, 'blockchain_manager'):
                try:
                    transactions = self.app.blockchain_manager.scan_transactions_for_address(current_address)
                    print(f"Loaded {len(transactions)} transactions from blockchain")
                except Exception as e:
                    print(f"Error loading from blockchain: {e}")
            
            # Method 2: Try database
            if not transactions and hasattr(self.app, 'database'):
                try:
                    # Try common database methods
                    db_methods = ['get_transactions', 'get_wallet_transactions', 'get_all_transactions']
                    for method in db_methods:
                        if hasattr(self.app.database, method):
                            try:
                                if method == 'get_all_transactions':
                                    all_txs = getattr(self.app.database, method)()
                                    transactions = [tx for tx in all_txs if 
                                                  tx.get('from') == current_address or 
                                                  tx.get('to') == current_address]
                                else:
                                    transactions = getattr(self.app.database, method)(current_address)
                                if transactions:
                                    print(f"Loaded {len(transactions)} transactions from database")
                                    break
                            except:
                                continue
                except Exception as e:
                    print(f"Error loading from database: {e}")
            
            # Method 3: Try wallet core
            if not transactions and hasattr(self.app.wallet_core, 'get_transaction_history'):
                try:
                    history = self.app.wallet_core.get_transaction_history()
                    if isinstance(history, dict):
                        transactions = history.get('confirmed', []) + history.get('pending', [])
                    elif isinstance(history, list):
                        transactions = history
                    if transactions:
                        print(f"Loaded {len(transactions)} transactions from wallet core")
                except Exception as e:
                    print(f"Error loading from wallet core: {e}")
            
            # Sort by timestamp (newest first) and limit
            transactions.sort(key=lambda x: x.get('timestamp', 0), reverse=True)
            transactions = transactions[:20]  # Show last 20 transactions
            
            # Display transactions
            if transactions:
                for tx in transactions:
                    tx_item = self._create_transaction_item(tx, current_address)
                    self.transactions_list.controls.append(tx_item)
            else:
                self._show_no_transactions_message()
                
            if hasattr(self.app, 'page'):
                self.app.page.update()
                
        except Exception as e:
            print(f"Error refreshing transaction history: {e}")
            self._show_error_message(str(e))
    
    def _create_transaction_item(self, tx_data, current_address):
        """Create a minimalistic transaction list item"""
        tx_type = tx_data.get('type', 'transfer')
        amount = tx_data.get('amount', 0)
        from_addr = tx_data.get('from', 'Unknown')
        to_addr = tx_data.get('to', 'Unknown')
        status = tx_data.get('status', 'confirmed')
        timestamp = tx_data.get('timestamp', time.time())
        memo = tx_data.get('memo', '')
        
        # Determine if incoming or outgoing
        is_incoming = self._is_incoming_transaction(tx_data, current_address)
        
        # Format amount with color and prefix
        amount_color = "#00ff00" if is_incoming else "#ff4444"
        amount_prefix = "+" if is_incoming else "-"
        
        # Format date
        try:
            date_str = datetime.fromtimestamp(timestamp).strftime("%m/%d %H:%M")
        except:
            date_str = "Unknown"
        
        # Status indicator
        status_color = "#00ff00" if status == 'confirmed' else "#ffd700"
        status_text = "✓" if status == 'confirmed' else "⏳"
        
        # Create minimal transaction item
        return ft.Container(
            content=ft.ListTile(
                leading=ft.Icon(
                    ft.Icons.ARROW_UPWARD if not is_incoming else ft.Icons.ARROW_DOWNWARD,
                    color=amount_color,
                    size=20
                ),
                title=ft.Row([
                    ft.Text(f"{amount_prefix}{amount:.6f} LUN", 
                           color=amount_color, 
                           size=14,
                           weight="bold",
                           expand=True),
                    ft.Text(status_text, color=status_color, size=12),
                ]),
                subtitle=ft.Row([
                    ft.Text(date_str, size=11, color="#a8a8a8", expand=True),
                    ft.Text(memo if memo else tx_type, size=11, color="#a8a8a8"),
                ]),
                on_click=lambda e, tx=tx_data: self._show_transaction_details(tx),
            ),
            bgcolor="#2c1a1a",
            border_radius=8,
            padding=5,
            margin=ft.margin.symmetric(vertical=1),
        )
    
    def _is_incoming_transaction(self, tx_data, current_address):
        """Determine if transaction is incoming to current wallet"""
        try:
            tx_type = tx_data.get('type', '')
            to_addr = tx_data.get('to', '')
            
            # Rewards and fee distributions are always incoming
            if tx_type in ['reward', 'fee_distribution']:
                return True
            
            # For transfers, check if we're the recipient
            return to_addr.lower() == current_address.lower()
            
        except:
            return False
    
    def _show_no_transactions_message(self):
        """Show no transactions message"""
        self.transactions_list.controls.append(
            ft.Container(
                content=ft.Column([
                    ft.Icon(ft.Icons.RECEIPT_LONG, size=32, color="#5c2e2e"),
                    ft.Text("No transactions yet", color="#f8d7da", size=14),
                    ft.Text("Your transactions will appear here", color="#a8a8a8", size=12),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=5),
                padding=20,
                alignment=ft.alignment.center
            )
        )
    
    def _show_no_wallet_message(self):
        """Show no wallet selected message"""
        self.transactions_list.controls.append(
            ft.Container(
                content=ft.Column([
                    ft.Icon(ft.Icons.WALLET, size=32, color="#5c2e2e"),
                    ft.Text("No Wallet Selected", color="#f8d7da", size=14),
                    ft.Text("Select a wallet to view transactions", color="#a8a8a8", size=12),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=5),
                padding=20,
                alignment=ft.alignment.center
            )
        )
    
    def _show_error_message(self, error: str):
        """Show error message"""
        self.transactions_list.controls.append(
            ft.Container(
                content=ft.Column([
                    ft.Icon(ft.Icons.ERROR, size=32, color="#5c2e2e"),
                    ft.Text("Error Loading", color="#f8d7da", size=14),
                    ft.Text(f"Failed to load transactions", color="#a8a8a8", size=12),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=5),
                padding=20,
                alignment=ft.alignment.center
            )
        )
    
    def _show_transaction_details(self, tx_data):
        """Show transaction details in a dialog"""
        # Import and show the transaction details page
        from gui.page_details import TransactionDetailsPage
        
        details_page = TransactionDetailsPage(
            self.app,
            tx_data,
            on_back=self._return_to_wallet
        )
        
        # Replace current page with details page
        self.app.current_page = details_page.create()
        self.app.show_current_page()

    def _return_to_wallet(self):
        """Return to wallet page from details"""
        # Recreate the wallet page to ensure fresh data
        wallet_page = WalletPage(
            self.app,
            on_send=self.on_send,
            on_receive=self.on_receive,
            on_export_key=self.on_export_key,
            on_create_wallet=self.on_create_wallet,
            on_import_wallet=self.on_import_wallet
        )
        self.app.current_page = wallet_page.create()
        self.app.show_current_page()
    def _create_detail_row(self, label, value, color):
        return ft.Container(
            content=ft.Row([
                ft.Text(label, size=12, color="#f8d7da", weight="bold", width=120),
                ft.Text(value, size=12, color=color, expand=True, selectable=True),
            ]),
            padding=ft.padding.symmetric(vertical=2)
        )
    
    def update_quick_stats(self):
        stats = []
        
        try:
            if hasattr(self.app, 'wallet_core') and self.app.wallet_core:
                # Check if wallet is unlocked using multiple methods
                is_unlocked = (
                    getattr(self.app.wallet_core, 'is_unlocked', False) or
                    getattr(self.app.wallet_core, 'is_locked', True) == False or
                    getattr(self.app, 'is_locked', True) == False
                )
                
                if is_unlocked:
                    # Block height - try to get from blockchain
                    try:
                        # Use the blockchain manager to get height
                        if hasattr(self.app, 'blockchain_manager'):
                            height = self.app.blockchain_manager.get_blockchain_height()
                            stats.append(self.create_stat_item("📦", f"{height}", "Height"))
                        else:
                            stats.append(self.create_stat_item("📦", "0", "Height"))
                    except:
                        stats.append(self.create_stat_item("📦", "0", "Height"))
                    
                    # Network status - actually check the connection
                    try:
                        network_status = self._check_network_status()
                        if network_status['connected']:
                            stats.append(self.create_stat_item("🟢", "Online", "Network"))
                            # Update sync status to show we're connected
                            self.sync_status.value = "✅ Connected"
                        else:
                            stats.append(self.create_stat_item("🔴", "Offline", "Network"))
                            self.sync_status.value = "❌ Offline"
                    except:
                        stats.append(self.create_stat_item("❓", "Unknown", "Network"))
                    
                    # Wallet count
                    try:
                        wallet_count = len(self.app.wallet_core.wallets) if self.app.wallet_core.wallets else 0
                        stats.append(self.create_stat_item("👛", f"{wallet_count}", "Wallets"))
                    except:
                        stats.append(self.create_stat_item("👛", "1", "Wallets"))
                    
                else:
                    stats.append(self.create_stat_item("🔒", "Locked", "Wallet"))
                    stats.append(self.create_stat_item("⏳", "Waiting", "Sync"))
            
            else:
                stats.append(self.create_stat_item("❌", "No Core", "Wallet"))
            
        except Exception as e:
            stats.append(self.create_stat_item("❌", "Error", "Stats"))
        
        self.stats_row.controls = stats

    def refresh_network_status(self):
        """Manually refresh network status"""
        try:
            network_status = self._check_network_status()
            
            if network_status['connected']:
                self.sync_status.value = "✅ Connected"
                if hasattr(self.app, 'show_snackbar'):
                    self.app.show_snackbar("Connected to blockchain", "success")
            else:
                self.sync_status.value = "❌ Offline"
                if hasattr(self.app, 'show_snackbar'):
                    self.app.show_snackbar("Cannot connect to blockchain", "error")
            
            # Update the quick stats to reflect new network status
            self.update_quick_stats()
            
            if hasattr(self.app, 'page'):
                self.app.page.update()
                
        except Exception as e:
            print(f"Error refreshing network status: {e}")

    def _check_network_status(self):
        """Check network connection to blockchain endpoint"""
        try:
            import requests
            
            # Check if we have blockchain_manager with network check
            if hasattr(self.app, 'blockchain_manager'):
                is_connected = self.app.blockchain_manager.check_network_connection()
                return {'connected': is_connected, 'endpoint': 'blockchain_manager'}
            
            # Fallback: direct check to your endpoint
            endpoint_url = "https://bank.linglin.art"
            
            try:
                # Try health endpoint first
                response = requests.get(f"{endpoint_url}/health", timeout=5)
                if response.status_code == 200:
                    return {'connected': True, 'endpoint': endpoint_url}
            except:
                pass
            
            try:
                # Try blockchain height as fallback
                response = requests.get(f"{endpoint_url}/blockchain/height", timeout=5)
                if response.status_code == 200:
                    return {'connected': True, 'endpoint': endpoint_url}
            except:
                pass
            
            return {'connected': False, 'endpoint': endpoint_url}
            
        except Exception as e:
            print(f"Network check error: {e}")
            return {'connected': False, 'endpoint': 'error'}

    def create_stat_item(self, icon, value, label):
        return ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Text(icon, size=12),
                    ft.Text(value, size=12, color="#ffffff", weight="bold")
                ], spacing=2),
                ft.Text(label, size=10, color="#f8d7da")
            ], spacing=2, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            padding=8,
            bgcolor="#2c1a1a",
            border_radius=8,
            margin=ft.margin.symmetric(horizontal=2)
        )
    
    def manual_sync(self, e=None):
        self.sync_status.value = "🔄 Syncing all wallets..."
        if self.app.page:
            self.app.page.update()
        
        def sync_thread():
            try:
                if hasattr(self.app, 'sync_all_wallets'):
                    self.app.sync_all_wallets()
                    
                    def update_ui():
                        self.sync_status.value = "✅ Synced"
                        self.update_wallet_data()
                        self._refresh_sidebar_wallets()
                        self.refresh_transaction_history()
                        
                        if hasattr(self.app, 'show_snackbar'):
                            self.app.show_snackbar("All wallets synced!", "success")
                        
                        if self.app.page:
                            self.app.page.update()
                    
                    if hasattr(self.app, 'page'):
                        self.app.page.run_thread(update_ui)
                else:
                    self.sync_status.value = "❌ Sync unavailable"
                    if self.app.page:
                        self.app.page.update()
                        
            except Exception as e:
                print(f"DEBUG: Manual sync error: {e}")
                
                def show_error():
                    self.sync_status.value = "❌ Sync failed"
                    if hasattr(self.app, 'show_snackbar'):
                        self.app.show_snackbar(f"Sync error: {str(e)[:50]}", "error")
                    if self.app.page:
                        self.app.page.update()
                
                if hasattr(self.app, 'page'):
                    self.app.page.run_thread(show_error)
        
        threading.Thread(target=sync_thread, daemon=True).start()

    def show_loading(self):
        self.is_loading = True
        self.preloader.visible = True
        self.main_content.visible = False
        if hasattr(self.app, 'page'):
            self.app.page.update()
    
    def hide_loading(self):
        self.is_loading = False
        self.preloader.visible = False
        self.main_content.visible = True
        self.update_wallet_data()
        if hasattr(self.app, 'page'):
            self.app.page.update()
    
    def update_wallet_data(self):
        try:
            if hasattr(self.app, 'wallet_core') and self.app.wallet_core:
                # Check if wallet is unlocked using multiple methods
                is_unlocked = (
                    getattr(self.app.wallet_core, 'is_unlocked', False) or
                    getattr(self.app.wallet_core, 'is_locked', True) == False or
                    getattr(self.app, 'is_locked', True) == False
                )
                
                if is_unlocked:
                    # Get current wallet info - try multiple methods
                    wallet_info = None
                    
                    # Method 1: Use get_wallet_info if available
                    if hasattr(self.app.wallet_core, 'get_wallet_info'):
                        wallet_info = self.app.wallet_core.get_wallet_info()
                    
                    # Method 2: Get from current wallet data
                    if not wallet_info and hasattr(self.app.wallet_core, 'current_wallet_address'):
                        current_address = self.app.wallet_core.current_wallet_address
                        if current_address and hasattr(self.app.wallet_core, 'wallets'):
                            if isinstance(self.app.wallet_core.wallets, dict) and current_address in self.app.wallet_core.wallets:
                                wallet_info = self.app.wallet_core.wallets[current_address]
                            elif isinstance(self.app.wallet_core.wallets, list):
                                # Find wallet by address in list
                                for wallet in self.app.wallet_core.wallets:
                                    if isinstance(wallet, dict) and wallet.get('address') == current_address:
                                        wallet_info = wallet
                                        break
                    
                    # Method 3: Get first wallet if no current
                    if not wallet_info and hasattr(self.app.wallet_core, 'wallets'):
                        if isinstance(self.app.wallet_core.wallets, dict) and self.app.wallet_core.wallets:
                            first_address = list(self.app.wallet_core.wallets.keys())[0]
                            wallet_info = self.app.wallet_core.wallets[first_address]
                        elif isinstance(self.app.wallet_core.wallets, list) and self.app.wallet_core.wallets:
                            wallet_info = self.app.wallet_core.wallets[0]
                    
                    if wallet_info:
                        balance = wallet_info.get('balance', 0)
                        address = wallet_info.get('address', 'No wallet')
                        label = wallet_info.get('label', 'Wallet')
                        
                        self.balance_text.value = f"{balance:.6f}"
                        self.address_text.value = f"{label}: {address[:12]}...{address[-6:]}" if len(address) > 20 else address
                    else:
                        self.balance_text.value = "0.00"
                        self.address_text.value = "No wallet data"
                    
                    self.sync_status.value = "✅ Ready"
                else:
                    self.balance_text.value = "0.00"
                    self.address_text.value = "Wallet Locked"
                    self.sync_status.value = "🔒 Locked"
                
                self.update_quick_stats()
                self.refresh_transaction_history()
                self._refresh_sidebar_wallets()  # Refresh sidebar when wallet data updates
            
        except Exception as e:
            self.balance_text.value = "Error"
            self.address_text.value = "Failed to load"
            self.sync_status.value = "❌ Error"
            print(f"Error updating wallet data: {e}")
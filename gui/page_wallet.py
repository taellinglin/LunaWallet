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
        self.balance_text = ft.Text("0.00 LKC", size=28, weight="bold", color="#ffffff")
        self.pending_balance_text = ft.Text("0.00 LKC", size=16, weight="500", color="#ffd700")
        self.address_text = ft.Text("", size=12, color="#f8d7da")
        
        # Create balance card and store in ref
        self.refs['balance_card'] = ft.Ref[ft.Container]()
        self.balance_card = self.create_balance_card()
        
        # Preloader state - start with loading FALSE so main content shows
        self.is_loading = False
        self.preloader = self.create_preloader()
        self.main_content = self.create_main_content()
        
        # Threading lock for sidebar updates to prevent duplicates
        self.sidebar_update_lock = threading.Lock()
        
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
                self.balance_card,  # Use stored balance card reference
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
        # Use lock to prevent concurrent updates causing duplicates
        with self.sidebar_update_lock:
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
                            print(f"\n=== REFRESHING SIDEBAR: Found {len(self.app.wallet_core.wallets)} wallets ===")
                            for address, wallet_data in self.app.wallet_core.wallets.items():
                                balance = wallet_data.get('balance', 0)
                                confirmed_balance = wallet_data.get('confirmed_balance', balance)  # Use confirmed_balance if available
                                pending = wallet_data.get('pending_balance', 0)
                                label = wallet_data.get('label', 'Wallet')
                                print(f"  {label} ({address[:12]}...): balance={balance:.6f}, confirmed={confirmed_balance:.6f}, pending={pending:.6f}")
                                wallets.append({
                                    'address': address,
                                    'label': label,
                                    'balance': balance,
                                    'confirmed_balance': confirmed_balance,  # Include confirmed_balance
                                    'pending_balance': pending
                                })
                        elif isinstance(self.app.wallet_core.wallets, list):
                            # Include address from list wallets
                            for wallet in self.app.wallet_core.wallets:
                                wallets.append({
                                    'address': wallet.get('address', ''),
                                    'label': wallet.get('label', 'Wallet'),
                                    'balance': wallet.get('balance', 0),
                                    'pending_balance': wallet.get('pending_balance', 0)
                                })
                    
                    for i, wallet in enumerate(wallets):
                        wallet_item = self._create_sidebar_wallet_item(wallet, i)
                        sidebar_list.controls.append(wallet_item)
                    
                    print(f"=== SIDEBAR REFRESH COMPLETE ===\n")
                        
            except Exception as e:
                print(f"Error refreshing sidebar wallets: {e}")
                import traceback
                traceback.print_exc()
    
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
                tooltip=f"{wallet['label']}\nBalance: {wallet.get('confirmed_balance', wallet.get('balance', 0)):.6f} LKC\nPending: {wallet.get('pending_balance', 0):+.6f} LKC",
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
                            ft.Text(f"{wallet.get('confirmed_balance', wallet.get('balance', 0)):.6f} LKC", 
                                size=10, 
                                color="#f8d7da"),
                            ft.Text(f"Pending: {wallet.get('pending_balance', 0):+.6f}", 
                                size=8, 
                                color="#ffd700"),
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
    def _on_wallet_select(self, index):
        """Handle wallet selection from sidebar - immediate UI update with background refresh"""
        try:
            if hasattr(self.app, 'selected_wallet_index'):
                self.app.selected_wallet_index = index
                
            # Get the selected wallet address
            if hasattr(self.app, 'wallet_core') and self.app.wallet_core:
                if isinstance(self.app.wallet_core.wallets, dict):
                    wallet_addresses = list(self.app.wallet_core.wallets.keys())
                    if index < len(wallet_addresses):
                        selected_address = wallet_addresses[index]
                        
                        # Switch to the selected wallet in the core (fast in-memory operation)
                        if hasattr(self.app.wallet_core, 'switch_wallet'):
                            success = self.app.wallet_core.switch_wallet(selected_address)
                            if not success and hasattr(self.app.wallet_core, 'unlock_wallet'):
                                pass
                        
                        # Update current wallet address in app
                        self.app.wallet_core.current_wallet_address = selected_address
                        
                        print(f"DEBUG: Switched to wallet: {selected_address}")
            
            # Immediately update UI with cached data
            self._refresh_sidebar_wallets()
            self._update_wallet_data_ui_only()
            
            if hasattr(self.app, 'page'):
                self.app.page.update()
            
            # Defer heavy operations to background threads
            def background_operations():
                try:
                    # Save wallet selection
                    self.app.save_wallet_data(force_save=True)
                    
                    # Recalculate balances fresh from all transactions
                    self.recalculate_wallet_balances(selected_address)
                    
                    # Refresh transactions list for display
                    self.refresh_transaction_history()
                    self.update_quick_stats()
                    
                    # Schedule UI update on main thread
                    def update_ui():
                        try:
                            if hasattr(self.app, 'page'):
                                self.app.page.update()
                        except Exception as ui_error:
                            print(f"DEBUG: Error updating UI: {ui_error}")
                    
                    # Use page.run_task to schedule on main thread
                    if hasattr(self.app, 'page') and hasattr(self.app.page, 'run_task'):
                        self.app.page.run_task(update_ui)
                    else:
                        # Fallback if run_task not available
                        update_ui()
                        
                except Exception as e:
                    print(f"DEBUG: Error in background operations: {e}")
            
            threading.Thread(target=background_operations, daemon=True).start()
                
        except Exception as e:
            print(f"Error selecting wallet: {e}")
    
    def _get_pending_balance(self, address: str) -> float:
        """Get pending balance from stored wallet data (no mempool scanning)"""
        try:
            if hasattr(self.app, 'wallet_core') and self.app.wallet_core:
                if hasattr(self.app.wallet_core, 'wallets'):
                    if isinstance(self.app.wallet_core.wallets, dict) and address in self.app.wallet_core.wallets:
                        wallet = self.app.wallet_core.wallets[address]
                        return wallet.get('pending_balance', 0.0)
            return 0.0
        except Exception as e:
            print(f"Error getting pending balance: {e}")
            return 0.0
    
    def update_balance_card(self, confirmed_balance: float = None, pending_balance: float = None):
        """Update balance card display with stored values (no scanning)"""
        try:
            # If no values provided, get from current wallet
            if confirmed_balance is None or pending_balance is None:
                if hasattr(self.app, 'wallet_core') and self.app.wallet_core:
                    if hasattr(self.app.wallet_core, 'current_wallet_address'):
                        current_addr = self.app.wallet_core.current_wallet_address
                        if current_addr and hasattr(self.app.wallet_core, 'wallets'):
                            if isinstance(self.app.wallet_core.wallets, dict) and current_addr in self.app.wallet_core.wallets:
                                wallet = self.app.wallet_core.wallets[current_addr]
                                confirmed_balance = wallet.get('confirmed_balance', 0.0)
                                pending_balance = wallet.get('pending_balance', 0.0)
            
            # Update display with stored values
            if confirmed_balance is not None:
                self.balance_text.value = f"{confirmed_balance:.6f} LKC"
                self.balance_text.update()
            if pending_balance is not None:
                self.pending_balance_text.value = f"{pending_balance:.6f} LKC"
                self.pending_balance_text.update()
            
            # Update the page to reflect changes
            if hasattr(self, 'page') and self.page:
                try:
                    self.page.update()
                except:
                    pass
                    
        except Exception as e:
            print(f"Error updating balance card: {e}")
    
    def _update_wallet_data_ui_only(self):
        """Update wallet data UI from cached data - recreate balance card content"""
        try:
            current_address = None
            wallet_data = None
            
            # Get current wallet address and data
            if hasattr(self.app, 'wallet_core') and self.app.wallet_core:
                if hasattr(self.app.wallet_core, 'current_wallet_address'):
                    current_address = self.app.wallet_core.current_wallet_address
                    print(f"DEBUG CARD: current_address = {current_address}")
                
                if current_address and hasattr(self.app.wallet_core, 'wallets'):
                    if isinstance(self.app.wallet_core.wallets, dict):
                        wallet_data = self.app.wallet_core.wallets.get(current_address)
                        print(f"DEBUG CARD: wallet_data found = {wallet_data is not None}")
                
                # Fallback: get first wallet if no current address
                if not wallet_data and hasattr(self.app.wallet_core, 'wallets'):
                    if isinstance(self.app.wallet_core.wallets, dict) and self.app.wallet_core.wallets:
                        current_address = list(self.app.wallet_core.wallets.keys())[0]
                        wallet_data = self.app.wallet_core.wallets[current_address]
                        print(f"DEBUG CARD: Using fallback wallet: {current_address}")
            
            # Update UI with wallet data
            if wallet_data and current_address:
                # Read balance: use 'available_balance' (confirmed only, not including pending)
                # to match what sidebar shows with confirmed_balance
                available_balance = wallet_data.get('available_balance', wallet_data.get('confirmed_balance', wallet_data.get('balance', 0.0)))
                pending_balance = wallet_data.get('pending_balance', 0.0)
                label = wallet_data.get('label', 'Wallet')
                
                print(f"DEBUG CARD: available_balance = {available_balance}, type = {type(available_balance)}")
                print(f"DEBUG CARD: pending_balance = {pending_balance}, type = {type(pending_balance)}")
                
                # Convert to float
                try:
                    available_balance = float(available_balance) if available_balance is not None else 0.0
                    pending_balance = float(pending_balance) if pending_balance is not None else 0.0
                except Exception as conv_error:
                    print(f"DEBUG CARD: Error converting balance: {conv_error}")
                    available_balance = 0.0
                    pending_balance = 0.0
                
                balance_str = f"{available_balance:.6f} LKC"
                pending_str = f"{pending_balance:+.6f} LKC"
                
                print(f"DEBUG CARD: Final balance_str = '{balance_str}'")
                
                # Update the text widget values directly
                self.balance_text.value = balance_str
                self.pending_balance_text.value = pending_str
                
                # Set color
                if pending_balance > 0:
                    self.pending_balance_text.color = "#00ff00"  # Green for positive
                elif pending_balance < 0:
                    self.pending_balance_text.color = "#ff4444"  # Red for negative
                else:
                    self.pending_balance_text.color = "#ffd700"  # Yellow for zero
                
                # Update address display
                label_text = label if label else "Wallet"
                addr_text = f"{current_address[:12]}...{current_address[-6:]}" if len(current_address) > 20 else current_address
                self.address_text.value = f"{label_text}: {addr_text}"
                
                # Force update on the balance card container and everything inside it
                try:
                    if 'balance_card' in self.refs:
                        card_ref = self.refs['balance_card'].current
                        if card_ref:
                            print(f"DEBUG CARD: Updating balance_card container")
                            card_ref.update()
                        else:
                            print(f"DEBUG CARD: balance_card.current is None")
                    else:
                        print(f"DEBUG CARD: balance_card not in refs")
                except Exception as ref_error:
                    print(f"DEBUG CARD: Error accessing balance_card ref: {ref_error}")
                
                # Always update the page
                if hasattr(self.app, 'page') and self.app.page:
                    try:
                        print(f"DEBUG CARD: Calling page.update()")
                        self.app.page.update()
                    except Exception as page_error:
                        print(f"DEBUG CARD: Error updating page: {page_error}")
            else:
                print(f"DEBUG CARD: No wallet_data found or no current_address")
                self.balance_text.value = "0.000000 LKC"
                self.pending_balance_text.value = "0.000000 LKC"
                self.address_text.value = "No wallet selected"
                
                if hasattr(self.app, 'page') and self.app.page:
                    try:
                        self.app.page.update()
                    except:
                        pass
                
        except Exception as e:
            print(f"ERROR in _update_wallet_data_ui_only: {e}")
            import traceback
            traceback.print_exc()
            self.pending_balance_text.value = "0.000000 LKC"
            self.address_text.value = "Error loading balance"
    
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
            ref=self.refs['balance_card'],
            content=ft.Column([
                ft.Text("Wallet Balance", size=14, color="#f8d7da"),
                ft.Column([
                    self.balance_text,
                    ft.Row([
                        ft.Text("Pending:", size=10, color="#999999"),
                        self.pending_balance_text,
                    ], spacing=5),
                ], spacing=4),
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
    def _transaction_involves_wallet(self, tx_data, wallet_address):
        """Check if a transaction involves a specific wallet address"""
        try:
            if not wallet_address:
                return False
                
            wallet_lower = wallet_address.lower()
            
            # Check all possible address fields
            address_fields = ['from', 'to', 'reward_address', 'recipient', 'sender', 'receiver']
            
            for field in address_fields:
                field_value = tx_data.get(field, '')
                if isinstance(field_value, str) and field_value.lower() == wallet_lower:
                    return True
            
            # Special check for reward transactions
            tx_type = tx_data.get('type', '')
            if tx_type == 'reward':
                # For mining rewards, check if the reward is for this wallet
                reward_address = tx_data.get('reward_address', '')
                if reward_address.lower() == wallet_lower:
                    return True
            
            return False
            
        except Exception as e:
            print(f"Error checking transaction involvement: {e}")
            return False
    def refresh_transaction_history(self):
        """Load and display transaction history for CURRENT wallet only"""
        def load_transactions():
            try:
                # Get current wallet address
                current_address = None
                if hasattr(self.app.wallet_core, 'current_wallet_address'):
                    current_address = self.app.wallet_core.current_wallet_address
                elif hasattr(self.app.wallet_core, 'address'):
                    current_address = self.app.wallet_core.address
                
                if not current_address:
                    def show_no_wallet():
                        self._show_no_wallet_message()
                    if hasattr(self.app, 'page'):
                        self.app.page.run_thread(show_no_wallet)
                    return
                
                print(f"\n=== LOADING TRANSACTIONS FOR {current_address[:12]}... ===")
                
                # Try to get transactions from various sources
                all_transactions = []
                
                # Method 1: Try database (most reliable - includes both confirmed and pending)
                if hasattr(self.app, 'database'):
                    try:
                        db_methods = ['get_all_transactions', 'get_transactions', 'get_wallet_transactions']
                        for method in db_methods:
                            if hasattr(self.app.database, method):
                                try:
                                    if method == 'get_all_transactions':
                                        all_txs = getattr(self.app.database, method)()
                                        print(f"DEBUG: Database returned {len(all_txs)} total transactions")
                                        
                                        # Filter for current wallet
                                        all_transactions = []
                                        for tx in all_txs:
                                            # Check if this transaction involves our wallet
                                            from_addr = tx.get('from', '').lower()
                                            to_addr = tx.get('to', '').lower()
                                            reward_addr = tx.get('reward_address', '').lower()
                                            recipient_addr = tx.get('recipient', '').lower()
                                            status = tx.get('status', 'unknown')
                                            
                                            current_lower = current_address.lower()
                                            
                                            # Include if any address matches our wallet
                                            if (from_addr == current_lower or 
                                                to_addr == current_lower or
                                                reward_addr == current_lower or
                                                recipient_addr == current_lower):
                                                all_transactions.append(tx)
                                                print(f"  Found: {tx.get('hash', 'unknown')[:8]}... (status={status}, type={tx.get('type', 'unknown')})")
                                        
                                        print(f"DEBUG: Filtered {len(all_transactions)} transactions for current wallet")
                                        if all_transactions:
                                            break
                                    else:
                                        # These methods should return filtered transactions
                                        all_transactions = getattr(self.app.database, method)(current_address)
                                        if all_transactions:
                                            print(f"DEBUG: Loaded {len(all_transactions)} transactions via {method}")
                                            break
                                except Exception as e:
                                    print(f"DEBUG: Error with database method {method}: {e}")
                                    continue
                    except Exception as e:
                        print(f"DEBUG: Error loading from database: {e}")
                
                # Method 2: Try blockchain manager (for confirmed transactions only)
                if not all_transactions and hasattr(self.app, 'blockchain_manager'):
                    try:
                        all_transactions = self.app.blockchain_manager.scan_transactions_for_address(current_address)
                        print(f"DEBUG: Found {len(all_transactions)} transactions from blockchain manager")
                    except Exception as e:
                        print(f"DEBUG: Error loading from blockchain: {e}")
                
                print(f"DEBUG: Total transactions to display: {len(all_transactions)}")
                
                # Filter transactions specifically for the current wallet
                filtered_transactions = []
                for tx in all_transactions:
                    if self._transaction_involves_wallet(tx, current_address):
                        filtered_transactions.append(tx)
                
                print(f"DEBUG: After filtering: {len(filtered_transactions)} transactions")
                
                # Sort by timestamp (newest first) and limit
                filtered_transactions.sort(key=lambda x: x.get('timestamp', 0), reverse=True)
                filtered_transactions = filtered_transactions[:20]
                
                # Note: Balance recalculation is now done in _on_wallet_select() instead
                # to avoid duplicate sidebar refreshes during wallet selection
                
                def update_ui():
                    self.transactions_list.controls.clear()
                    
                    if filtered_transactions:
                        for tx in filtered_transactions:
                            tx_item = self._create_transaction_item(tx, current_address)
                            self.transactions_list.controls.append(tx_item)
                    else:
                        self._show_no_transactions_message()
                    
                    if hasattr(self.app, 'page'):
                        self.app.page.update()
                
                if hasattr(self.app, 'page'):
                    self.app.page.run_thread(update_ui)
                        
            except Exception as e:
                print(f"Error in load_transactions: {e}")
        
        threading.Thread(target=load_transactions, daemon=True).start()
    
    def recalculate_wallet_balances(self, wallet_address=None):
        """
        Recalculate available and pending balances from scratch by tallying:
        - All confirmed blockchain transactions (transfers, rewards, fees)
        - All pending mempool transactions
        Updates both balance card and sidebar immediately.
        """
        try:
            if not wallet_address:
                if hasattr(self.app.wallet_core, 'current_wallet_address'):
                    wallet_address = self.app.wallet_core.current_wallet_address
                else:
                    return
            
            if not wallet_address:
                return
            
            print(f"\n=== RECALCULATING BALANCES FOR {wallet_address[:12]}... ===")
            
            wallet_lower = wallet_address.lower()
            available_balance = 0.0
            pending_balance = 0.0
            
            # Get all transactions for this specific wallet from database
            all_transactions = []
            if hasattr(self.app, 'database'):
                print(f"DEBUG: Checking database methods...")
                print(f"  Database type: {type(self.app.database)}")
                print(f"  Has get_wallet_transactions: {hasattr(self.app.database, 'get_wallet_transactions')}")
                print(f"  Has get_all_transactions: {hasattr(self.app.database, 'get_all_transactions')}")
                
                # Try get_wallet_transactions first (specific to wallet)
                if hasattr(self.app.database, 'get_wallet_transactions'):
                    try:
                        all_transactions = self.app.database.get_wallet_transactions(wallet_address)
                        print(f"SUCCESS: get_wallet_transactions() returned {len(all_transactions)} transactions")
                    except Exception as e:
                        print(f"ERROR calling get_wallet_transactions({wallet_address[:12]}...): {e}")
                        all_transactions = []
                
                # If that didn't work, try get_all_transactions
                if not all_transactions and hasattr(self.app.database, 'get_all_transactions'):
                    try:
                        print(f"Attempting fallback: get_all_transactions()...")
                        all_txs = self.app.database.get_all_transactions()
                        print(f"DEBUG: Fallback - got {len(all_txs)} total transactions from database")
                        
                        # Filter for this wallet
                        for tx in all_txs:
                            from_addr = tx.get('from', '').lower()
                            to_addr = tx.get('to', '').lower()
                            reward_addr = tx.get('reward_address', '').lower()
                            
                            # Include if this wallet is involved
                            if (from_addr == wallet_lower or 
                                to_addr == wallet_lower or
                                reward_addr == wallet_lower):
                                all_transactions.append(tx)
                        print(f"DEBUG: After filtering, {len(all_transactions)} transactions for this wallet")
                    except Exception as e:
                        print(f"ERROR with get_all_transactions: {e}")
                
                if not all_transactions:
                    print(f"WARNING: No transactions found via any database method")

            
            # Process each transaction
            for tx in all_transactions:
                tx_type = tx.get('type', 'transfer').lower()
                tx_status = tx.get('status', 'confirmed').lower()
                amount = float(tx.get('amount', 0))
                fee = float(tx.get('fee', 0))
                from_addr = tx.get('from', '').lower()
                to_addr = tx.get('to', '').lower()
                reward_addr = tx.get('reward_address', '').lower()
                
                # Determine if this is a confirmed or pending transaction
                is_confirmed = (tx_status == 'confirmed')
                
                # Process based on transaction type
                if tx_type == 'reward':
                    # Mining reward - add to available if confirmed
                    if reward_addr == wallet_lower or (from_addr == 'network' and to_addr == wallet_lower):
                        if is_confirmed:
                            available_balance += amount
                            print(f"    → REWARD (confirmed): +{amount}")
                        else:
                            pending_balance += amount
                            print(f"    → REWARD (pending): +{amount}")
                
                elif tx_type == 'fee_distribution':
                    # Fee distribution - add if recipient
                    recipient = tx.get('recipient', '').lower()
                    if recipient == wallet_lower or reward_addr == wallet_lower:
                        if is_confirmed:
                            available_balance += amount
                            print(f"    → FEE DIST (confirmed): +{amount}")
                        else:
                            pending_balance += amount
                            print(f"    → FEE DIST (pending): +{amount}")
                
                else:
                    # Regular transfer (transfer, stake, delegate, gtx_genesis)
                    # Incoming
                    if to_addr == wallet_lower:
                        if is_confirmed:
                            available_balance += amount
                            print(f"    → INCOMING (confirmed): +{amount}")
                        else:
                            pending_balance += amount
                            print(f"    → INCOMING (pending): +{amount}")
                    # Outgoing
                    elif from_addr == wallet_lower:
                        net_amount = amount + fee
                        if is_confirmed:
                            available_balance -= net_amount
                            print(f"    → OUTGOING (confirmed): -{net_amount} (amount: {amount}, fee: {fee})")
                        else:
                            pending_balance -= net_amount
                            print(f"    → OUTGOING (pending): -{net_amount} (amount: {amount}, fee: {fee})")
            
            # Ensure non-negative available balance
            available_balance = max(0.0, available_balance)
            
            print(f"RESULT: available={available_balance:.6f}, pending={pending_balance:.6f}")
            print(f"=== BALANCE RECALCULATION COMPLETE ===\n")
            
            # Update wallet_core.wallets with recalculated balances
            print(f"DEBUG: Updating wallet_core.wallets[{wallet_address[:8]}...]")
            if hasattr(self.app.wallet_core, 'wallets'):
                print(f"  wallet_core.wallets exists: {self.app.wallet_core.wallets is not None}")
                if isinstance(self.app.wallet_core.wallets, dict):
                    print(f"  wallet_core.wallets is dict: True")
                    if wallet_address in self.app.wallet_core.wallets:
                        print(f"  wallet_address in dict: True")
                        # Update all balance fields
                        self.app.wallet_core.wallets[wallet_address]['available_balance'] = available_balance
                        self.app.wallet_core.wallets[wallet_address]['balance'] = available_balance + pending_balance
                        self.app.wallet_core.wallets[wallet_address]['pending_balance'] = pending_balance
                        self.app.wallet_core.wallets[wallet_address]['confirmed_balance'] = available_balance
                        
                        # Verify the update
                        updated_balance = self.app.wallet_core.wallets[wallet_address].get('balance', 'MISSING')
                        updated_pending = self.app.wallet_core.wallets[wallet_address].get('pending_balance', 'MISSING')
                        print(f"  VERIFIED: balance={updated_balance}, pending_balance={updated_pending}")
                        print(f"Updated wallet_core.wallets[{wallet_address[:8]}...] with recalculated balances")
                    else:
                        print(f"  ERROR: wallet_address NOT in dict! Keys: {list(self.app.wallet_core.wallets.keys())}")
                else:
                    print(f"  ERROR: wallet_core.wallets is not dict, it's {type(self.app.wallet_core.wallets)}")
            else:
                print(f"  ERROR: wallet_core.wallets does not exist")
            
            # Update UI immediately
            self._update_balance_display_ui(available_balance, pending_balance, wallet_address)
            
            # Update sidebar
            self._refresh_sidebar_wallets()
            
        except Exception as e:
            print(f"ERROR in recalculate_wallet_balances: {e}")
            import traceback
            traceback.print_exc()
    
    def _update_balance_display_ui(self, available_balance, pending_balance, wallet_address):
        """Update balance card UI with calculated values"""
        try:
            # Update balance text
            self.balance_text.value = f"{available_balance:.6f} LKC"
            self.pending_balance_text.value = f"{pending_balance:+.6f} LKC"
            
            # Color pending balance
            if pending_balance > 0:
                self.pending_balance_text.color = "#00ff00"  # Green
            elif pending_balance < 0:
                self.pending_balance_text.color = "#ff4444"  # Red
            else:
                self.pending_balance_text.color = "#ffd700"  # Yellow
            
            # Update address display
            label = self.app.wallet_core.wallets.get(wallet_address, {}).get('label', 'Wallet') if hasattr(self.app.wallet_core, 'wallets') else 'Wallet'
            addr_text = f"{wallet_address[:12]}...{wallet_address[-6:]}" if len(wallet_address) > 20 else wallet_address
            self.address_text.value = f"{label}: {addr_text}"
            
            # Update the balance card
            if 'balance_card' in self.refs and self.refs['balance_card'].current:
                try:
                    self.refs['balance_card'].current.update()
                except:
                    pass
            
            # Update page
            if hasattr(self.app, 'page'):
                try:
                    self.app.page.update()
                except:
                    pass
        
        except Exception as e:
            print(f"ERROR in _update_balance_display_ui: {e}")
    
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
        
        # Create description based on transaction type
        if tx_type == 'reward':
            reward_address = tx_data.get('reward_address', to_addr)
            description = f"Reward → {reward_address[:8]}..."
        elif tx_type == 'fee_distribution':
            description = "Fee Distribution"
        else:
            # For regular transfers
            if is_incoming:
                description = f"From: {from_addr[:8]}..."
            else:
                description = f"To: {to_addr[:8]}..."
        
        # Create minimal transaction item
        return ft.Container(
            content=ft.ListTile(
                leading=ft.Icon(
                    ft.Icons.ATTACH_MONEY if tx_type == 'reward' else 
                    (ft.Icons.ARROW_UPWARD if not is_incoming else ft.Icons.ARROW_DOWNWARD),
                    color=amount_color,
                    size=20
                ),
                title=ft.Row([
                    ft.Text(f"{amount_prefix}{amount:.6f} LKC", 
                        color=amount_color, 
                        size=14,
                        weight="bold",
                        expand=True),
                    ft.Text(status_text, color=status_color, size=12),
                ]),
                subtitle=ft.Row([
                    ft.Text(date_str, size=11, color="#a8a8a8", expand=True),
                    ft.Text(description if not memo else memo, size=11, color="#a8a8a8"),
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
            from_addr = tx_data.get('from', '')
            
            # For rewards, check if the reward address matches current wallet
            if tx_type == 'reward':
                reward_address = tx_data.get('reward_address', to_addr)
                return reward_address.lower() == current_address.lower()
            
            # For fee distributions, check if the recipient matches
            if tx_type == 'fee_distribution':
                recipient_address = tx_data.get('recipient', to_addr)
                return recipient_address.lower() == current_address.lower()
            
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
            on_import_wallet=self.on_import_wallet,
            on_lock=self.on_lock,
            on_settings=self.on_settings,
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
        """Update stats asynchronously to avoid blocking UI"""
        def load_stats():
            stats = []
            
            try:
                if hasattr(self.app, 'wallet_core') and self.app.wallet_core:
                    is_unlocked = (
                        getattr(self.app.wallet_core, 'is_unlocked', False) or
                        getattr(self.app.wallet_core, 'is_locked', True) == False or
                        getattr(self.app, 'is_locked', True) == False
                    )
                    
                    if is_unlocked:
                        # Block height - get from blockchain asynchronously
                        try:
                            if hasattr(self.app, 'blockchain_manager'):
                                height = self.app.blockchain_manager.get_blockchain_height()
                                stats.append(self.create_stat_item("📦", f"{height}", "Height"))
                            else:
                                stats.append(self.create_stat_item("📦", "0", "Height"))
                        except:
                            stats.append(self.create_stat_item("📦", "0", "Height"))
                        
                        # Network status - check the connection
                        try:
                            network_status = self._check_network_status()
                            if network_status['connected']:
                                stats.append(self.create_stat_item("🟢", "Online", "Network"))
                            else:
                                stats.append(self.create_stat_item("🔴", "Offline", "Network"))
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
            
            def update_ui():
                self.stats_row.controls = stats
                if hasattr(self.app, 'page'):
                    self.app.page.update()
            
            if hasattr(self.app, 'page'):
                self.app.page.run_thread(update_ui)
        
        threading.Thread(target=load_stats, daemon=True).start()

    def refresh_network_status(self):
        """Manually refresh network status"""
        try:
            network_status = self._check_network_status()
            
            if network_status['connected']:
                if hasattr(self.app, 'show_snackbar'):
                    self.app.show_snackbar("Connected to blockchain", "success")
            else:
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
                        # Start with 0 balance until sync completes to avoid showing incorrect cached balances
                        balance = 0.0  # wallet_info.get('balance', 0) - don't trust cached balance
                        pending_balance = wallet_info.get('pending_balance', 0)
                        address = wallet_info.get('address', 'No wallet')
                        label = wallet_info.get('label', 'Wallet')
                        
                        self.balance_text.value = f"{balance:.6f} LKC"
                        self.balance_text.update()
                        
                        if pending_balance != 0:
                            sign = "+" if pending_balance > 0 else ""
                            self.pending_balance_text.value = f"Pending Balance: {sign}{pending_balance:.6f}"
                        else:
                            self.pending_balance_text.value = ""
                        self.pending_balance_text.update()
                        
                        self.address_text.value = f"{label}: {address[:12]}...{address[-6:]}" if len(address) > 20 else address
                        self.address_text.update()
                    else:
                        self.balance_text.value = "0.00 LKC"
                        self.balance_text.update()
                        self.pending_balance_text.value = ""
                        self.pending_balance_text.update()
                        self.address_text.value = "No wallet data"
                        self.address_text.update()
                    
                else:
                    self.balance_text.value = "0.00 LKC"
                    self.pending_balance_text.value = ""
                    self.address_text.value = "Wallet Locked"
                
                self.update_quick_stats()
                self.refresh_transaction_history()
                self._refresh_sidebar_wallets()  # Refresh sidebar when wallet data updates
            
        except Exception as e:
            self.balance_text.value = "0.00 LKC"
            self.pending_balance_text.value = ""
            self.address_text.value = "Failed to load"
            print(f"Error updating wallet data: {e}")
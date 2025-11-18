import flet as ft
import threading
from datetime import datetime
import time
class WalletPage:
    def __init__(self, app, on_send, on_receive, on_export_key, on_create_wallet, on_import_wallet):
        self.app = app
        self.on_send = on_send
        self.on_receive = on_receive
        self.on_export_key = on_export_key
        self.on_create_wallet = on_create_wallet
        self.on_import_wallet = on_import_wallet
        
        # Sidebar state
        self.sidebar_collapsed = False
        self.sidebar_width = 280
        self.sidebar_collapsed_width = 60
        # Refs for UI elements
        self.refs = {}  # Add this line
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
        self.transactions_list = ft.ListView(spacing=8, height=200, expand=True)
        self.app.update_transaction_history()
        
        return ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Text("📊 Transactions", size=16, weight="bold", color="#f8d7da", expand=True),
                    ft.IconButton(
                        icon=ft.Icons.REFRESH,
                        icon_color="#f8d7da",
                        icon_size=16,
                        on_click=lambda e: self.app.update_transaction_history(),
                        tooltip="Refresh",
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
    
    
    
    def _show_transaction_details(self, tx_data):
        """Show transaction details in a dialog"""
        tx_type = tx_data.get('type', 'transfer')
        amount = tx_data.get('amount', 0)
        from_addr = tx_data.get('from', 'Unknown')
        to_addr = tx_data.get('to', 'Unknown')
        status = tx_data.get('status', 'unknown')
        timestamp = tx_data.get('timestamp', 0)
        tx_hash = tx_data.get('hash', 'Unknown')
        memo = tx_data.get('memo', '')
        fee = tx_data.get('fee', 0)
        
        # Determine if incoming or outgoing
        our_addresses = [w['address'].lower() for w in self.app.wallet_core.wallets]
        is_incoming = tx_type == 'reward' or (to_addr and to_addr.lower() in our_addresses)
        
        color = "#00ff00" if is_incoming else "#ff4444"
        direction = "Received" if is_incoming else "Sent"
        
        date_str = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S") if timestamp else "Unknown"
        
        # Create details content
        details_content = ft.Column([
            self._create_detail_row("Type:", f"{tx_type.title()} ({direction})", "#f8d7da"),
            self._create_detail_row("Amount:", f"{amount:.6f} LUN", color),
            self._create_detail_row("From:", from_addr, "#f8d7da"),
            self._create_detail_row("To:", to_addr, "#f8d7da"),
            self._create_detail_row("Status:", status.title(), color),
            self._create_detail_row("Date:", date_str, "#f8d7da"),
            self._create_detail_row("TX Hash:", tx_hash, "#a8a8a8"),
            self._create_detail_row("Fee:", f"{fee:.6f} LUN", "#f8d7da"),
            self._create_detail_row("Memo:", memo if memo else "None", "#a8a8a8"),
        ], spacing=8)
        
        def close_dialog(e):
            self.app.page.dialog.open = False
            self.app.page.update()
        
        def copy_tx_hash(e):
            self.app.page.set_clipboard(tx_hash)
            if hasattr(self.app, 'show_snackbar'):
                self.app.show_snackbar("Transaction hash copied!", "success")
        
        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Transaction Details", color="#f8d7da"),
            content=ft.Container(
                content=details_content,
                width=400,
                padding=10
            ),
            actions=[
                ft.TextButton("Copy TX Hash", on_click=copy_tx_hash, style=ft.ButtonStyle(color="#dc3545")),
                ft.TextButton("Close", on_click=close_dialog, style=ft.ButtonStyle(color="#f8d7da")),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
            bgcolor="#2c1a1a"
        )
        
        self.app.page.dialog = dialog
        dialog.open = True
        self.app.page.update()
    
    def _create_detail_row(self, label, value, color):
        return ft.Container(
            content=ft.Row([
                ft.Text(label, size=12, color="#f8d7da", weight="bold", width=80),
                ft.Text(value, size=12, color=color, expand=True, selectable=True),
            ]),
            padding=ft.padding.symmetric(vertical=2)
        )
    
    def manual_sync(self, e=None):
        self.sync_status.value = "🔄 Checking network..."
        if self.app.page:
            self.app.page.update()
        
        def sync_thread():
            try:
                # First check network connection
                network_status = self._check_network_status()
                if not network_status['connected']:
                    self.sync_status.value = "❌ Offline"
                    if hasattr(self.app, 'show_snackbar'):
                        self.app.show_snackbar("Cannot connect to blockchain network", "error")
                    if self.app.page:
                        self.app.page.update()
                    return
                
                # Network is connected, proceed with sync
                self.sync_status.value = "🔄 Syncing..."
                if self.app.page:
                    self.app.page.update()
                
                # Use the blockchain sync method
                if hasattr(self.app, 'start_blockchain_sync'):
                    self.app.start_blockchain_sync()
                    
                    # Wait a bit for sync to start
                    time.sleep(2)
                    
                    self.sync_status.value = "✅ Syncing..."
                    if hasattr(self.app, 'show_snackbar'):
                        self.app.show_snackbar("Sync started with blockchain", "info")
                else:
                    # Fallback to wallet core sync
                    if hasattr(self.app, 'wallet_core') and self.app.wallet_core:
                        success = self.app.wallet_core.scan_blockchain(force_full_scan=True)
                        if success:
                            self.sync_status.value = "✅ Synced"
                            if hasattr(self.app, 'show_snackbar'):
                                self.app.show_snackbar("Sync completed", "success")
                        else:
                            self.sync_status.value = "❌ Failed"
                            if hasattr(self.app, 'show_snackbar'):
                                self.app.show_snackbar("Sync failed", "error")
                
                # Update UI
                self.update_quick_stats()
                self.app.update_transaction_history()
                
                if self.app.page:
                    self.app.page.update()
                
            except Exception as e:
                self.sync_status.value = "❌ Error"
                if hasattr(self.app, 'show_snackbar'):
                    self.app.show_snackbar(f"Sync error: {str(e)}", "error")
                if self.app.page:
                    self.app.page.update()
        
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
                self.app.update_transaction_history()
                self._refresh_sidebar_wallets()  # Refresh sidebar when wallet data updates
            
        except Exception as e:
            self.balance_text.value = "Error"
            self.address_text.value = "Failed to load"
            self.sync_status.value = "❌ Error"
            print(f"Error updating wallet data: {e}")

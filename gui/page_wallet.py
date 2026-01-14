import flet as ft
from tqdm import tqdm
from rich.console import Console
console = Console()
import threading
from datetime import datetime
import time
from utils import calculate_wallet_balances
import json
import os

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
        self.balance_text = ft.Text("--.-- LKC", size=28, weight="bold", color="#999999")
        self.pending_balance_text = ft.Text("--.-- LKC", size=16, weight="500", color="#999999")
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
        
        # Populate sidebar with wallets from app.wallet_core
        self._populate_sidebar_wallets()
        
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
                on_click=lambda e: self.app.show_create_wallet(),
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
    
    def _populate_sidebar_wallets(self):
        """Populate the sidebar with wallets using direct transaction tally for balances"""
        try:
            if 'sidebar_wallets_list' not in self.refs:
                print("DEBUG: sidebar_wallets_list ref not found")
                return

            sidebar_list = self.refs['sidebar_wallets_list'].current
            if not sidebar_list:
                print("DEBUG: sidebar_list is None")
                return

            print(f"DEBUG: Populating sidebar with wallets using transaction tally (force clear)")

            # サイドバーUIを完全クリア
            sidebar_list.controls.clear()

            # ウォレットリストをwallet_coreから取得
            wallet_dict = getattr(self.app.wallet_core, "wallets", {})
            for address, wdata in wallet_dict.items():
                # 残高をトランザクション履歴から計算
                confirmed_balance, pending_balance = self._calculate_balance_from_transactions(address)
                label = wdata.get("label", address[:8] + "..." + address[-6:] if len(address) > 16 else address)
                wallet_item = self._create_sidebar_wallet_item({
                    'address': address,
                    'label': label,
                    'balance': confirmed_balance + pending_balance,
                    'confirmed_balance': confirmed_balance,
                    'pending_balance': pending_balance
                }, len(sidebar_list.controls))
                sidebar_list.controls.append(wallet_item)
                print(f"DEBUG: [SIDEBAR] {label} ({address[:12]}...): confirmed={confirmed_balance}, pending={pending_balance}")
            print("[bold green]Sidebar Wallets Update Complete (transaction tally)")
        except Exception as e:
            print(f"ERROR: Error populating sidebar: {e}")
            import traceback
            traceback.print_exc()
    
    def _toggle_sidebar(self, e):
        """Toggle sidebar collapsed state"""
        self.sidebar_collapsed = not self.sidebar_collapsed
        self._refresh_sidebar_wallets()
        if hasattr(self.app, 'page'):
            self.app.page.update()
    
    def _save_wallets(self):
        """Save wallets to a JSON file."""
        try:
            with open(self.WALLET_STORAGE_FILE, "w") as f:
                json.dump(self.wallets, f, indent=4)
            print("DEBUG: Wallets saved successfully.")
        except Exception as e:
            print(f"ERROR: Failed to save wallets: {e}")


    def _refresh_sidebar_wallets(self):
        """Refresh the wallets list in the sidebar, ensuring wallets are always displayed. Wallet cardと同じ変数でサイドバーも更新"""
        with self.sidebar_update_lock:
            if 'sidebar_wallets_list' not in self.refs:
                return
            sidebar_list = self.refs['sidebar_wallets_list'].current
            if not sidebar_list:
                return
            try:
                if hasattr(self.app, 'wallet_core') and self.app.wallet_core:
                    if hasattr(self.app.wallet_core, 'wallets') and isinstance(self.app.wallet_core.wallets, dict):
                        print(f"\n=== REFRESHING SIDEBAR: Found {len(self.app.wallet_core.wallets)} wallets ===")
                        sidebar_addresses = set()
                        for control in sidebar_list.controls:
                            if hasattr(control, 'data'):
                                if isinstance(control.data, dict) and 'address' in control.data:
                                    sidebar_addresses.add(control.data['address'])
                        print(f"DEBUG: Wallets currently in sidebar: {sidebar_addresses}")
                        current_addr = getattr(self.app.wallet_core, 'current_wallet_address', None)
                        for address, wallet_data in self.app.wallet_core.wallets.items():
                            confirmed_balance = wallet_data.get('confirmed_balance', 0.0)
                            pending_balance = wallet_data.get('pending_balance', 0.0)
                            existing_wallet = None
                            for w in sidebar_list.controls:
                                if hasattr(w, 'data'):
                                    if isinstance(w.data, dict) and w.data.get('address') == address:
                                        existing_wallet = w
                                        break
                            if existing_wallet:
                                print(f"DEBUG: Wallet {address[:12]}... already in sidebar, updating display")
                                # サイドバーのウォレットがcurrent_wallet_addressならwallet cardと同じ変数で更新
                                if current_addr and address == current_addr:
                                    self.update_balance_card(confirmed_balance, pending_balance)
                                self._update_sidebar_wallet_display(existing_wallet, confirmed_balance, pending_balance)
                            else:
                                if address not in sidebar_addresses:
                                    print(f"DEBUG: Adding new wallet {address[:12]}... to sidebar")
                                    label = wallet_data.get('label', 'Wallet')
                                    wallet_item = self._create_sidebar_wallet_item({
                                        'address': address,
                                        'label': label,
                                        'balance': confirmed_balance + pending_balance,
                                        'confirmed_balance': confirmed_balance,
                                        'pending_balance': pending_balance
                                    }, len(sidebar_list.controls))
                                    sidebar_list.controls.append(wallet_item)
                                else:
                                    print(f"DEBUG: Wallet {address[:12]}... already in sidebar (by address check), skipping")
                        print(f"=== SIDEBAR REFRESH COMPLETE ===\n")
            except Exception as e:
                print(f"Error refreshing sidebar wallets: {e}")
                import traceback
                traceback.print_exc()
    
    def _update_sidebar_wallet_display(self, wallet_item, confirmed_balance, pending_balance):
        """Update the visual text display of a sidebar wallet item with new balances"""
        try:
            # Format balance display
            if confirmed_balance is None:
                balance_display = "--.--"
                balance_color = "#999999"
            else:
                balance_display = f"{confirmed_balance:.6f}"
                balance_color = "#f8d7da"
            
            if pending_balance is None:
                pending_display = "--.--"
                pending_color = "#999999"
            else:
                pending_display = f"{pending_balance:+.6f}"
                pending_color = "#00ff00" if pending_balance > 0 else ("#ff4444" if pending_balance < 0 else "#ffd700")
            
            # Get the content column
            if hasattr(wallet_item.content, 'controls') and len(wallet_item.content.controls) > 0:
                # The first row contains the wallet info
                row = wallet_item.content.controls[0]
                
                if hasattr(row, 'controls') and len(row.controls) > 1:
                    # The second control in the row is the Column with label, balance, pending
                    info_column = row.controls[1]
                    
                    if hasattr(info_column, 'controls') and len(info_column.controls) >= 2:
                        # Update balance text (second control)
                        info_column.controls[1].value = f"{balance_display} LKC"
                        info_column.controls[1].color = balance_color
                        
                        # Update pending text (third control) if it exists
                        if len(info_column.controls) > 2:
                            info_column.controls[2].value = f"Pending: {pending_display}"
                            info_column.controls[2].color = pending_color
                        
                        # Update the entire column
                        info_column.update()
            
            # Also update balance card if this is the current wallet
            if hasattr(self.app.wallet_core, 'current_wallet_address') and hasattr(wallet_item, 'data'):
                if wallet_item.data.get('address') == self.app.wallet_core.current_wallet_address:
                    # Use the unified update_balance_card function
                    self.update_balance_card(confirmed_balance, pending_balance)
            
            print(f"DEBUG: Updated sidebar + card - confirmed={balance_display}, pending={pending_display}")
        except Exception as e:
            print(f"DEBUG: Error updating sidebar wallet display: {e}")
            import traceback
            traceback.print_exc()
    
    def _calculate_balance_from_transactions(self, wallet_address):
        """Calculate balance from loaded transaction history"""
        try:
            confirmed_balance = 0.0
            pending_balance = 0.0
            wallet_addr_lower = wallet_address.lower()
            
            # Get all transactions for this wallet from database
            all_txs = []
            if hasattr(self.app, 'database'):
                try:
                    # Try multiple methods to get transactions
                    if hasattr(self.app.database, 'get_wallet_transactions'):
                        all_txs = self.app.database.get_wallet_transactions(wallet_address, limit=10000)
                    elif hasattr(self.app.database, 'get_transactions'):
                        all_txs = self.app.database.get_transactions(wallet_address)
                    else:
                        print(f"DEBUG: No transaction retrieval method found on database")
                except Exception as db_err:
                    print(f"DEBUG: Error getting transactions from database: {db_err}")
            
            print(f"DEBUG: Got {len(all_txs)} transactions for {wallet_address[:12]}...")
            
            # Get pending transactions from mempool
            pending_txs = []
            if hasattr(self.app, 'get_mempool_manager'):
                try:
                    mempool_mgr = self.app.get_mempool_manager()
                    if mempool_mgr:
                        pending_txs = mempool_mgr.get_pending_transactions(wallet_address)
                    print(f"DEBUG: Got {len(pending_txs) if pending_txs else 0} pending transactions from mempool")
                except Exception as e:
                    print(f"DEBUG: Error getting pending transactions: {e}")
            elif hasattr(self.app, 'mempool_manager') and self.app.mempool_manager:
                try:
                    pending_txs = self.app.mempool_manager.get_pending_transactions(wallet_address)
                    print(f"DEBUG: Got {len(pending_txs) if pending_txs else 0} pending transactions from mempool")
                except Exception as e:
                    print(f"DEBUG: Error getting pending transactions: {e}")
            
            # Calculate confirmed balance
            for tx in all_txs:
                tx_status = tx.get('status', 'confirmed').lower()
                if tx_status != 'confirmed':
                    continue
                
                # Handle both field name formats
                tx_from = tx.get('from', tx.get('from_address', '')).lower()
                tx_to = tx.get('to', tx.get('to_address', '')).lower()
                reward_addr = tx.get('reward_address', '').lower()
                tx_type = tx.get('type', tx.get('tx_type', 'transfer')).lower()
                amount = float(tx.get('amount', 0))
                fee = float(tx.get('fee', 0))
                
                # Mining reward
                if tx_type == 'reward':
                    if (tx_to == wallet_addr_lower or reward_addr == wallet_addr_lower):
                        confirmed_balance += amount
                        print(f"  ✓ Reward: +{amount}")
                # Fee distribution (mining reward variant)
                elif tx_type == 'fee_distribution':
                    recipient_addr = tx.get('recipient', '').lower()
                    if (tx_to == wallet_addr_lower or reward_addr == wallet_addr_lower or recipient_addr == wallet_addr_lower):
                        confirmed_balance += amount
                        print(f"  ✓ Fee distribution: +{amount}")
                # Incoming transfer
                elif tx_to == wallet_addr_lower:
                    confirmed_balance += amount
                    print(f"  ✓ Transfer in: +{amount}")
                # Outgoing transfer
                elif tx_from == wallet_addr_lower:
                    confirmed_balance -= (amount + fee)
                    print(f"  ✓ Transfer out: -{amount} - {fee} fee")
            
            # Calculate pending balance
            for tx in pending_txs:
                # Handle both field name formats
                tx_from = tx.get('from', tx.get('from_address', '')).lower()
                tx_to = tx.get('to', tx.get('to_address', '')).lower()
                reward_addr = tx.get('reward_address', '').lower()
                tx_type = tx.get('type', tx.get('tx_type', 'transfer')).lower()
                amount = float(tx.get('amount', 0))
                fee = float(tx.get('fee', 0))

                # Pending reward
                if tx_type == 'reward':
                    if (tx_to == wallet_addr_lower or reward_addr == wallet_addr_lower):
                        pending_balance += amount
                        print(f"  ⏳ Pending Reward: +{amount}")
                # Pending fee distribution
                elif tx_type == 'fee_distribution':
                    recipient_addr = tx.get('recipient', '').lower()
                    if (tx_to == wallet_addr_lower or reward_addr == wallet_addr_lower or recipient_addr == wallet_addr_lower):
                        pending_balance += amount
                        print(f"  ⏳ Pending Fee distribution: +{amount}")
                # Outgoing pending
                elif tx_from == wallet_addr_lower:
                    pending_balance -= (amount + fee)
                # Incoming pending
                elif tx_to == wallet_addr_lower:
                    pending_balance += amount
            
            confirmed_balance = max(0.0, confirmed_balance)
            
            print(f"DEBUG: Calculated balance - confirmed={confirmed_balance:.6f}, pending={pending_balance:.6f}")
            return confirmed_balance, pending_balance
            
        except Exception as e:
            print(f"DEBUG: Error calculating balance from transactions: {e}")
            import traceback
            traceback.print_exc()
            return None, None
    
    def _get_wallet_balances(self, wallet_address):
        """Get balance by directly tallying from all transactions (DB+pending)."""
        confirmed, pending = self._calculate_balance_from_transactions(wallet_address)
        return confirmed or 0.0, pending or 0.0
    
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
        
        # Get cached balance or show placeholder
        confirmed = wallet.get('confirmed_balance', wallet.get('balance', None))
        pending = wallet.get('pending_balance', None)
        
        # Format balance display - use placeholder if not loaded
        if confirmed is None:
            balance_display = "--.--"
            balance_color = "#999999"
        else:
            balance_display = f"{confirmed:.6f}"
            balance_color = "#f8d7da"
        
        if pending is None:
            pending_display = "--.--"
            pending_color = "#999999"
        else:
            pending_display = f"{pending:+.6f}"
            pending_color = "#00ff00" if pending > 0 else ("#ff4444" if pending < 0 else "#ffd700")
        
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
                        alignment=ft.Alignment(0, 0)
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
                tooltip=f"{wallet['label']}\nBalance: {balance_display} LKC\nPending: {pending_display} LKC",
                data=wallet  # Store the wallet dict for proper duplicate detection
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
                            alignment=ft.Alignment(0, 0)
                        ),
                        ft.Column([
                            ft.Text(wallet['label'], 
                                size=14, 
                                color="#ffffff",
                                weight="bold"),
                            ft.Text(f"{balance_display} LKC", 
                                size=10, 
                                color=balance_color),
                            ft.Text(f"Pending: {pending_display}", 
                                size=8, 
                                color=pending_color),
                        ], spacing=2, expand=True)
                    ], spacing=10),
                ]),
                padding=10,
                bgcolor="#2c1a1a" if is_selected else "transparent",
                border=ft.border.all(1, "#dc3545" if is_selected else "transparent"),
                border_radius=8,
                on_click=lambda e, idx=index: self._on_wallet_select(idx),
                data=wallet  # Store the wallet dict for proper duplicate detection
            )
    def _on_wallet_select(self, index):
        """Handle wallet selection from sidebar (スキャンは行わずキャッシュのみ参照)"""
        try:
            # サイドバー選択インデックスを永続化
            if hasattr(self.app, 'selected_wallet_index'):
                self.app.selected_wallet_index = index

            # Get the selected wallet address
            selected_address = None
            if hasattr(self.app, 'wallet_core') and self.app.wallet_core:
                if isinstance(self.app.wallet_core.wallets, dict):
                    wallet_addresses = list(self.app.wallet_core.wallets.keys())
                    if index < len(wallet_addresses):
                        selected_address = wallet_addresses[index]
                        
                        # Ensure wallet has private_key before switching
                        wallet_obj = self.app.wallet_core.wallets.get(selected_address)
                        if wallet_obj and 'private_key' not in wallet_obj and hasattr(self.app.wallet_core, 'private_key'):
                            wallet_obj['private_key'] = self.app.wallet_core.private_key
                        
                        # Switch to the selected wallet in the core
                        if hasattr(self.app.wallet_core, 'switch_wallet'):
                            self.app.wallet_core.switch_wallet(selected_address)
                        self.app.wallet_core.current_wallet_address = selected_address
                        print(f"DEBUG: Switched to wallet: {selected_address}")

            if not selected_address:
                return

            # サイドバーの選択状態を即時反映（色のみ）
            if 'sidebar_wallets_list' in self.refs and self.refs['sidebar_wallets_list'].current:
                sidebar_list = self.refs['sidebar_wallets_list'].current
                for i, control in enumerate(sidebar_list.controls):
                    # 色だけ即時反映、残高はrecalculate_wallet_balancesで更新
                    if hasattr(control, 'data') and (
                        (isinstance(control.data, dict) and control.data.get('address') == selected_address)
                        or control.data == index
                    ):
                        if self.sidebar_collapsed:
                            if hasattr(control.content, 'controls') and len(control.content.controls) > 0:
                                control.content.controls[0].bgcolor = "#dc3545"
                        else:
                            control.bgcolor = "#2c1a1a"
                            control.border = ft.border.all(1, "#dc3545")
                    else:
                        if self.sidebar_collapsed:
                            if hasattr(control.content, 'controls') and len(control.content.controls) > 0:
                                control.content.controls[0].bgcolor = "#5c2e2e"
                        else:
                            control.bgcolor = "transparent"
                            control.border = ft.border.all(1, "transparent")
                    control.update()


            # 残高・UIは選択ウォレットのみlunalibから取得し、サイドバーとカードを即時更新（他は更新しない）
            confirmed_balance, pending_balance = self._get_wallet_balances(selected_address)
            # サイドバー該当項目のみ更新
            if 'sidebar_wallets_list' in self.refs and self.refs['sidebar_wallets_list'].current:
                sidebar_list = self.refs['sidebar_wallets_list'].current
                for control in sidebar_list.controls:
                    if hasattr(control, 'data') and isinstance(control.data, dict) and control.data.get('address') == selected_address:
                        self._update_sidebar_wallet_display(control, confirmed_balance, pending_balance)
                        break
            # ウォレットカードも同じ値で更新
            self._update_balance_display_ui(confirmed_balance, pending_balance, selected_address)

            # バックグラウンドで選択状態のみ保存（スキャンはしない）
            def background_operations():
                try:
                    self.app.save_wallet_data(force_save=True)
                except Exception as e:
                    print(f"DEBUG: Error saving wallet selection: {e}")
            threading.Thread(target=background_operations, daemon=True).start()
        except Exception as e:
            print(f"DEBUG: Error in _on_wallet_select: {e}")
            import traceback
            traceback.print_exc()
    
    # def _should_scan_wallet(self, wallet_address):
    #     """
    #     5分ごとのスキャン判定はcore.pyのタイマーで一括管理するため、ここでは使わない
    #     """
    #     return False
    
    def _show_balance_placeholder(self, wallet_address):
        """Show placeholder balance while loading"""
        self.balance_text.value = "--.-- LKC"
        self.balance_text.color = "#999999"
        self.pending_balance_text.value = "--.-- LKC"
        self.pending_balance_text.color = "#999999"
        
        # Update address display
        label = self.app.wallet_core.wallets.get(wallet_address, {}).get('label', 'Wallet') if hasattr(self.app.wallet_core, 'wallets') else 'Wallet'
        addr_text = f"{wallet_address[:12]}...{wallet_address[-6:]}" if len(wallet_address) > 20 else wallet_address
        self.address_text.value = f"{label}: {addr_text}"
    
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
        """Update balance card display using lunalib WalletManager API (always latest)"""
        try:
            current_addr = None
            if hasattr(self.app, 'wallet_core') and self.app.wallet_core:
                if hasattr(self.app.wallet_core, 'current_wallet_address'):
                    current_addr = self.app.wallet_core.current_wallet_address
            wallet_data = None
            if hasattr(self.app.wallet_core, 'wallets') and current_addr:
                wallet_data = self.app.wallet_core.wallets.get(current_addr, None)
            if wallet_data is None and hasattr(self.app.wallet_core, 'wallets'):
                for w in self.app.wallet_core.wallets.values():
                    if w.get('address') == current_addr:
                        wallet_data = w
                        break
            # None値のフォーマット防止
            confirmed = confirmed_balance
            pending = pending_balance
            if confirmed is None and wallet_data:
                confirmed = wallet_data.get('confirmed_balance', wallet_data.get('balance', None))
            if pending is None and wallet_data:
                pending = wallet_data.get('pending_balance', None)
            if confirmed is None:
                self.balance_text.value = "--.-- LKC"
                self.balance_text.color = "#999999"
            else:
                try:
                    self.balance_text.value = f"{float(confirmed):.6f} LKC"
                    self.balance_text.color = "#f8d7da"
                except Exception:
                    self.balance_text.value = "--.-- LKC"
                    self.balance_text.color = "#999999"
            if pending is None:
                self.pending_balance_text.value = "--.-- LKC"
                self.pending_balance_text.color = "#999999"
            else:
                try:
                    self.pending_balance_text.value = f"Pending: {float(pending):+.6f}"
                    self.pending_balance_text.color = "#00ff00" if float(pending) > 0 else ("#ff4444" if float(pending) < 0 else "#ffd700")
                except Exception:
                    self.pending_balance_text.value = "--.-- LKC"
                    self.pending_balance_text.color = "#999999"
            # アドレス表示
            label = wallet_data.get('label', 'Wallet') if wallet_data else 'Wallet'
            addr_text = f"{current_addr[:12]}...{current_addr[-6:]}" if current_addr and len(current_addr) > 20 else (current_addr or "")
            self.address_text.value = f"{label}: {addr_text}"
            # 強制UI更新
            try:
                if 'balance_card' in self.refs:
                    card_ref = self.refs['balance_card'].current
                    if card_ref:
                        card_ref.update()
            except Exception as ref_error:
                print(f"DEBUG CARD: Error accessing balance_card ref: {ref_error}")
            if hasattr(self.app, 'page') and self.app.page:
                try:
                    self.app.page.update()
                except Exception as page_error:
                    print(f"DEBUG CARD: Error updating page: {page_error}")
        except Exception as e:
            print(f"ERROR in update_balance_card: {e}")
            import traceback
            traceback.print_exc()
            self.balance_text.value = "--.-- LKC"
            self.balance_text.color = "#999999"
            self.pending_balance_text.value = "--.-- LKC"
            self.pending_balance_text.color = "#999999"
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
                        # IMPORTANT: Try get_all_transactions FIRST because get_wallet_transactions
                        # has a 100-transaction limit in lunalib. Always prefer get_all_transactions.
                        db_methods = ['get_all_transactions', 'get_transactions', 'get_wallet_transactions']
                        for method in db_methods:
                            if hasattr(self.app.database, method):
                                try:
                                    if method == 'get_all_transactions':
                                        all_txs = getattr(self.app.database, method)()
                                        print(f"DEBUG: Database returned {len(all_txs)} total transactions (NO LIMIT)")
                                        
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
                
                print(f"DEBUG: Total transactions from database: {len(all_transactions)}")
                
                # Filter transactions specifically for the current wallet
                filtered_transactions = []
                for tx in all_transactions:
                    if self._transaction_involves_wallet(tx, current_address):
                        filtered_transactions.append(tx)
                
                print(f"DEBUG: After filtering database: {len(filtered_transactions)} transactions")
                
                # IMPORTANT: Also load pending transactions from mempool that aren't in the database yet
                if hasattr(self.app, 'get_mempool_manager'):
                    try:
                        print(f"DEBUG: Loading pending transactions from mempool for {current_address[:12]}...")
                        mempool_mgr = self.app.get_mempool_manager()
                        if mempool_mgr:
                            pending_txs = mempool_mgr.get_pending_transactions(current_address)
                            print(f"DEBUG: mempool_manager.get_pending_transactions() returned: {type(pending_txs)}")
                            if pending_txs:
                                print(f"DEBUG: Found {len(pending_txs)} pending transactions in mempool")
                                for tx in pending_txs:
                                    # Add pending status if not already present
                                    if 'status' not in tx or tx.get('status') != 'pending':
                                        tx['status'] = 'pending'
                                    # Check if this transaction is already in our list (avoid duplicates)
                                    tx_hash = tx.get('hash', '')
                                    already_exists = any(t.get('hash') == tx_hash for t in filtered_transactions)
                                    if not already_exists:
                                        filtered_transactions.append(tx)
                                        print(f"  Added pending: {tx_hash[:8]}... (status=pending)")
                            else:
                                print(f"DEBUG: No pending transactions in mempool (returned: {pending_txs})")
                        else:
                            print(f"DEBUG: mempool_manager is None")
                    except Exception as e:
                        print(f"DEBUG: Error loading pending transactions: {e}")
                        import traceback
                        traceback.print_exc()
                elif hasattr(self.app, 'mempool_manager') and self.app.mempool_manager:
                    try:
                        print(f"DEBUG: Loading pending transactions from mempool for {current_address[:12]}...")
                        pending_txs = self.app.mempool_manager.get_pending_transactions(current_address)
                        print(f"DEBUG: mempool_manager.get_pending_transactions() returned: {type(pending_txs)}")
                        if pending_txs:
                            print(f"DEBUG: Found {len(pending_txs)} pending transactions in mempool")
                            for tx in pending_txs:
                                # Add pending status if not already present
                                if 'status' not in tx or tx.get('status') != 'pending':
                                    tx['status'] = 'pending'
                                # Check if this transaction is already in our list (avoid duplicates)
                                tx_hash = tx.get('hash', '')
                                already_exists = any(t.get('hash') == tx_hash for t in filtered_transactions)
                                if not already_exists:
                                    filtered_transactions.append(tx)
                                    print(f"  Added pending: {tx_hash[:8]}... (status=pending)")
                        else:
                            print(f"DEBUG: No pending transactions in mempool (returned: {pending_txs})")
                    except Exception as e:
                        print(f"DEBUG: Error loading pending transactions: {e}")
                        import traceback
                        traceback.print_exc()
                else:
                    print(f"DEBUG: mempool_manager not available")
                
                print(f"DEBUG: Total transactions (confirmed + pending): {len(filtered_transactions)}")
                
                # Sort by timestamp (newest first) and show ALL transactions (no limit)
                filtered_transactions.sort(key=lambda x: x.get('timestamp', 0), reverse=True)
                
                # Note: Balance recalculation is now done in _on_wallet_select() instead
                # to avoid duplicate sidebar refreshes during wallet selection
                
                def update_ui():
                    self.transactions_list.controls.clear()
                    
                    if filtered_transactions:
                        # Compress sequential reward transactions
                        compressed_transactions = self._compress_sequential_rewards(filtered_transactions)
                        
                        for tx in compressed_transactions:
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
        Recalculate and display balance for a specific wallet.
        This is called after blockchain scans to update the display with fresh data.
        サイドバーとカードの残高計算を一元化。
        """
        try:
            # すべてのウォレットの残高を一括計算
            if hasattr(self.app.wallet_core, 'wallets') and isinstance(self.app.wallet_core.wallets, dict):
                for addr in self.app.wallet_core.wallets.keys():
                    confirmed_balance, pending_balance = self._get_wallet_balances(addr)
                    self.app.wallet_core.wallets[addr]['available_balance'] = confirmed_balance
                    self.app.wallet_core.wallets[addr]['balance'] = confirmed_balance + pending_balance
                    self.app.wallet_core.wallets[addr]['pending_balance'] = pending_balance
                    self.app.wallet_core.wallets[addr]['confirmed_balance'] = confirmed_balance
            # UI更新
            if hasattr(self.app.wallet_core, 'current_wallet_address'):
                current_addr = self.app.wallet_core.current_wallet_address
                if current_addr:
                    confirmed_balance = self.app.wallet_core.wallets[current_addr].get('confirmed_balance', 0.0)
                    pending_balance = self.app.wallet_core.wallets[current_addr].get('pending_balance', 0.0)
                    self._update_balance_display_ui(confirmed_balance, pending_balance, current_addr)
            self._refresh_sidebar_wallets()
            if hasattr(self.app, 'page'):
                try:
                    self.app.page.update()
                    print(f"DEBUG: Page updated after balance recalculation")
                except Exception as e:
                    print(f"DEBUG: Error updating page: {e}")
        except Exception as e:
            print(f"ERROR in recalculate_wallet_balances: {e}")
            import traceback
            traceback.print_exc()
    
    def _refresh_all_wallet_balances(self):
        """
        Refresh balance calculations for ALL wallets.
        Called when inter-wallet transfers are detected to ensure both sender and receiver are updated.
        """
        try:
            if not hasattr(self.app.wallet_core, 'wallets') or not isinstance(self.app.wallet_core.wallets, dict):
                return
            
            from utils import update_all_wallet_balances
            
            # Get database and mempool manager
            database = getattr(self.app.wallet_core, 'database', None)
            mempool_manager = getattr(self.app.wallet_core, 'mempool_manager', None)
            
            print(f"\n=== REFRESHING ALL {len(self.app.wallet_core.wallets)} WALLET BALANCES FOR INTER-WALLET TRANSFERS ===")
            
            # Update all wallets' balances
            update_all_wallet_balances(self.app.wallet_core.wallets, database, mempool_manager)
            
            print(f"=== ALL WALLET BALANCES REFRESHED ===\n")
            
        except Exception as e:
            print(f"DEBUG: Error refreshing all wallet balances: {e}")
            import traceback
            traceback.print_exc()
    
    def _update_balance_display_ui(self, available_balance, pending_balance, wallet_address):
        """Update balance card UI with calculated values (Noneは0.0)"""
        try:
            ab = available_balance if available_balance is not None else 0.0
            pb = pending_balance if pending_balance is not None else 0.0
            # Update balance text
            self.balance_text.value = f"{ab:.6f} LKC"
            self.pending_balance_text.value = f"{pb:+.6f} LKC"
            # Color pending balance
            if pb > 0:
                self.pending_balance_text.color = "#00ff00"  # Green
            elif pb < 0:
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
            # NOTE: Do NOT call page.update() here - let the caller handle it
            print(f"DEBUG: _update_balance_display_ui completed")
        except Exception as e:
            print(f"ERROR in _update_balance_display_ui: {e}")
    
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
    
    def _create_transaction_item(self, tx_data, current_address):
        """Create a minimalistic transaction list item"""
        # Check if this is a compressed reward transaction
        is_compressed = tx_data.get('_is_compressed', False)
        
        if is_compressed:
            # Handle compressed reward transactions with expandable view
            original_count = tx_data.get('_original_count', 1)
            amount = tx_data.get('amount', 0)
            status = tx_data.get('status', 'confirmed')
            timestamp = tx_data.get('timestamp', time.time())
            original_transactions = tx_data.get('_original_transactions', [])
            
            # Format amount with color
            amount_color = "#00ff00"  # Rewards are always incoming (green)
            
            # Format date
            try:
                date_str = datetime.fromtimestamp(timestamp).strftime("%m/%d %H:%M")
            except:
                date_str = "Unknown"
            
            # Status indicator
            status_color = "#00ff00" if status == 'confirmed' else "#ffd700"
            status_text = "✓" if status == 'confirmed' else "⏳"
            
            # Create description for compressed rewards
            reward_address = tx_data.get('reward_address', tx_data.get('to', 'Unknown'))
            description = f"Rewards ({original_count}x) → {reward_address[:8]}..."
            
            # Create expandable container for compressed rewards
            # State to track if expanded
            expanded_state = {'is_expanded': False}
            expansion_container = ft.Ref[ft.Column]()
            expand_icon = ft.Ref[ft.Icon]()
            
            def toggle_expand(e):
                """Toggle expansion of compressed rewards"""
                expanded_state['is_expanded'] = not expanded_state['is_expanded']
                
                # Update icon rotation
                if expand_icon.current:
                    expand_icon.current.name = (ft.Icons.EXPAND_LESS if expanded_state['is_expanded'] 
                                                else ft.Icons.EXPAND_MORE)
                    expand_icon.current.update()
                
                # Update expanded content
                if expansion_container.current:
                    expansion_container.current.controls.clear()
                    
                    if expanded_state['is_expanded']:
                        # Show individual rewards
                        expansion_container.current.controls.append(
                            ft.Divider(height=1, color="#444444")
                        )
                        for i, original_tx in enumerate(original_transactions, 1):
                            orig_timestamp = original_tx.get('timestamp', time.time())
                            try:
                                orig_date_str = datetime.fromtimestamp(orig_timestamp).strftime("%m/%d %H:%M")
                            except:
                                orig_date_str = "Unknown"
                            
                            reward_item = ft.Container(
                                    content=ft.ListTile(
                                        leading=ft.Icon(ft.Icons.ATTACH_MONEY, color="#00ff00", size=16),
                                        title=ft.Text(f"+{original_tx.get('amount', 0):.6f} LKC", 
                                            color="#00ff00", size=12, weight="bold"),
                                        subtitle=ft.Text(orig_date_str, size=10, color="#888888"),
                                        on_click=lambda e, tx=original_tx: self._show_transaction_details(tx),
                                    ),
                                    bgcolor="#1a0f0f",
                                    padding=5,
                                    margin=ft.margin.symmetric(vertical=0, horizontal=10),
                                )
                            expansion_container.current.controls.append(reward_item)
                    
                    expansion_container.current.update()
            
            # Main compressed reward item
            return ft.Container(
                content=ft.Column([
                    ft.ListTile(
                        leading=ft.Icon(
                            ft.Icons.ATTACH_MONEY,
                            color=amount_color,
                            size=20
                        ),
                        title=ft.Row([
                            ft.Text(f"+{amount:.6f} LKC × {original_count}", 
                                color=amount_color, 
                                size=14,
                                weight="bold",
                                expand=True),
                            ft.Text(status_text, color=status_color, size=12),
                        ]),
                        subtitle=ft.Row([
                            ft.Text(date_str, size=11, color="#a8a8a8", expand=True),
                            ft.Text(description, size=11, color="#a8a8a8"),
                        ]),
                        trailing=ft.Icon(
                            ft.Icons.EXPAND_MORE,
                            color="#a8a8a8",
                            size=18,
                            ref=expand_icon
                        ),
                        on_click=toggle_expand,
                    ),
                    ft.Column([], ref=expansion_container, spacing=0),
                ], spacing=0),
                bgcolor="#2c1a1a",
                border_radius=8,
                padding=5,
                margin=ft.margin.symmetric(vertical=1),
            )
        
        # Regular transaction handling
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
                alignment=ft.Alignment(0, 0)
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
                alignment=ft.Alignment(0, 0)
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
                alignment=ft.Alignment(0, 0)
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

                        # Peers数（lunalib.core.p2p経由）
                        try:
                            if hasattr(self.app, 'blockchain_manager'):
                                peer_count = self.app.blockchain_manager.get_peer_count()
                                stats.append(self.create_stat_item("🌐", str(peer_count), "Peers"))
                        except Exception as e:
                            stats.append(self.create_stat_item("🌐", "?", "Peers"))
                        
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
        """Check network connection to blockchain and mempool endpoints more robustly"""
        try:
            blockchain_online = False
            mempool_online = False
            peer_count = 0
            
            # Blockchain endpoint - try multiple methods
            if hasattr(self.app, 'blockchain_manager') and self.app.blockchain_manager:
                try:
                    # Try the official check_network_connection method
                    if hasattr(self.app.blockchain_manager, 'check_network_connection'):
                        blockchain_online = self.app.blockchain_manager.check_network_connection()
                    else:
                        # Fallback: try to get latest block (indicates connectivity)
                        if hasattr(self.app.blockchain_manager, 'get_latest_block'):
                            block = self.app.blockchain_manager.get_latest_block()
                            blockchain_online = block is not None and block.get('index') is not None
                        else:
                            blockchain_online = True  # Assume online if manager exists
                    
                    # Try to get peer count
                    if hasattr(self.app.blockchain_manager, 'get_peer_count'):
                        peer_count = self.app.blockchain_manager.get_peer_count()
                    elif hasattr(self.app.blockchain_manager, 'peer_count'):
                        peer_count = self.app.blockchain_manager.peer_count
                    elif hasattr(self.app.blockchain_manager, 'peers'):
                        peers = self.app.blockchain_manager.peers
                        peer_count = len(peers) if peers else 1  # At least the primary endpoint
                    else:
                        # Fallback: if blockchain is online, assume at least 1 peer
                        peer_count = 1 if blockchain_online else 0
                        
                except Exception as e:
                    print(f"DEBUG: Network check error (blockchain): {e}")
                    # If manager exists, assume at least online
                    blockchain_online = True
                    peer_count = 1
            
            # Mempool endpoint - try multiple methods
            if hasattr(self.app, 'mempool_manager') and self.app.mempool_manager:
                try:
                    # Try the official check_network_connection method
                    if hasattr(self.app.mempool_manager, 'check_network_connection'):
                        mempool_online = self.app.mempool_manager.check_network_connection()
                    else:
                        # Fallback: assume online if manager exists
                        mempool_online = True
                except Exception as e:
                    print(f"DEBUG: Network check error (mempool): {e}")
                    mempool_online = True  # Assume online
            
            # Determine overall connection status
            # If either blockchain or mempool is online, and we have peer count, we're connected
            is_connected = False
            if blockchain_online or mempool_online:
                is_connected = True
            elif peer_count and peer_count > 0:
                is_connected = True
            else:
                is_connected = False
            
            # Ensure peer_count is never None
            if peer_count is None:
                peer_count = 1 if is_connected else 0
            
            return {
                'connected': is_connected, 
                'endpoint': 'multi', 
                'peers': peer_count if isinstance(peer_count, int) else 1
            }
        except Exception as e:
            print(f"DEBUG: Network check error: {e}")
            # Default to online with 1 peer on error (be optimistic)
            return {'connected': True, 'endpoint': 'error', 'peers': 1}

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
                        # Use cached balance from wallet_info (don't hardcode to 0)
                        balance = wallet_info.get('balance', wallet_info.get('confirmed_balance', None))
                        pending_balance = wallet_info.get('pending_balance', 0)
                        address = wallet_info.get('address', 'No wallet')
                        label = wallet_info.get('label', 'Wallet')
                        
                        # Display balance or placeholder if not yet calculated
                        if balance is not None:
                            self.balance_text.value = f"{balance:.6f} LKC"
                            self.balance_text.color = "#ffffff"
                        else:
                            self.balance_text.value = "--.-- LKC"
                            self.balance_text.color = "#999999"
                        self.balance_text.update()
                        
                        if pending_balance !=  0:
                            sign = "+" if pending_balance > 0 else ""
                            self.pending_balance_text.value = f"Pending Balance: {sign}{pending_balance:.6f}"
                        else:
                            self.pending_balance_text.value = ""
                        self.pending_balance_text.update()
                        
                        self.address_text.value = f"{label}: {address[:12]}...{address[-6:]}" if len(address) > 20 else address
                        self.address_text.update()
                    else:
                        # No wallet info yet, show placeholder
                        self.balance_text.value = "--.-- LKC"
                        self.balance_text.color = "#999999"
                        self.balance_text.update()
                        self.pending_balance_text.value = ""
                        self.pending_balance_text.update()
                        self.address_text.value = "No wallet data"
                        self.address_text.update()
                    
                else:
                                       # Wallet locked - show placeholder
                    self.balance_text.value = "--.-- LKC"
                    self.balance_text.color = "#999999"
                    self.pending_balance_text.value = ""
                    self.address_text.value = "Wallet Locked"
                
                self.update_quick_stats()
                self.refresh_transaction_history()
                self._refresh_sidebar_wallets()  # Refresh sidebar when wallet data updates
            
        except Exception as e:
            # Show placeholder on error instead of 0
            self.balance_text.value = "--.-- LKC"
            self.balance_text.color = "#999999"
            self.pending_balance_text.value = ""
            self.address_text.value = "Failed to load"
            print(f"Error updating wallet data: {e}")
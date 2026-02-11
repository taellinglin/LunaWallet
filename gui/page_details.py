import flet as ft
from datetime import datetime
import time
from utils import format_amount, format_amount_with_unit

class TransactionDetailsPage:
    def __init__(self, app, transaction_data, on_back=None):
        self.app = app
        self.transaction_data = transaction_data
        self.on_back = on_back
        
    def create(self):
        # Create a responsive container that adjusts based on screen size
        return ft.Container(
            content=ft.Column([
                self._create_header(),
                ft.Container(
                    content=ft.ResponsiveRow([
                        # Left column - Main transaction info
                        ft.Column([
                            self._create_status_card(),
                            self._create_amount_card(),
                            self._create_quick_info_card(),
                        ], col={"sm": 12, "md": 6}),
                        
                        # Right column - Detailed info
                        ft.Column([
                            self._create_details_card(),
                            self._create_actions_card(),
                        ], col={"sm": 12, "md": 6}),
                    ], spacing=15),
                    padding=20,
                    expand=True,
                )
            ], spacing=0),
            expand=True,
            bgcolor="#2c1a1a",
            padding=0
        )
    
    def _create_header(self):
        """Create page header with back button"""
        return ft.Container(
            content=ft.Row([
                ft.IconButton(
                    icon=ft.Icons.ARROW_BACK,
                    icon_color="#f8d7da",
                    on_click=lambda e: self._go_back(),
                    tooltip="Back to Wallet"
                ),
                ft.Text("Transaction Details", size=20, weight="bold", color="#f8d7da", expand=True),
                ft.Container(
                    content=ft.Icon(ft.Icons.RECEIPT, color="#dc3545", size=20),
                    padding=5,
                    bgcolor="#1a0f0f",
                    border_radius=8
                )
            ]),
            padding=ft.padding.symmetric(vertical=15, horizontal=20),
            bgcolor="#1a0f0f",
            border=ft.border.only(bottom=ft.BorderSide(1, "#5c2e2e"))
        )
    
    def _create_status_card(self):
        """Create compact status card"""
        tx = self.transaction_data
        status = tx.get('status', 'unknown')
        confirmations = tx.get('confirmations', 0)
        block_height = tx.get('block_height')
        
        status_color = "#00ff00" if status == 'confirmed' else "#ffd700"
        status_icon = ft.Icons.CHECK_CIRCLE if status == 'confirmed' else ft.Icons.SCHEDULE
        
        return ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Icon(status_icon, color=status_color, size=20),
                    ft.Text("Status", size=16, weight="bold", color="#f8d7da", expand=True),
                ]),
                ft.Container(height=10),
                ft.Row([
                    ft.Container(
                        content=ft.Text(
                            status.upper(),
                            color=status_color,
                            weight="bold",
                            size=12
                        ),
                        padding=ft.padding.symmetric(horizontal=12, vertical=6),
                        bgcolor=f"{status_color}20",
                        border_radius=20,
                        border=ft.border.all(1, status_color)
                    ),
                    ft.Container(expand=True),
                    ft.Text(f"{confirmations} confs", size=12, color="#a8a8a8") if confirmations > 0 else ft.Container(),
                ]),
                ft.Text(
                    f"Block: {block_height}" if block_height else "Pending",
                    size=12,
                    color="#a8a8a8"
                ) if block_height else ft.Container()
            ]),
            padding=15,
            bgcolor="#1a0f0f",
            border_radius=12,
        )
    
    def _create_amount_card(self):
        """Create compact amount card"""
        tx = self.transaction_data
        amount = tx.get('amount', 0)
        fee = tx.get('fee', 0)
        tx_type = tx.get('type', 'transfer')
        
        # Determine direction
        current_address = getattr(self.app.wallet_core, 'current_wallet_address', '')
        to_addr = tx.get('to', '')
        is_incoming = (tx_type in ['reward', 'fee_distribution'] or 
                      (to_addr and to_addr.lower() == current_address.lower()))
        
        color = "#00ff00" if is_incoming else "#ff4444"
        direction = "Received" if is_incoming else "Sent"
        icon = ft.Icons.ARROW_DOWNWARD if is_incoming else ft.Icons.ARROW_UPWARD
        
        return ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Icon(icon, color=color, size=20),
                    ft.Text("Amount", size=16, weight="bold", color="#f8d7da", expand=True),
                ]),
                ft.Container(height=10),
                ft.Text(
                    f"'{format_amount_with_unit(amount)}'",
                    size=20,
                    weight="bold",
                    color=color
                ),
                ft.Row([
                    ft.Text(f"{tx_type.title()} - {direction}", size=12, color="#a8a8a8", expand=True),
                    ft.Text(f"Fee: {format_amount_with_unit(fee)}", size=12, color="#a8a8a8"),
                ])
            ]),
            padding=15,
            bgcolor="#1a0f0f",
            border_radius=12,
        )
    
    def _create_quick_info_card(self):
        """Create quick info card with essential details"""
        tx = self.transaction_data
        timestamp = tx.get('timestamp', 0)
        memo = tx.get('memo', '')
        
        try:
            date_str = datetime.fromtimestamp(timestamp).strftime("%b %d, %Y at %H:%M") if timestamp else "Unknown"
        except:
            date_str = "Unknown"
        
        return ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Icon(ft.Icons.INFO, color="#f8d7da", size=18),
                    ft.Text("Quick Info", size=16, weight="bold", color="#f8d7da", expand=True),
                ]),
                ft.Container(height=10),
                self._create_info_row("Date", date_str),
                self._create_info_row("Memo", memo if memo else "No memo"),
            ]),
            padding=15,
            bgcolor="#1a0f0f",
            border_radius=12,
        )
    
    def _create_details_card(self):
        """Create detailed information card"""
        tx = self.transaction_data
        from_addr, to_addr = self._resolve_addresses(tx)
        tx_hash = tx.get('hash', 'Unknown')
        
        return ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Icon(ft.Icons.LIST_ALT, color="#f8d7da", size=18),
                    ft.Text("Details", size=16, weight="bold", color="#f8d7da", expand=True),
                ]),
                ft.Container(height=10),
                self._create_detail_item("From Address", from_addr, True),
                self._create_detail_item("To Address", to_addr, True),
                self._create_detail_item("Transaction Hash", tx_hash, True),
            ], scroll=ft.ScrollMode.ADAPTIVE),
            padding=15,
            bgcolor="#1a0f0f",
            border_radius=12,
            height=300  # Fixed height with scroll
        )
    
    def _create_actions_card(self):
        """Create actions card with buttons"""
        tx_hash = self.transaction_data.get('hash', '')
        
        return ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Icon(ft.Icons.BUILD, color="#f8d7da", size=18),
                    ft.Text("Actions", size=16, weight="bold", color="#f8d7da", expand=True),
                ]),
                ft.Container(height=10),
                ft.Column([
                    ft.ElevatedButton(
                        content=ft.Row([
                            ft.Icon(ft.Icons.CONTENT_COPY, size=16),
                            ft.Text("Copy TX Hash", size=14, expand=True),
                        ]),
                        on_click=lambda e: self._copy_tx_hash(tx_hash),
                        style=ft.ButtonStyle(
                            color="#ffffff",
                            bgcolor="#dc3545",
                            padding=ft.padding.symmetric(horizontal=15, vertical=12),
                        ),
                        height=45
                    ),
                    ft.Container(height=8),
                    ft.ElevatedButton(
                        content=ft.Row([
                            ft.Icon(ft.Icons.EXPLORE, size=16),
                            ft.Text("View in Explorer", size=14, expand=True),
                        ]),
                        on_click=lambda e: self._view_in_explorer(tx_hash),
                        style=ft.ButtonStyle(
                            color="#ffffff",
                            bgcolor="#28a745",
                            padding=ft.padding.symmetric(horizontal=15, vertical=12),
                        ),
                        height=45
                    ),
                    ft.Container(height=8),
                    ft.ElevatedButton(
                        content=ft.Row([
                            ft.Icon(ft.Icons.SHARE, size=16),
                            ft.Text("Share Details", size=14, expand=True),
                        ]),
                        on_click=lambda e: self._share_details(),
                        style=ft.ButtonStyle(
                            color="#ffffff",
                            bgcolor="#17a2b8",
                            padding=ft.padding.symmetric(horizontal=15, vertical=12),
                        ),
                        height=45
                    ),
                ])
            ]),
            padding=15,
            bgcolor="#1a0f0f",
            border_radius=12,
        )
    
    def _create_info_row(self, label, value):
        """Create a compact info row"""
        return ft.Container(
            content=ft.Column([
                ft.Text(label, size=12, color="#a8a8a8", weight="bold"),
                ft.Text(value, size=13, color="#f8d7da", selectable=True),
            ], spacing=2),
            padding=ft.padding.symmetric(vertical=6),
        )
    
    def _create_detail_item(self, label, value, show_copy=False):
        """Create a compact detailed item with optional copy button"""
        return ft.Container(
            content=ft.Row([
                ft.Column([
                    ft.Text(label, size=11, color="#a8a8a8", weight="bold"),
                    ft.Text(
                        value,
                        size=11,
                        color="#f8d7da",
                        selectable=True,
                        max_lines=1,
                        overflow="ellipsis"
                    ),
                ], spacing=1, expand=True),
                ft.IconButton(
                    icon=ft.Icons.CONTENT_COPY,
                    icon_size=12,
                    icon_color="#dc3545",
                    on_click=lambda e, v=value: self._copy_to_clipboard(v),
                    tooltip=f"Copy {label}",
                    style=ft.ButtonStyle(padding=3)
                ) if show_copy else ft.Container(width=0, height=0),
            ], spacing=8, vertical_alignment="start"),
            padding=ft.padding.symmetric(vertical=4),
            border=ft.border.only(bottom=ft.BorderSide(0.5, "#5c2e2e"))
        )
    
    def _copy_tx_hash(self, tx_hash):
        """Copy transaction hash to clipboard"""
        try:
            copied = False
            if hasattr(self.app, "copy_to_clipboard"):
                copied = self.app.copy_to_clipboard(tx_hash)
            if not copied and not self.app.is_mobile:
                import pyperclip
                pyperclip.copy(tx_hash)
        except Exception as e:
            print(f"DEBUG: Clipboard error: {e}")
            try:
                if not self.app.is_mobile:
                    import pyperclip
                    pyperclip.copy(tx_hash)
            except Exception as e2:
                print(f"DEBUG: Pyperclip error: {e2}")
        
        if hasattr(self.app, 'show_snackbar'):
            def show_snack():
                try:
                    self.app.show_snackbar("Transaction hash copied!", "success")
                except Exception as e:
                    print(f"DEBUG: Error in snackbar callback: {e}")
            
            if hasattr(self.app.page, 'run_thread'):
                self.app.page.run_thread(show_snack)
            else:
                show_snack()
    
    def _copy_to_clipboard(self, text):
        """Copy any text to clipboard"""
        try:
            copied = False
            if hasattr(self.app, "copy_to_clipboard"):
                copied = self.app.copy_to_clipboard(text)
            if not copied and not self.app.is_mobile:
                import pyperclip
                pyperclip.copy(text)
        except Exception as e:
            print(f"DEBUG: Clipboard error: {e}")
            try:
                if not self.app.is_mobile:
                    import pyperclip
                    pyperclip.copy(text)
            except Exception as e2:
                print(f"DEBUG: Pyperclip error: {e2}")
        
        if hasattr(self.app, 'show_snackbar'):
            def show_snack():
                try:
                    self.app.show_snackbar("Copied to clipboard!", "success")
                except Exception as e:
                    print(f"DEBUG: Error in snackbar callback: {e}")
            
            if hasattr(self.app.page, 'run_thread'):
                self.app.page.run_thread(show_snack)
            else:
                show_snack()
    
    def _view_in_explorer(self, tx_hash):
        """View transaction in blockchain explorer"""
        if hasattr(self.app, 'show_snackbar'):
            self.app.show_snackbar("Opening blockchain explorer...", "info")
        
        base_url = "https://bank.linglin.art"
        explorer_url = f"{base_url}/transaction-viewer/{tx_hash}"
        
        import webbrowser
        webbrowser.open(explorer_url)
    
    def _share_details(self):
        """Share transaction details"""
        tx = self.transaction_data
        from_addr, to_addr = self._resolve_addresses(tx)
        share_text = f"""
Transaction Details:
Amount: {format_amount_with_unit(tx.get('amount', 0))}
Type: {tx.get('type', 'transfer')}
    From: {from_addr}
    To: {to_addr}
Hash: {tx.get('hash', 'Unknown')}
        """.strip()
        
        try:
            copied = False
            if hasattr(self.app, "copy_to_clipboard"):
                copied = self.app.copy_to_clipboard(share_text)
            if not copied and not self.app.is_mobile:
                import pyperclip
                pyperclip.copy(share_text)
        except AttributeError:
            # Fallback for different Flet versions
            import pyperclip
            pyperclip.copy(share_text)
        if hasattr(self.app, 'show_snackbar'):
            self.app.show_snackbar("Transaction details copied for sharing!", "success")

    def _resolve_addresses(self, tx: dict) -> tuple[str, str]:
        """Resolve from/to addresses across possible transaction schemas."""
        candidates_from = [
            tx.get('from'),
            tx.get('from_address'),
            tx.get('sender'),
            tx.get('input_address'),
        ]
        candidates_to = [
            tx.get('to'),
            tx.get('to_address'),
            tx.get('recipient'),
            tx.get('output_address'),
        ]

        def _first_valid(values):
            for v in values:
                if v:
                    return v
            return "Unknown"

        return _first_valid(candidates_from), _first_valid(candidates_to)
    
    def _go_back(self):
        """Go back to wallet page"""
        if self.on_back:
            self.on_back()
        else:
            # Fallback to wallet page
            from gui.page_wallet import WalletPage
            try:
                if hasattr(self.app, "show_wallet_page"):
                    self.app.show_wallet_page(reuse=True)
                    return
            except Exception:
                pass
            wallet_page = WalletPage(
                self.app,
                on_send=self.app.show_send_page,
                on_receive=self.app.show_receive_page,
                on_export_key=self.app.show_export_key_page,
                on_create_wallet=self.app.show_create_wallet,
                on_import_wallet=self.app.show_import_wallet
            )
            self.app.current_page = wallet_page.create()
            self.app.show_current_page()
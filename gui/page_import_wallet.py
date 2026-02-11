import flet as ft
import re
import time

from utils import validate_private_key

class ImportWalletPage:
    def __init__(self, app, on_back, on_wallet_imported):
        self.app = app
        self.on_back = on_back
        self.on_wallet_imported = on_wallet_imported
        self._field_width = 420 if not app.is_mobile else 320
        self.is_importing = False
        
        # Form fields
        self.private_key = ft.TextField(
            label="Private Key",
            hint_text="Enter your private key",
            multiline=True,
            width=self._field_width,
            height=120,
            bgcolor="#1a0f0f",
            border_color="#5c2e2e",
            focused_border_color="#dc3545",
            color="#f8d7da",
            label_style=ft.TextStyle(color="#f8d7da"),
            text_style=ft.TextStyle(color="#f8d7da", font_family="monospace"),
            prefix_icon=ft.Icons.KEY,
        )
        self.wallet_name = ft.TextField(
            label="Wallet Name",
            hint_text="Enter wallet name", 
            width=self._field_width,
            bgcolor="#1a0f0f",
            border_color="#5c2e2e",
            focused_border_color="#dc3545",
            color="#f8d7da",
            label_style=ft.TextStyle(color="#f8d7da"),
            text_style=ft.TextStyle(color="#f8d7da"),
            prefix_icon=ft.Icons.ACCOUNT_BALANCE_WALLET,
            on_submit=self.import_wallet,
        )
        self.password = ft.TextField(
            label="Password",
            password=True,
            can_reveal_password=True,
            hint_text="Enter password",
            width=self._field_width,
            bgcolor="#1a0f0f",
            border_color="#5c2e2e",
            focused_border_color="#dc3545",
            color="#f8d7da",
            label_style=ft.TextStyle(color="#f8d7da"),
            text_style=ft.TextStyle(color="#f8d7da"),
            prefix_icon=ft.Icons.LOCK,
            on_submit=self.import_wallet,
        )

        self.import_button = ft.ElevatedButton(
            "Import",
            on_click=self.import_wallet,
            style=ft.ButtonStyle(
                color="#ffffff",
                bgcolor="#dc3545", 
                padding=ft.padding.symmetric(horizontal=18, vertical=12),
                shape=ft.RoundedRectangleBorder(radius=8)
            ),
            width=160
        )
        self.progress_indicator = ft.ProgressRing(
            color="#dc3545",
            visible=False,
            width=20,
            height=20
        )
        
    def create(self):
        top_padding = 24 if self.app.is_mobile else 10
        return ft.Container(
            content=ft.Column([
                # Header
                ft.Row([
                    ft.IconButton(
                        icon=ft.Icons.ARROW_BACK,
                        icon_color="#f8d7da", 
                        on_click=lambda e: self.on_back()
                    ),
                    ft.Column([
                        ft.Text("Import Wallet", size=22, weight="bold", color="#f8d7da"),
                        ft.Text("Restore from a private key", size=12, color="#a8a8a8"),
                    ], spacing=2),
                    ft.Container(expand=True)
                ]),
                
                ft.Divider(color="#5c2e2e"),
                
                # Form
                ft.Container(
                    content=ft.Column([
                        ft.Text("Wallet Details", size=14, color="#f8d7da", weight="bold", text_align="center"),
                        ft.Text("Use the original private key for this wallet", size=11, color="#a8a8a8", text_align="center"),
                        ft.Container(height=12),
                        
                        self.private_key,
                        ft.Container(height=10),
                        self.wallet_name,
                        ft.Container(height=10),
                        self.password,
                        
                        ft.Container(height=16),
                        
                        ft.Row([
                            self.import_button,
                            self.progress_indicator
                        ], alignment=ft.MainAxisAlignment.CENTER, spacing=10)
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                    padding=20,
                    margin=ft.margin.symmetric(vertical=6),
                    bgcolor="#1a0f0f",
                    border_radius=12,
                    border=ft.border.all(1, "#5c2e2e"),
                    expand=True
                )
            ], scroll=ft.ScrollMode.ADAPTIVE, expand=True),
            expand=True, 
            padding=ft.padding.only(top=top_padding, left=10, right=10, bottom=16),
            bgcolor="#2c1a1a"
        )

    def _label_exists(self, label: str) -> bool:
        try:
            if not label:
                return False
            label_lower = label.strip().lower()
            wallets = getattr(self.app.wallet_core, 'wallets', None)
            if isinstance(wallets, dict):
                for w in wallets.values():
                    if isinstance(w, dict):
                        existing = str(w.get('label', '')).strip().lower()
                        if existing and existing == label_lower:
                            return True
            elif isinstance(wallets, list):
                for w in wallets:
                    if isinstance(w, dict):
                        existing = str(w.get('label', '')).strip().lower()
                        if existing and existing == label_lower:
                            return True
        except Exception:
            return False
        return False
    
    def import_wallet(self, e):
        if self.is_importing:
            return
        # Validate form
        private_key_raw = self.private_key.value.strip()
        wallet_name = self.wallet_name.value.strip()
        password = self.password.value
        
        if not private_key_raw:
            self.app.show_snackbar("Please enter private key", "error")
            return
            
        if not wallet_name:
            self.app.show_snackbar("Please enter wallet name", "error")
            return

        if self._label_exists(wallet_name):
            self.app.show_snackbar("Wallet name already exists. Please choose a different name.", "error")
            return
            
        if not password:
            self.app.show_snackbar("Please enter password", "error")
            return
            
        if len(password) < 8:
            self.app.show_snackbar("Password must be at least 8 characters", "error")
            return
        
        # Normalize common export formats (e.g., priv_/0x prefixes, whitespace)
        private_key = re.sub(r"\s+", "", private_key_raw)
        if private_key.lower().startswith("priv_"):
            private_key = private_key[5:]
        if private_key.lower().startswith("0x"):
            private_key = private_key[2:]

        is_valid, reason = validate_private_key(private_key)
        if not is_valid:
            self.app.show_snackbar(f"Invalid private key: {reason}", "error")
            return

        self._show_loading_state(True)

        def _build_wallet_data() -> dict:
            data = {
                'private_key': private_key,
                'label': wallet_name,
                'public_key': None,
                'encrypted_private_key': None,
                'balance': 0.0,
                'confirmed_balance': 0.0,
                'pending_balance': 0.0,
                'available_balance': 0.0,
                'created': time.time(),
                'is_locked': False,
            }
            try:
                from lunalib.core.crypto import KeyManager

                key_manager = KeyManager()
                public_key = None
                if hasattr(key_manager, "derive_public_key"):
                    try:
                        public_key = key_manager.derive_public_key(private_key)
                    except Exception as key_err:
                        print(f"DEBUG: derive_public_key failed: {key_err}")
                if public_key:
                    data['public_key'] = public_key

                address = None
                for method in (
                    "public_key_to_address",
                    "derive_address_from_public_key",
                    "address_from_public_key",
                    "derive_address",
                ):
                    if hasattr(key_manager, method):
                        try:
                            address = getattr(key_manager, method)(public_key)
                            if address:
                                break
                        except Exception as addr_err:
                            print(f"DEBUG: {method} failed: {addr_err}")
                if not address:
                    for method in (
                        "private_key_to_address",
                        "derive_address_from_private_key",
                        "address_from_private_key",
                    ):
                        if hasattr(key_manager, method):
                            try:
                                address = getattr(key_manager, method)(private_key)
                                if address:
                                    break
                            except Exception as addr_err:
                                print(f"DEBUG: {method} failed: {addr_err}")

                if address:
                    data['address'] = address
            except Exception as e:
                print(f"DEBUG: Failed to build wallet data: {e}")

            # Best-effort encryption for compatibility with lunalib import
            if password:
                try:
                    from lunalib.core import wallet as wallet_module

                    encrypted = wallet_module._encrypt_with_password(
                        private_key.encode("utf-8"),
                        password,
                    )
                    # lunalib validate_wallet_import json.dumps requires serializable values
                    if isinstance(encrypted, (bytes, bytearray)):
                        import base64

                        data['encrypted_private_key'] = base64.b64encode(encrypted).decode("ascii")
                    else:
                        data['encrypted_private_key'] = encrypted
                except Exception as enc_err:
                    print(f"DEBUG: Failed to encrypt private key: {enc_err}")
            return data

        def do_import():
            try:
                # 既存ウォレットがある場合はアンロックを試みる
                if self.app.wallet_core.wallets:
                    unlocked = False
                    for addr in self.app.wallet_core.wallets:
                        if self.app.wallet_core.unlock_wallet(addr, password):
                            unlocked = True
                            break
                    if not unlocked:
                        self.app.show_snackbar("Invalid password for existing wallet", "error")
                        return

                result = None
                try:
                    wallet_data = _build_wallet_data()
                    if wallet_data.get('address') or wallet_data.get('public_key'):
                        result = self.app.wallet_core.import_wallet(wallet_data, password)
                    if not result:
                        result = self.app.wallet_core.import_wallet(private_key, wallet_name, password)
                except TypeError:
                    try:
                        wallet_data = _build_wallet_data()
                        result = self.app.wallet_core.import_wallet(wallet_data, password)
                    except TypeError:
                        result = self.app.wallet_core.import_wallet(private_key, password)

                if result:
                    if hasattr(self.app, "save_wallet_data"):
                        self.app.save_wallet_data(force_save=True)
                    elif hasattr(self.app.wallet_core, "save_wallet_data"):
                        self.app.wallet_core.save_wallet_data()
                    try:
                        if hasattr(self.app, "_register_wallets_with_manager"):
                            self.app._register_wallets_with_manager()
                    except Exception:
                        pass
                    try:
                        if hasattr(self.app, "show_snackbar"):
                            self.app.show_snackbar("Rescanning blockchain...", "info")
                        if hasattr(self.app, "force_rescan_blockchain"):
                            self.app.force_rescan_blockchain()
                        elif hasattr(self.app, "scan_all_wallets_for_changes"):
                            self.app.scan_all_wallets_for_changes(force_full_scan=True)
                    except Exception:
                        pass
                    self.on_wallet_imported()
                else:
                    self.app.show_snackbar("Failed to import wallet - invalid private key or password", "error")
            except Exception as ex:
                self.app.show_snackbar(f"Error importing wallet: {str(ex)}", "error")
            finally:
                self._show_loading_state(False)

        import threading
        threading.Thread(target=do_import, daemon=True).start()

    def _show_loading_state(self, loading: bool):
        self.is_importing = loading
        self.import_button.disabled = loading
        self.progress_indicator.visible = loading
        if hasattr(self.app, 'page') and self.app.page:
            self.app.page.update()
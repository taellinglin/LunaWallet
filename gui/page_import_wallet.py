import flet as ft

class ImportWalletPage:
    def __init__(self, app, on_back, on_wallet_imported):
        self.app = app
        self.on_back = on_back
        self.on_wallet_imported = on_wallet_imported
        self._field_width = 420 if not app.is_mobile else 320
        
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
        
    def create(self):
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
                        
                        ft.ElevatedButton(
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
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                    padding=20,
                    margin=ft.margin.symmetric(vertical=6),
                    bgcolor="#1a0f0f",
                    border_radius=12,
                    border=ft.border.all(1, "#5c2e2e"),
                    expand=True
                )
            ]),
            expand=True, 
            padding=10,
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
        # Validate form
        private_key = self.private_key.value.strip()
        wallet_name = self.wallet_name.value.strip()
        password = self.password.value
        
        if not private_key:
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
        
        # Import wallet
        try:
            # 既存ウォレットがある場合はアンロックを試みる
            if self.app.wallet_core.wallets:
                # 既存ウォレットのいずれかのアドレスでアンロック
                unlocked = False
                for addr in self.app.wallet_core.wallets:
                    if self.app.wallet_core.unlock_wallet(addr, password):
                        unlocked = True
                        break
                if not unlocked:
                    self.app.show_snackbar("Invalid password for existing wallet", "error")
                    return

            # lunalib 1.9.3 import API (try new signature first, then fallback)
            result = None
            try:
                result = self.app.wallet_core.import_wallet(private_key, wallet_name, password)
            except TypeError:
                try:
                    wallet_data = {
                        'private_key': private_key,
                        'label': wallet_name,
                    }
                    result = self.app.wallet_core.import_wallet(wallet_data, password)
                except TypeError:
                    result = self.app.wallet_core.import_wallet(private_key, password)
            if result:
                self.app.wallet_core.save_wallet(password)
                self.on_wallet_imported()
            else:
                self.app.show_snackbar("Failed to import wallet - invalid private key or password", "error")

        except Exception as ex:
            self.app.show_snackbar(f"Error importing wallet: {str(ex)}", "error")
import flet as ft

class ImportWalletPage:
    def __init__(self, app, on_back, on_wallet_imported):
        self.app = app
        self.on_back = on_back
        self.on_wallet_imported = on_wallet_imported
        
        # Form fields
        self.private_key = ft.TextField(
            label="🔑 Private Key",
            hint_text="Enter your private key",
            multiline=True,
            width=400 if not app.is_mobile else 300,
            height=100
        )
        self.wallet_name = ft.TextField(
            label="👛 Wallet Name",
            hint_text="Enter wallet name", 
            width=400 if not app.is_mobile else 300
        )
        self.password = ft.TextField(
            label="🔒 Password",
            password=True,
            can_reveal_password=True,
            hint_text="Enter password",
            width=400 if not app.is_mobile else 300
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
                    ft.Text("📥 Import Wallet", size=24, weight="bold", color="#f8d7da"),
                    ft.Container(expand=True)
                ]),
                
                ft.Divider(color="#5c2e2e"),
                
                # Form
                ft.Container(
                    content=ft.Column([
                        ft.Text("Import existing wallet", size=18, color="#f8d7da"),
                        ft.Text("Enter your private key to import your wallet", size=14, color="#f8d7da"),
                        ft.Container(height=20),
                        
                        self.private_key,
                        self.wallet_name,
                        self.password,
                        
                        ft.Container(height=30),
                        
                        ft.ElevatedButton(
                            "📥 Import Wallet",
                            on_click=self.import_wallet,
                            style=ft.ButtonStyle(
                                color="#ffffff",
                                bgcolor="#dc3545", 
                                padding=20
                            ),
                            width=200
                        )
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                    padding=20,
                    margin=10,
                    bgcolor="#1a0f0f",
                    border_radius=15,
                    width=500 if not self.app.is_mobile else 350
                )
            ]),
            expand=True, 
            padding=20,
            bgcolor="#2c1a1a"
        )
    
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
            
        if not password:
            self.app.show_snackbar("Please enter password", "error")
            return
            
        if len(password) < 8:
            self.app.show_snackbar("Password must be at least 8 characters", "error")
            return
        
        # Import wallet
        try:
            # First unlock if we have existing wallets
            if self.app.wallet_core.wallets:
                if not self.app.wallet_core.unlock_wallet(password):
                    self.app.show_snackbar("Invalid password for existing wallet", "error")
                    return
            
            # Import the wallet
            if self.app.wallet_core.import_wallet(private_key, wallet_name):
                # Save the wallet
                self.app.wallet_core.save_wallet(password)
                self.on_wallet_imported()
            else:
                self.app.show_snackbar("Failed to import wallet - invalid private key", "error")
                
        except Exception as ex:
            self.app.show_snackbar(f"Error importing wallet: {str(ex)}", "error")
import flet as ft

class LockPage:
    def __init__(self, app, on_unlock, onCreate_wallet, wallet_exists=False):
        self.app = app
        self.on_unlock = on_unlock
        self.onCreate_wallet = onCreate_wallet
        self.wallet_exists = wallet_exists  # Whether a wallet already exists
        
        self.password_field = ft.TextField(
            label="Password",
            password=True,
            can_reveal_password=True,
            width=300,
            border_color="#5c2e2e",
            focused_border_color="#dc3545",
            text_size=14,
            color="#f8d7da",
            cursor_color="#dc3545",
            label_style=ft.TextStyle(color="#f8d7da"),
            on_submit=self.unlock
        )
        
    def create(self):
        if self.wallet_exists:
            # Show unlock UI for existing wallet
            return self._create_unlock_ui()
        else:
            # Show create wallet UI for new users
            return self._create_setup_ui()
    
    def _create_unlock_ui(self):
        """Create UI for unlocking existing wallet"""
        return ft.Container(
            content=ft.Column([
                ft.Container(expand=True),
                
                # Wallet Icon
                ft.Container(
                    content=ft.Image(
                        src="./wallet_icon.svg",
                        width=80,
                        height=80,
                        fit=ft.ImageFit.CONTAIN,
                        error_content=ft.Icon(ft.Icons.ACCOUNT_BALANCE_WALLET, size=80, color="#dc3545")
                    ),
                    margin=ft.margin.only(bottom=20)
                ),
                    
                ft.Text("Luna Wallet", size=32, weight="bold", color="#f8d7da"),
                ft.Container(height=10),
                ft.Text("Enter your password to unlock", size=16, color="#f8d7da"),
                ft.Container(height=30),
                
                # Password field
                self.password_field,
                ft.Container(height=20),
                
                ft.ElevatedButton(
                    content=ft.Row(
                        [
                            ft.Icon(ft.Icons.LOCK_OPEN, color="#ffffff"),
                            ft.Text("Unlock", color="#ffffff"),
                        ],
                        alignment=ft.MainAxisAlignment.CENTER,
                        tight=True,
                    ),
                    on_click=self.unlock,
                    style=ft.ButtonStyle(
                        color="#ffffff",
                        bgcolor="#dc3545",
                        padding=ft.padding.symmetric(horizontal=20, vertical=15),
                    ),
                    width=200
                ),
                
                ft.Container(expand=True),
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            expand=True,
            padding=20,
            bgcolor="#2c1a1a",
            alignment=ft.alignment.center
        )
    
    def _create_setup_ui(self):
        """Create UI for new wallet setup"""
        return ft.Container(
            content=ft.Column([
                ft.Container(expand=True),
                
                # Wallet Icon
                ft.Container(
                    content=ft.Icon(
                        ft.Icons.ACCOUNT_BALANCE_WALLET, 
                        size=80, 
                        color="#dc3545"
                    ),
                    margin=ft.margin.only(bottom=20)
                ),
                
                ft.Text("Welcome to Luna Wallet", size=24, weight="bold", color="#f8d7da"),
                ft.Container(height=10),
                ft.Text("Set up your wallet to get started", size=16, color="#f8d7da"),
                ft.Container(height=30),
                
                # Create wallet button
                ft.ElevatedButton(
                    content=ft.Row(
                        [
                            ft.Icon(ft.Icons.ADD_CIRCLE_OUTLINE, color="#ffffff"),
                            ft.Text("Create New Wallet", color="#ffffff"),
                        ],
                        alignment=ft.MainAxisAlignment.CENTER,
                        tight=True,
                    ),
                    on_click=lambda e: self.onCreate_wallet(),
                    style=ft.ButtonStyle(
                        color="#ffffff",
                        bgcolor="#dc3545",
                        padding=ft.padding.symmetric(horizontal=20, vertical=15),
                    ),
                    width=200
                ),
                
                ft.Container(height=15),
                
                # Import wallet button
                ft.OutlinedButton(
                    content=ft.Row(
                        [
                            ft.Icon(ft.Icons.IMPORT_EXPORT, color="#dc3545"),
                            ft.Text("Import Existing Wallet", color="#dc3545"),
                        ],
                        alignment=ft.MainAxisAlignment.CENTER,
                        tight=True,
                    ),
                    on_click=lambda e: self.app.show_import_wallet(),
                    style=ft.ButtonStyle(
                        color="#dc3545",
                        side=ft.BorderSide(color="#dc3545", width=2),
                        padding=ft.padding.symmetric(horizontal=20, vertical=15),
                    ),
                    width=200
                ),
                
                ft.Container(expand=True),
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            expand=True,
            padding=20,
            bgcolor="#2c1a1a",
            alignment=ft.alignment.center
        )
    
    def unlock(self, e):
        password = self.password_field.value.strip()
        if not password:
            self.app.show_snackbar("Please enter password", "error")
            return
            
        self.on_unlock(password)
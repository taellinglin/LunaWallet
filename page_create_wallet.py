import flet as ft

class CreateWalletPage:
    def __init__(self, app, on_back, on_wallet_created):
        self.app = app
        self.on_back = on_back
        self.on_wallet_created = on_wallet_created
        
        # Form fields
        self.wallet_name = ft.TextField(
            label="Wallet Name",
            hint_text="My Wallet",
            width=300,
            border_color="#5c2e2e",
            focused_border_color="#dc3545",
            text_size=14,
            color="#f8d7da",
            cursor_color="#dc3545",
            label_style=ft.TextStyle(color="#f8d7da"),
        )
        self.password = ft.TextField(
            label="Password", 
            password=True,
            can_reveal_password=True,
            hint_text="Password to encrypt wallet",
            width=300,
            border_color="#5c2e2e",
            focused_border_color="#dc3545",
            text_size=14,
            color="#f8d7da",
            cursor_color="#dc3545",
            label_style=ft.TextStyle(color="#f8d7da"),
        )
        self.confirm_password = ft.TextField(
            label="Confirm Password",
            password=True,
            can_reveal_password=True, 
            hint_text="Confirm password",
            width=300,
            border_color="#5c2e2e",
            focused_border_color="#dc3545",
            text_size=14,
            color="#f8d7da",
            cursor_color="#dc3545",
            label_style=ft.TextStyle(color="#f8d7da"),
        )
        
    def create(self):
        return ft.Container(
            content=ft.Column([
                # Back button at top left
                ft.Container(
                    content=ft.IconButton(
                        icon=ft.Icons.ARROW_BACK,
                        icon_color="#f8d7da",
                        on_click=lambda e: self.on_back(),
                    ),
                    alignment=ft.alignment.top_left,
                    padding=10
                ),
                
                # Centered form content
                ft.Container(
                    content=ft.Column([
                        # Wallet Icon
                        ft.Container(
                            content=ft.Icon(
                                ft.Icons.ACCOUNT_BALANCE_WALLET, 
                                size=60, 
                                color="#dc3545"
                            ),
                            margin=ft.margin.only(bottom=20)
                        ),
                        
                        ft.Text("Create New Wallet", size=24, weight="bold", color="#f8d7da"),
                        ft.Container(height=10),
                        ft.Text("Set up your first Luna wallet", size=16, color="#f8d7da"),
                        ft.Container(height=30),
                        
                        # Form fields
                        self.wallet_name,
                        ft.Container(height=15),
                        self.password,
                        ft.Container(height=15),
                        self.confirm_password,
                        ft.Container(height=30),
                        
                        # Create button
                        ft.ElevatedButton(
                            "Create Wallet",
                            on_click=self.create_wallet,
                            style=ft.ButtonStyle(
                                color="#ffffff",
                                bgcolor="#dc3545",
                                padding=ft.padding.symmetric(horizontal=30, vertical=15),
                            ),
                            width=200
                        )
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                    padding=30,
                    alignment=ft.alignment.center
                ),
            ]),
            expand=True,
            padding=20,
            bgcolor="#2c1a1a",
            alignment=ft.alignment.center
        )
    
    def create_wallet(self, e):
        # Validate form
        wallet_name = self.wallet_name.value.strip()
        password = self.password.value
        confirm_password = self.confirm_password.value
        
        if not wallet_name:
            self.app.show_snackbar("Please enter wallet name", "error")
            return
            
        if not password:
            self.app.show_snackbar("Please enter password", "error") 
            return
            
        if password != confirm_password:
            self.app.show_snackbar("Passwords do not match", "error")
            return
            
        if len(password) < 8:
            self.app.show_snackbar("Password must be at least 8 characters", "error")
            return
        
        # Create wallet - handle the case where wallet is created but not properly unlocked
        try:
            # First try to create the wallet using the library method
            if self.app.wallet_core.initialize_wallet(password, wallet_name):
                # If successful, manually ensure the app state is consistent
                self.app.is_locked = False
                self.app.show_snackbar("Wallet created successfully!", "success")
                self.on_wallet_created()
            else:
                # If initialize_wallet returned False but wallet might have been created,
                # try to manually unlock with the same password
                try:
                    if self.app.wallet_core.unlock_wallet(password):
                        self.app.is_locked = False
                        self.app.show_snackbar("Wallet created successfully!", "success")
                        self.on_wallet_created()
                    else:
                        self.app.show_snackbar("Failed to create wallet", "error")
                except:
                    self.app.show_snackbar("Failed to create wallet", "error")
                    
        except Exception as ex:
            self.app.show_snackbar(f"Error creating wallet: {str(ex)}", "error")
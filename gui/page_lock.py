import flet as ft

class LockPage:
    def __init__(self, app, on_unlock, onCreate_wallet, wallet_exists=False, title="Luna Wallet", subtitle="Enter password to unlock...", show_create_option=True):
        self.app = app
        self.on_unlock = on_unlock
        self.onCreate_wallet = onCreate_wallet
        self.wallet_exists = wallet_exists
        self.title = title
        self.subtitle = subtitle
        self.show_create_option = show_create_option
        self.is_unlocking = False
            
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
        
        self.loading_container = None
        self.unlock_button = None
        self.content_column = None
        
    def create(self):
        # Show unlock UI if wallets exist, otherwise show setup UI
        if self.wallet_exists:
            return self._create_unlock_ui()
        else:
            return self._create_setup_ui()
    
    def _create_unlock_ui(self):
        """Create UI for unlocking existing wallet - ONLY unlock options"""
        self.unlock_button = ft.ElevatedButton(
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
        )
        
        self.loading_container = ft.Container(
            visible=False,
            content=ft.Column([
                ft.ProgressRing(
                    value=None,
                    stroke_width=4,
                    color="#dc3545",
                    width=50,
                    height=50
                ),
                ft.Container(height=15),
                ft.Text("Unlocking wallet...", size=16, color="#f8d7da", weight="bold"),
                ft.Text("This may take a moment", size=12, color="#a89a9a"),
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER)
        )
        
        self.content_column = ft.Column([
            ft.Container(expand=True),
            
            ft.Container(
                content=ft.Image(
                    src="../wallet_icon.svg",
                    width=80,
                    height=80,
                    fit=ft.ImageFit.CONTAIN,
                    error_content=ft.Icon(ft.Icons.ACCOUNT_BALANCE_WALLET, size=80, color="#dc3545")
                ),
                margin=ft.margin.only(bottom=20)
            ),
                
            ft.Text(self.title, size=32, weight="bold", color="#f8d7da"),
            ft.Container(height=10),
            ft.Text(self.subtitle, size=16, color="#f8d7da"),
            ft.Container(height=30),
            
            self.password_field,
            ft.Container(height=20),
            
            self.unlock_button,
            self.loading_container,
            
            ft.Container(expand=True),
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER)
        
        return ft.Container(
            content=self.content_column,
            expand=True,
            padding=20,
            bgcolor="#2c1a1a",
            alignment=ft.alignment.center
        )
    
    def _create_setup_ui(self):
        """Create UI for new wallet setup - ONLY create/import options"""
        return ft.Container(
            content=ft.Column([
                ft.Container(expand=True),
                
                # Wallet Icon
                ft.Container(
                    content=ft.Image(
                        src="../wallet_icon.svg",
                        width=80,
                        height=80,
                        fit=ft.ImageFit.CONTAIN,
                        error_content=ft.Icon(ft.Icons.ACCOUNT_BALANCE_WALLET, size=80, color="#dc3545")
                    ),
                    margin=ft.margin.only(bottom=20)
                ),
                
                ft.Text(self.title, size=24, weight="bold", color="#f8d7da"),
                ft.Container(height=10),
                ft.Text(self.subtitle, size=16, color="#f8d7da"),
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
        
        if self.is_unlocking:
            return
        
        self.is_unlocking = True
        self.show_loading()
        self.on_unlock(password)
    
    def show_loading(self):
        if self.unlock_button:
            self.unlock_button.visible = False
        if self.loading_container:
            self.loading_container.visible = True
        if self.password_field:
            self.password_field.disabled = True
        if self.app and hasattr(self.app, 'page'):
            self.app.page.update()
    
    def hide_loading(self):
        self.is_unlocking = False
        if self.unlock_button:
            self.unlock_button.visible = True
        if self.loading_container:
            self.loading_container.visible = False
        if self.password_field:
            self.password_field.disabled = False
        if self.app and hasattr(self.app, 'page'):
            self.app.page.update()
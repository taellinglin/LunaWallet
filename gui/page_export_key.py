import flet as ft

class ExportKeyPage:
    def __init__(self, app, on_back, wallet_address=None):
        self.app = app
        self.on_back = on_back
        self.wallet_address = wallet_address
        
        # Form fields
        field_width = 400 if not app.is_mobile else 300
        self.password = ft.TextField(
            label="🔒 Enter Password", password=True, can_reveal_password=True,
            hint_text="Enter your wallet password", width=field_width
        )
        self.private_key_display = ft.TextField(
            label="🔑 Your Private Key", multiline=True, read_only=True,
            width=field_width, height=100, visible=False
        )
        self.copy_button = ft.ElevatedButton(
            "📋 Copy to Clipboard", icon=ft.Icons.COPY, on_click=self.copy_private_key,
            style=ft.ButtonStyle(color="#ffffff", bgcolor="#dc3545", padding=15),
            visible=False
        )
        
    def create(self):
        return ft.Container(
            content=ft.Column([
                # Header
                ft.Row([
                    ft.IconButton(ft.Icons.ARROW_BACK, icon_color="#f8d7da", on_click=lambda e: self.on_back()),
                    ft.Text("🔑 Export Private Key", size=24, weight="bold", color="#f8d7da"),
                    ft.Container(expand=True)
                ]),
                ft.Divider(color="#5c2e2e"),
                
                # Warning
                ft.Container(
                    content=ft.Column([
                        ft.Icon(ft.Icons.WARNING, color="#FF6B6B", size=40),
                        ft.Text("⚠️ Security Warning", size=18, color="#FF6B6B", weight="bold"),
                        ft.Text(
                            "🚫 Never share your private key with anyone! "
                            "Anyone with this key can access your funds.",
                            color="#FF6B6B", text_align="center"
                        )
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                    padding=20, margin=10, bgcolor="#2a1e1e", border_radius=10,
                    width=500 if not self.app.is_mobile else 350
                ),
                
                # Centered form container
                ft.Container(
                    content=ft.Column([
                        self.password,
                        self.private_key_display,
                        ft.Container(height=20),
                        ft.Row([
                            ft.ElevatedButton(
                                "👁️ Show Private Key", on_click=self.show_private_key,
                                style=ft.ButtonStyle(color="#ffffff", bgcolor="#dc3545", padding=15)
                            ),
                            self.copy_button
                        ], alignment=ft.MainAxisAlignment.CENTER)
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                    padding=20, margin=15, bgcolor="#1a0f0f", border_radius=15,
                    alignment=ft.Alignment(0, 0), expand=True
                )
            ]),
            expand=True, padding=10, bgcolor="#2c1a1a", alignment=ft.Alignment(0, 0)
        )
    
    def show_private_key(self, e):
        password = self.password.value
        
        if not password:
            self.app.show_snackbar("Please enter password", "error")
            return
        
        try:
            target_address = self.wallet_address
            if not target_address and hasattr(self.app.wallet_core, 'current_wallet_address'):
                target_address = self.app.wallet_core.current_wallet_address
            
            if not target_address:
                self.app.show_snackbar("No wallet selected", "error")
                return
            
            if hasattr(self.app.wallet_core, 'export_private_key'):
                private_key = self.app.wallet_core.export_private_key(target_address, password)
                if private_key:
                    self.private_key_display.value = private_key
                    self.private_key_display.visible = True
                    self.copy_button.visible = True
                    self.app.page.update()
                    self.app.show_snackbar("✅ Private key retrieved", "success")
                else:
                    self.app.show_snackbar("❌ Failed to export private key - wrong password?", "error")
            else:
                self.app.show_snackbar("❌ Export not supported", "error")
                
        except Exception as ex:
            self.app.show_snackbar(f"❌ Error: {str(ex)}", "error")
    
    def copy_private_key(self, e):
        if self.private_key_display.value:
            try:
                self.app.page.set_clipboard_async(self.private_key_display.value)
            except AttributeError:
                # Fallback for different Flet versions
                import pyperclip
                pyperclip.copy(self.private_key_display.value)
            self.app.show_snackbar("✅ Private key copied to clipboard", "success")
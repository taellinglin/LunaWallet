import flet as ft

class ExportKeyPage:
    def __init__(self, app, on_back, wallet_address=None):
        self.app = app
        self.on_back = on_back
        self.wallet_address = wallet_address
        
        # Form fields
        self.password = ft.TextField(
            label="🔒 Enter Password",
            password=True,
            can_reveal_password=True,
            hint_text="Enter your wallet password",
            width=400 if not app.is_mobile else 300
        )
        self.private_key_display = ft.TextField(
            label="🔑 Your Private Key",
            multiline=True,
            read_only=True,
            width=400 if not app.is_mobile else 300,
            height=100,
            visible=False
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
                            color="#FF6B6B",
                            text_align="center"
                        )
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                    padding=20,
                    margin=10,
                    bgcolor="#2a1e1e",
                    border_radius=10
                ),
                
                # Form
                ft.Container(
                    content=ft.Column([
                        self.password,
                        self.private_key_display,
                        
                        ft.Container(height=20),
                        
                        ft.Row([
                            ft.ElevatedButton(
                                "👁️ Show Private Key",
                                on_click=self.show_private_key,
                                style=ft.ButtonStyle(
                                    color="#ffffff",
                                    bgcolor="#dc3545",
                                    padding=15
                                )
                            ),
                            ft.ElevatedButton(
                                "📋 Copy to Clipboard",
                                icon=ft.Icons.COPY,
                                on_click=self.copy_private_key,
                                style=ft.ButtonStyle(
                                    color="#ffffff", 
                                    bgcolor="#dc3545",
                                    padding=15
                                ),
                                visible=False
                            )
                        ], alignment=ft.MainAxisAlignment.CENTER)
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
    
    def show_private_key(self, e):
        password = self.password.value
        
        if not password:
            self.app.show_snackbar("Please enter password", "error")
            return
        
        try:
            # Get the current wallet address to export
            target_address = self.wallet_address
            if not target_address and hasattr(self.app.wallet_core, 'current_wallet_address'):
                target_address = self.app.wallet_core.current_wallet_address
            
            if not target_address:
                self.app.show_snackbar("No wallet selected", "error")
                return
            
            # Export private key for the specific wallet
            if hasattr(self.app.wallet_core, 'export_private_key'):
                private_key = self.app.wallet_core.export_private_key(target_address, password)
                if private_key:
                    self.private_key_display.value = private_key
                    self.private_key_display.visible = True
                    
                    # Show copy button
                    for control in self.app.page.controls[0].content.controls:
                        if isinstance(control, ft.Container) and hasattr(control.content, 'controls'):
                            for btn in control.content.controls[-1].controls:
                                if "Copy to Clipboard" in getattr(btn, 'text', ''):
                                    btn.visible = True
                    
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
            self.app.page.set_clipboard(self.private_key_display.value)
            self.app.show_snackbar("✅ Private key copied to clipboard", "success")
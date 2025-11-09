import flet as ft

class ReceivePage:
    def __init__(self, app, on_back):
        self.app = app
        self.on_back = on_back
        
    def create(self):
        # Get wallet address
        wallet_info = self.app.wallet_core.get_wallet_info()
        address = wallet_info.get('address', 'No wallet available') if wallet_info else 'No wallet available'
        
        return ft.Container(
            content=ft.Column([
                # Header
                ft.Row([
                    ft.IconButton(
                        icon=ft.Icons.ARROW_BACK,
                        icon_color="#f8d7da",
                        on_click=lambda e: self.on_back()
                    ),
                    ft.Text("📥 Receive Luna", size=24, weight="bold", color="#f8d7da"),
                    ft.Container(expand=True)
                ]),
                
                ft.Divider(color="#5c2e2e"),
                
                # Content
                ft.Container(
                    content=ft.Column([
                        ft.Text("👛 Your Wallet Address", size=18, color="#f8d7da"),
                        ft.Container(height=20),
                        
                        # Address display
                        ft.Container(
                            content=ft.Column([
                                ft.Text(address, size=14, color="#ffffff", selectable=True),
                                ft.Container(height=10),
                                ft.Row([
                                    ft.ElevatedButton(
                                        "📋 Copy Address",
                                        icon=ft.Icons.COPY,
                                        on_click=lambda e: self.copy_address(address),
                                        style=ft.ButtonStyle(
                                            color="#ffffff",
                                            bgcolor="#dc3545"
                                        )
                                    )
                                ], alignment=ft.MainAxisAlignment.CENTER)
                            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                            padding=20,
                            bgcolor="#1a0f0f",
                            border_radius=10
                        ),
                        
                        ft.Container(height=30),
                        
                        # QR Code placeholder
                        ft.Container(
                            content=ft.Column([
                                ft.Text("📱 QR Code", size=16, color="#f8d7da"),
                                ft.Container(
                                    content=ft.Text("🔲 QR Code\nPlaceholder", color="#f8d7da", text_align="center"),
                                    width=200,
                                    height=200,
                                    bgcolor="#1a0f0f",
                                    border_radius=10,
                                    alignment=ft.alignment.center
                                ),
                                ft.Container(height=10),
                                ft.Text("Scan to receive Luna", color="#f8d7da")
                            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                            padding=20
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
    
    def copy_address(self, address):
        self.app.page.set_clipboard(address)
        self.app.show_snackbar("✅ Address copied to clipboard", "success")
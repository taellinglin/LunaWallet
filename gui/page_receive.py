import flet as ft
import qrcode
import io
import base64

class ReceivePage:
    def __init__(self, app, on_back, wallet_address=None):
        self.app = app
        self.on_back = on_back
        self.wallet_address = wallet_address
        
    def create(self):
        address = self.wallet_address or self.get_wallet_address()
        
        return ft.Container(
            content=ft.Column([
                # Header
                ft.Row([
                    ft.IconButton(ft.Icons.ARROW_BACK, icon_color="#f8d7da", on_click=lambda e: self.on_back()),
                    ft.Text("📥 Receive Luna", size=24, weight="bold", color="#f8d7da"),
                    ft.Container(expand=True)
                ]),
                ft.Divider(color="#5c2e2e"),
                
                # Centered content container
                ft.Container(
                    content=ft.Column([
                        self._create_address_section(address),
                        ft.Container(height=20),
                        self._create_qr_section(address),
                        ft.Container(height=20),
                        self._create_instructions_section()
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                    padding=20,
                    margin=15,  # Small margin around the entire content
                    bgcolor="#1a0f0f",
                    border_radius=15,
                    alignment=ft.Alignment(0, 0),
                    expand=True  # Expand to fill available space
                )
            ]),
            expand=True,  # Fill entire window
            padding=10,   # Small outer padding
            bgcolor="#2c1a1a",
            alignment=ft.Alignment(0, 0)  # Center everything
        )
    
    def _create_address_section(self, address):
        return ft.Container(
            content=ft.Column([
                ft.Text("👛 Your Wallet Address", size=18, color="#f8d7da"),
                ft.Container(height=15),
                ft.Text(address, size=14, color="#ffffff", selectable=True, text_align="center"),
                ft.Container(height=10),
                ft.ElevatedButton(
                    "📋 Copy Address", icon=ft.Icons.COPY,
                    on_click=lambda e: self.copy_address(address),
                    style=ft.ButtonStyle(color="#ffffff", bgcolor="#dc3545")
                )
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            padding=20, bgcolor="#1a0f0f", border_radius=10,
            width=400 if not self.app.is_mobile else 300
        )
    
    def _create_qr_section(self, address):
        return ft.Container(
            content=ft.Column([
                ft.Text("📱 QR Code", size=16, color="#f8d7da"),
                ft.Container(height=10),
                self._generate_qr_code(address),
                ft.Container(height=5),
                ft.Text("Scan to receive Luna", color="#f8d7da", size=12)
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER)
        )
    
    def _create_instructions_section(self):
        return ft.Container(
            content=ft.Column([
                ft.Text("💡 How to receive funds:", size=14, color="#f8d7da", weight="bold"),
                ft.Container(height=8),
                ft.Text("1. Share your address or QR code", size=12, color="#f8d7da"),
                ft.Text("2. Wait for sender to complete transaction", size=12, color="#f8d7da"),
                ft.Text("3. Funds will appear in your wallet", size=12, color="#f8d7da"),
            ]),
            padding=15, bgcolor="#1a0f0f", border_radius=10,
            width=400 if not self.app.is_mobile else 300
        )
    
    def get_wallet_address(self):
        try:
            if hasattr(self.app, 'wallet_core') and self.app.wallet_core:
                if hasattr(self.app.wallet_core, 'current_wallet_address') and self.app.wallet_core.current_wallet_address:
                    return self.app.wallet_core.current_wallet_address
                if hasattr(self.app.wallet_core, 'wallets') and self.app.wallet_core.wallets:
                    if isinstance(self.app.wallet_core.wallets, dict):
                        addresses = list(self.app.wallet_core.wallets.keys())
                        return addresses[0] if addresses else "No wallet available"
                    elif isinstance(self.app.wallet_core.wallets, list) and self.app.wallet_core.wallets:
                        return self.app.wallet_core.wallets[0].get('address', 'No address')
            if hasattr(self.app.wallet_core, 'get_wallet_info'):
                wallet_info = self.app.wallet_core.get_wallet_info()
                return wallet_info.get('address', 'No wallet available')
            return "No wallet available"
        except Exception as e:
            print(f"Error getting wallet address: {e}")
            return "Error loading address"
    
    def _generate_qr_code(self, address):
        try:
            if not address or address in ["No wallet available", "Error loading address"]:
                return self._create_qr_placeholder("No valid address")
            
            qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=8, border=2)
            qr.add_data(address)
            qr.make(fit=True)
            
            buffer = io.BytesIO()
            qr.make_image(fill_color="black", back_color="white").save(buffer, format="PNG")
            img_base64 = base64.b64encode(buffer.getvalue()).decode()
            
            return ft.Container(
                content=ft.Image(src=f"data:image/png;base64,{img_base64}", width=180, height=180, fit="contain"),
                width=200, height=200, bgcolor="#ffffff", border_radius=10, padding=10,
                alignment=ft.Alignment(0, 0)
            )
        except ImportError:
            return self._create_qr_placeholder("QR Code\nNot Available", ft.Icons.WARNING, "#ffd700")
        except Exception as e:
            print(f"Error generating QR code: {e}")
            return self._create_qr_placeholder("QR Code\nError", ft.Icons.ERROR, "#dc3545")
    
    def _create_qr_placeholder(self, text, icon=ft.Icons.QR_CODE, color="#5c2e2e"):
        return ft.Container(
            content=ft.Column([
                ft.Icon(icon, size=50, color=color),
                ft.Text(text, size=12, color=color, text_align="center")
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=5),
            width=200, height=200, alignment=ft.Alignment(0, 0), bgcolor="#ffffff", border_radius=10
        )
    
    def copy_address(self, address):
        if address and address not in ["No wallet available", "Error loading address"]:
            try:
                self.app.page.set_clipboard_async(address)
                self.app.show_snackbar("✅ Address copied to clipboard", "success")
            except AttributeError:
                # Fallback for different Flet versions
                import pyperclip
                pyperclip.copy(address)
                self.app.show_snackbar("✅ Address copied to clipboard", "success")
        else:
            self.app.show_snackbar("❌ No valid address to copy", "error")
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
        # Get wallet address - use provided address or get from wallet
        address = self.wallet_address or self.get_wallet_address()
        
        # Generate QR code
        qr_code_image = self.generate_qr_code(address)
        
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
                                ft.Text(
                                    address, 
                                    size=14, 
                                    color="#ffffff", 
                                    selectable=True,
                                    text_align="center"
                                ),
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
                            border_radius=10,
                            width=400
                        ),
                        
                        ft.Container(height=30),
                        
                        # QR Code
                        ft.Container(
                            content=ft.Column([
                                ft.Text("📱 QR Code", size=16, color="#f8d7da"),
                                ft.Container(
                                    content=qr_code_image,
                                    width=200,
                                    height=200,
                                    bgcolor="#ffffff",
                                    border_radius=10,
                                    alignment=ft.alignment.center,
                                    padding=10
                                ),
                                ft.Container(height=10),
                                ft.Text("Scan to receive Luna", color="#f8d7da", size=12)
                            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                            padding=20
                        ),
                        
                        ft.Container(height=20),
                        
                        # Instructions
                        ft.Container(
                            content=ft.Column([
                                ft.Text("💡 How to receive funds:", size=14, color="#f8d7da", weight="bold"),
                                ft.Container(height=8),
                                ft.Text("1. Share your address or QR code", size=12, color="#f8d7da"),
                                ft.Text("2. Wait for the sender to complete the transaction", size=12, color="#f8d7da"),
                                ft.Text("3. Funds will appear in your wallet", size=12, color="#f8d7da"),
                            ]),
                            padding=15,
                            bgcolor="#1a0f0f",
                            border_radius=10,
                            width=400
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
    
    def get_wallet_address(self):
        """Get the current wallet address"""
        try:
            # Method 1: Try to get current wallet address from app
            if hasattr(self.app, 'wallet_core') and self.app.wallet_core:
                # Try to get from current wallet address
                if hasattr(self.app.wallet_core, 'current_wallet_address') and self.app.wallet_core.current_wallet_address:
                    return self.app.wallet_core.current_wallet_address
                
                # Method 2: Try to get from wallets collection
                if hasattr(self.app.wallet_core, 'wallets') and self.app.wallet_core.wallets:
                    # If wallets is a dictionary
                    if isinstance(self.app.wallet_core.wallets, dict):
                        wallet_addresses = list(self.app.wallet_core.wallets.keys())
                        if wallet_addresses:
                            return wallet_addresses[0]
                    # If wallets is a list
                    elif isinstance(self.app.wallet_core.wallets, list) and len(self.app.wallet_core.wallets) > 0:
                        return self.app.wallet_core.wallets[0].get('address', 'No address')
            
            # Method 3: Try get_wallet_info method
            if hasattr(self.app.wallet_core, 'get_wallet_info'):
                wallet_info = self.app.wallet_core.get_wallet_info()
                if wallet_info and wallet_info.get('address'):
                    return wallet_info['address']
            
            return "No wallet available"
            
        except Exception as e:
            print(f"Error getting wallet address: {e}")
            return "Error loading address"
    
    def generate_qr_code(self, address):
        """Generate QR code image for the wallet address"""
        try:
            if address and address != "No wallet available" and address != "Error loading address":
                # Create QR code
                qr = qrcode.QRCode(
                    version=1,
                    error_correction=qrcode.constants.ERROR_CORRECT_L,
                    box_size=8,
                    border=2,
                )
                qr.add_data(address)
                qr.make(fit=True)
                
                # Create QR code image
                qr_img = qr.make_image(fill_color="black", back_color="white")
                
                # Convert to bytes
                buffer = io.BytesIO()
                qr_img.save(buffer, format="PNG")
                buffer.seek(0)
                
                # Convert to base64 for Flet Image
                img_bytes = buffer.getvalue()
                img_base64 = base64.b64encode(img_bytes).decode()
                
                return ft.Image(
                    src_base64=img_base64,
                    width=180,
                    height=180,
                    fit=ft.ImageFit.CONTAIN
                )
            else:
                # Return placeholder if no valid address
                return ft.Container(
                    content=ft.Column([
                        ft.Icon(ft.Icons.QR_CODE, size=50, color="#5c2e2e"),
                        ft.Text("No valid address", size=12, color="#5c2e2e", text_align="center")
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=5),
                    alignment=ft.alignment.center
                )
                
        except ImportError:
            # QR code library not available
            return ft.Container(
                content=ft.Column([
                    ft.Icon(ft.Icons.WARNING, size=40, color="#ffd700"),
                    ft.Text("QR Code\nNot Available", size=12, color="#ffd700", text_align="center"),
                    ft.Text("Install: pip install qrcode[pil]", size=10, color="#a8a8a8", text_align="center")
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=5),
                alignment=ft.alignment.center
            )
        except Exception as e:
            print(f"Error generating QR code: {e}")
            return ft.Container(
                content=ft.Column([
                    ft.Icon(ft.Icons.ERROR, size=40, color="#dc3545"),
                    ft.Text("QR Code\nError", size=12, color="#dc3545", text_align="center")
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=5),
                alignment=ft.alignment.center
            )
    
    def copy_address(self, address):
        if address and address != "No wallet available" and address != "Error loading address":
            self.app.page.set_clipboard(address)
            self.app.show_snackbar("✅ Address copied to clipboard", "success")
        else:
            self.app.show_snackbar("❌ No valid address to copy", "error")
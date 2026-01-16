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
                    ft.Column([
                        ft.Text("Receive", size=22, weight="bold", color="#f8d7da"),
                        ft.Text("Share your address or QR code", size=12, color="#a8a8a8"),
                    ], spacing=2),
                    ft.Container(expand=True)
                ]),
                ft.Divider(color="#5c2e2e"),
                
                # Centered content container
                ft.Container(
                    content=ft.Column([
                        self._create_address_section(address),
                        ft.Container(height=16),
                        self._create_qr_section(address),
                        ft.Container(height=16),
                        self._create_instructions_section()
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                    padding=20,
                    margin=ft.margin.symmetric(vertical=6),
                    bgcolor="#1a0f0f",
                    border_radius=12,
                    border=ft.border.all(1, "#5c2e2e"),
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
                ft.Text("Wallet Address", size=14, color="#f8d7da", weight="bold"),
                ft.Container(height=10),
                ft.Text(address, size=13, color="#ffffff", selectable=True, text_align="center"),
                ft.Container(height=8),
                ft.ElevatedButton(
                    "Copy Address",
                    icon=ft.Icons.COPY,
                    on_click=lambda e: self.copy_address(address),
                    style=ft.ButtonStyle(
                        color="#ffffff",
                        bgcolor="#dc3545",
                        padding=ft.padding.symmetric(horizontal=18, vertical=12),
                        shape=ft.RoundedRectangleBorder(radius=8)
                    )
                )
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            padding=16, bgcolor="#1a0f0f", border_radius=10,
            width=400 if not self.app.is_mobile else 300
        )
    
    def _create_qr_section(self, address):
        return ft.Container(
            content=ft.Column([
                ft.Text("QR Code", size=13, color="#f8d7da", weight="bold"),
                ft.Container(height=8),
                self._generate_qr_code(address),
                ft.Container(height=5),
                ft.Text("Scan to receive", color="#a8a8a8", size=11)
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER)
        )
    
    def _create_instructions_section(self):
        return ft.Container(
            content=ft.Column([
                ft.Text("How it works", size=13, color="#f8d7da", weight="bold"),
                ft.Container(height=6),
                ft.Text("Share your address or QR code", size=11, color="#a8a8a8"),
                ft.Text("Funds appear after network confirmation", size=11, color="#a8a8a8"),
            ]),
            padding=12, bgcolor="#1a0f0f", border_radius=10,
            expand=True
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
            
            try:
                from qrcode.image.pure import PyPNGImage

                png_img = qr.make_image(image_factory=PyPNGImage)
                buf = io.BytesIO()
                png_img.save(buf)
                png_base64 = base64.b64encode(buf.getvalue()).decode()
                png_src = f"data:image/png;base64,{png_base64}"
                qr_control = ft.Image(src=png_src, width=180, height=180, fit="contain")
            except Exception:
                from qrcode.image.svg import SvgImage

                svg_img = qr.make_image(image_factory=SvgImage)
                svg_bytes = svg_img.to_string()
                svg_base64 = base64.b64encode(svg_bytes).decode()
                svg_src = f"data:image/svg+xml;base64,{svg_base64}"
                qr_control = ft.Image(src=svg_src, width=180, height=180, fit="contain")

            return ft.Container(
                content=qr_control,
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
                print(f"DEBUG: copy_address called with: {address[:12]}...")
                
                # Prefer async clipboard on mobile
                if hasattr(self.app.page, 'set_clipboard_async'):
                    print("DEBUG: Using page.set_clipboard_async()")
                    async def _do_copy():
                        try:
                            await self.app.page.set_clipboard_async(address)
                        except Exception as e:
                            print(f"DEBUG: Async clipboard error: {e}")
                    if hasattr(self.app.page, 'run_task'):
                        self.app.page.run_task(_do_copy)
                    else:
                        self.app.page.set_clipboard_async(address)
                elif hasattr(self.app.page, 'set_clipboard'):
                    print("DEBUG: Using page.set_clipboard()")
                    self.app.page.set_clipboard(address)
                else:
                    # Fallback for different Flet versions
                    print("DEBUG: Using pyperclip fallback")
                    import pyperclip
                    pyperclip.copy(address)
                
                print(f"DEBUG: Address copied to clipboard: {address[:12]}...")
                print("DEBUG: About to show snackbar...")
                
                # Show snackbar - use a small delay to ensure clipboard operation completes
                def show_snack():
                    import time
                    time.sleep(0.1)  # Small delay
                    print("DEBUG: Inside show_snack() callback")
                    try:
                        print("DEBUG: Calling app.show_snackbar()...")
                        self.app.show_snackbar("✅ Address copied to clipboard", "success")
                        print("DEBUG: Snackbar call completed")
                    except Exception as e:
                        print(f"DEBUG: Error in snackbar callback: {e}")
                        import traceback
                        traceback.print_exc()
                
                print("DEBUG: Checking if page.run_thread exists...")
                if hasattr(self.app.page, 'run_thread'):
                    print("DEBUG: Using page.run_thread(show_snack)")
                    self.app.page.run_thread(show_snack)
                else:
                    print("DEBUG: Calling show_snack() directly")
                    show_snack()
                    
            except Exception as e:
                print(f"DEBUG: Clipboard error in primary method: {e}")
                import traceback
                traceback.print_exc()
                # Final fallback
                try:
                    print("DEBUG: Trying pyperclip fallback...")
                    import pyperclip
                    pyperclip.copy(address)
                    print("DEBUG: Pyperclip copy succeeded")
                    
                    def show_snack():
                        import time
                        time.sleep(0.1)
                        try:
                            print("DEBUG: Showing snackbar from pyperclip path")
                            self.app.show_snackbar("✅ Address copied to clipboard", "success")
                        except Exception as e:
                            print(f"DEBUG: Error in snackbar callback: {e}")
                            import traceback
                            traceback.print_exc()
                    
                    if hasattr(self.app.page, 'run_thread'):
                        self.app.page.run_thread(show_snack)
                    else:
                        show_snack()
                        
                except Exception as e2:
                    print(f"DEBUG: Pyperclip error: {e2}")
                    import traceback
                    traceback.print_exc()
                    def show_error():
                        import time
                        time.sleep(0.1)
                        try:
                            print("DEBUG: Showing error snackbar")
                            self.app.show_snackbar("❌ Could not copy to clipboard", "error")
                        except Exception as e:
                            print(f"DEBUG: Error in error snackbar callback: {e}")
                            import traceback
                            traceback.print_exc()
                    
                    if hasattr(self.app.page, 'run_thread'):
                        self.app.page.run_thread(show_error)
                    else:
                        show_error()
        else:
            print("DEBUG: Invalid address detected")
            def show_invalid():
                import time
                time.sleep(0.1)
                try:
                    print("DEBUG: Showing invalid address snackbar")
                    self.app.show_snackbar("❌ No valid address to copy", "error")
                except Exception as e:
                    print(f"DEBUG: Error in invalid snackbar callback: {e}")
                    import traceback
                    traceback.print_exc()
            if hasattr(self.app.page, 'run_thread'):
                self.app.page.run_thread(show_invalid)
            else:
                show_invalid()
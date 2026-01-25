import flet as ft

class ExportKeyPage:
    def __init__(self, app, on_back, wallet_address=None):
        self.app = app
        self.on_back = on_back
        self.wallet_address = wallet_address
        self._field_width = 420 if not app.is_mobile else 320
        
        # Form fields
        self.password = ft.TextField(
            label="Password",
            password=True,
            can_reveal_password=True,
            hint_text="Enter your wallet password",
            width=self._field_width,
            bgcolor="#1a0f0f",
            border_color="#5c2e2e",
            focused_border_color="#dc3545",
            color="#f8d7da",
            label_style=ft.TextStyle(color="#f8d7da"),
            text_style=ft.TextStyle(color="#f8d7da"),
            prefix_icon=ft.Icons.LOCK,
        )
        self.private_key_display = ft.TextField(
            label="Private Key",
            multiline=True,
            read_only=True,
            width=self._field_width,
            height=120,
            visible=False,
            bgcolor="#140b0b",
            border_color="#5c2e2e",
            focused_border_color="#dc3545",
            color="#f8d7da",
            label_style=ft.TextStyle(color="#f8d7da"),
            text_style=ft.TextStyle(color="#f8d7da", font_family="monospace"),
            prefix_icon=ft.Icons.KEY,
        )
        self.copy_button = ft.ElevatedButton(
            "Copy to Clipboard",
            icon=ft.Icons.COPY,
            on_click=self.copy_private_key,
            style=ft.ButtonStyle(
                color="#ffffff",
                bgcolor="#dc3545",
                padding=ft.padding.symmetric(horizontal=18, vertical=12),
                shape=ft.RoundedRectangleBorder(radius=8)
            ),
            visible=False
        )
        
    def create(self):
        return ft.Container(
            content=ft.Column([
                # Header
                ft.Row([
                    ft.IconButton(ft.Icons.ARROW_BACK, icon_color="#f8d7da", on_click=lambda e: self.on_back()),
                    ft.Column([
                        ft.Text("Export Private Key", size=22, weight="bold", color="#f8d7da"),
                        ft.Text("For advanced users only", size=12, color="#a8a8a8"),
                    ], spacing=2),
                    ft.Container(expand=True)
                ]),
                ft.Divider(color="#5c2e2e"),
                
                # Warning
                ft.Container(
                    content=ft.Row([
                        ft.Container(
                            width=4,
                            bgcolor="#ff6b6b",
                            border_radius=4
                        ),
                        ft.Column([
                            ft.Text("Security Warning", size=16, color="#ff6b6b", weight="bold"),
                            ft.Text(
                                "Never share your private key. Anyone with this key can access your funds.",
                                color="#f0b4b4",
                                size=11
                            ),
                        ], spacing=4, expand=True)
                    ], spacing=12),
                    padding=16,
                    margin=ft.margin.symmetric(vertical=8),
                    bgcolor="#2a1e1e",
                    border_radius=10,
                    border=ft.border.all(1, "#5c2e2e"),
                    expand=False
                ),
                
                # Centered form container
                ft.Container(
                    content=ft.Column([
                        ft.Text("Verify Password", size=14, color="#f8d7da", weight="bold", text_align="center"),
                        ft.Text(
                            "Enter your wallet password to reveal the private key.",
                            size=11,
                            color="#a8a8a8",
                            text_align="center"
                        ),
                        ft.Container(height=10),
                        self.password,
                        ft.Container(height=10),
                        self.private_key_display,
                        ft.Container(height=12),
                        ft.Row([
                            ft.ElevatedButton(
                                "Show Private Key",
                                on_click=self.show_private_key,
                                icon=ft.Icons.VISIBILITY,
                                style=ft.ButtonStyle(
                                    color="#ffffff",
                                    bgcolor="#dc3545",
                                    padding=ft.padding.symmetric(horizontal=18, vertical=12),
                                    shape=ft.RoundedRectangleBorder(radius=8)
                                )
                            ),
                            self.copy_button
                        ], alignment=ft.MainAxisAlignment.CENTER, spacing=10)
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=0),
                    padding=20,
                    margin=ft.margin.symmetric(vertical=8),
                    bgcolor="#1a0f0f",
                    border_radius=12,
                    border=ft.border.all(1, "#5c2e2e"),
                    alignment=ft.Alignment(0, 0),
                    expand=True
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
                    self.app.show_snackbar("Failed to export private key - wrong password?", "error")
            else:
                self.app.show_snackbar("Export not supported", "error")
                
        except Exception as ex:
            self.app.show_snackbar(f"Error: {str(ex)}", "error")
    
    def copy_private_key(self, e):
        if self.private_key_display.value:
            try:
                # Prefer async clipboard when available
                if hasattr(self.app.page, 'set_clipboard_async'):
                    async def _do_copy():
                        try:
                            await self.app.page.set_clipboard_async(self.private_key_display.value)
                        except Exception as async_err:
                            print(f"DEBUG: Async clipboard error: {async_err}")
                    if hasattr(self.app.page, 'run_task'):
                        self.app.page.run_task(_do_copy)
                    else:
                        self.app.page.set_clipboard_async(self.private_key_display.value)
                elif hasattr(self.app.page, 'set_clipboard'):
                    self.app.page.set_clipboard(self.private_key_display.value)
                else:
                    # Fallback for different Flet versions
                    import pyperclip
                    pyperclip.copy(self.private_key_display.value)
                
                print(f"DEBUG: Private key copied to clipboard")
                
                # Show snackbar on main thread
                def show_snack():
                    try:
                        self.app.show_snackbar("✅ Private key copied to clipboard", "success")
                    except Exception as e:
                        print(f"DEBUG: Error in snackbar callback: {e}")
                
                if hasattr(self.app.page, 'run_thread'):
                    self.app.page.run_thread(show_snack)
                else:
                    show_snack()
                    
            except Exception as e:
                print(f"DEBUG: Clipboard error: {e}")
                try:
                    import pyperclip
                    pyperclip.copy(self.private_key_display.value)
                    
                    def show_snack():
                        try:
                            self.app.show_snackbar("✅ Private key copied to clipboard", "success")
                        except Exception as e:
                            print(f"DEBUG: Error in snackbar callback: {e}")
                    
                    if hasattr(self.app.page, 'run_thread'):
                        self.app.page.run_thread(show_snack)
                    else:
                        show_snack()
                        
                except Exception as e2:
                    print(f"DEBUG: Pyperclip error: {e2}")
                    def show_error():
                        try:
                            self.app.show_snackbar("Could not copy to clipboard", "error")
                        except Exception as e:
                            print(f"DEBUG: Error in snackbar callback: {e}")
                    
                    if hasattr(self.app.page, 'run_thread'):
                        self.app.page.run_thread(show_error)
                    else:
                        show_error()
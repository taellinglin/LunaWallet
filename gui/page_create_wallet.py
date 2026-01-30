import flet as ft
import threading
import time
class CreateWalletPage:
    def __init__(self, app, on_back, on_wallet_created):
        self.app = app
        self.on_back = on_back
        self.on_wallet_created = on_wallet_created
        self._field_width = 420 if not app.is_mobile else 320
        
        # Form fields
        self.wallet_name = ft.TextField(
            label="Wallet Name",
            hint_text="My Wallet",
            value="My Wallet",  # Default value
            width=self._field_width,
            border_color="#5c2e2e",
            focused_border_color="#dc3545",
            text_size=14,
            color="#f8d7da",
            cursor_color="#dc3545",
            label_style=ft.TextStyle(color="#f8d7da"),
            bgcolor="#1a0f0f",
        )
        self.password = ft.TextField(
            label="Password", 
            password=True,
            can_reveal_password=True,
            hint_text="Password to encrypt wallet",
            width=self._field_width,
            border_color="#5c2e2e",
            focused_border_color="#dc3545",
            text_size=14,
            color="#f8d7da",
            cursor_color="#dc3545",
            label_style=ft.TextStyle(color="#f8d7da"),
            bgcolor="#1a0f0f",
        )
        self.confirm_password = ft.TextField(
            label="Confirm Password",
            password=True,
            can_reveal_password=True, 
            hint_text="Confirm password",
            width=self._field_width,
            border_color="#5c2e2e",
            focused_border_color="#dc3545",
            text_size=14,
            color="#f8d7da",
            cursor_color="#dc3545",
            label_style=ft.TextStyle(color="#f8d7da"),
            bgcolor="#1a0f0f",
        )
        
        # Create button reference for updating state
        self.create_button = ft.Button(
            "Create Wallet",
            on_click=self.create_wallet,
            style=ft.ButtonStyle(
                color="#ffffff",
                bgcolor="#dc3545",
                padding=ft.Padding.symmetric(horizontal=18, vertical=12),
                shape=ft.RoundedRectangleBorder(radius=8)
            ),
            width=160
        )
        # Progress indicator（必ず__init__で初期化）
        self.progress_indicator = ft.ProgressRing(
            color="#dc3545",
            visible=False,
            width=20,
            height=20
        )

    def _on_back(self):
        """Back button logic: always go to create/import screen."""
        self.app.show_lock_page(
            title="Welcome to Luna Wallet",
            subtitle="Create or import a wallet to get started",
            show_create=True,
            wallet_exists=False
        )
        # Progress indicator
        self.progress_indicator = ft.ProgressRing(
            color="#dc3545",
            visible=False,
            width=20,
            height=20
        )
        
    def create(self):
        return ft.Container(
            content=ft.Column([
                # Header
                ft.Row([
                    ft.IconButton(
                        icon=ft.Icons.ARROW_BACK,
                        icon_color="#f8d7da",
                        on_click=lambda e: self._on_back(),
                    ),
                    ft.Column([
                        ft.Text("Create Wallet", size=22, weight="bold", color="#f8d7da"),
                        ft.Text("Set up a new wallet", size=12, color="#a8a8a8"),
                    ], spacing=2),
                    ft.Container(expand=True)
                ]),
                ft.Divider(color="#5c2e2e"),
                
                # Centered form content
                ft.Container(
                    content=ft.Column([
                        ft.Text("Wallet Details", size=14, color="#f8d7da", weight="bold", text_align="center"),
                        ft.Text("Use a strong password to protect your keys", size=11, color="#a8a8a8", text_align="center"),
                        ft.Container(height=12),
                        
                        # Form fields
                        self.wallet_name,
                        ft.Container(height=10),
                        self.password,
                        ft.Container(height=10),
                        self.confirm_password,
                        ft.Container(height=16),
                        
                        # Create button with progress indicator
                        ft.Row([
                            self.create_button,
                            self.progress_indicator
                        ], alignment=ft.MainAxisAlignment.CENTER, spacing=10)
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                    padding=20,
                    margin=ft.margin.symmetric(vertical=6),
                    bgcolor="#1a0f0f",
                    border_radius=12,
                    border=ft.border.all(1, "#5c2e2e"),
                    alignment=ft.Alignment(0, 0),
                    expand=True
                ),
            ]),
            expand=True,
            padding=10,
            bgcolor="#2c1a1a",
            alignment=ft.Alignment(0, 0)
        )
    
    def _show_loading_state(self, loading=True):
        """Show or hide loading state"""
        self.create_button.disabled = loading
        self.create_button.text = "Creating Wallet..." if loading else "Create Wallet"
        self.progress_indicator.visible = loading
        if hasattr(self.app, 'page') and self.app.page:
            self.app.page.update()
    
    def _validate_form(self):
        """Validate form inputs and return error message or None if valid"""
        wallet_name = self.wallet_name.value.strip()
        password = self.password.value
        confirm_password = self.confirm_password.value
        
        if not wallet_name:
            return "Please enter wallet name"
            
        if not password:
            return "Please enter password"
            
        if password != confirm_password:
            return "Passwords do not match"
            
        if len(password) < 8:
            return "Password must be at least 8 characters"
            
        return None

    def _label_exists(self, label: str) -> bool:
        try:
            if not label:
                return False
            label_lower = label.strip().lower()
            wallets = getattr(self.app.wallet_core, 'wallets', None)
            if isinstance(wallets, dict):
                for w in wallets.values():
                    if isinstance(w, dict):
                        existing = str(w.get('label', '')).strip().lower()
                        if existing and existing == label_lower:
                            return True
            elif isinstance(wallets, list):
                for w in wallets:
                    if isinstance(w, dict):
                        existing = str(w.get('label', '')).strip().lower()
                        if existing and existing == label_lower:
                            return True
        except Exception:
            return False
        return False
        
    def create_wallet(self, e):
        # Validate form
        wallet_name = self.wallet_name.value.strip()
        password = self.password.value
        confirm_password = self.confirm_password.value
        
        if not wallet_name:
            self.app.show_snackbar("Please enter wallet name", "error")
            return

        if self._label_exists(wallet_name):
            self.app.show_snackbar("Wallet name already exists. Please choose a different name.", "error")
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
        
        # Show loading state
        self._show_loading_state(True)
        
        def create_and_unlock():
            import time
            try:
                print("DEBUG: Starting wallet creation...")
                # Wait for wallet_core to be ready (max 5 seconds)
                ready = False
                for _ in range(50):
                    wallet_core = getattr(self.app, 'wallet_core', None)
                    services_ready = getattr(self.app, '_services_ready', True)
                    if wallet_core:
                        if not services_ready:
                            print("DEBUG: wallet_core ready, other services still initializing")
                        ready = True
                        break
                    if hasattr(self.app, '_ensure_services'):
                        try:
                            self.app._ensure_services()
                        except Exception as svc_err:
                            print(f"DEBUG: Service init failed before wallet creation: {svc_err}")
                    time.sleep(0.1)
                if not ready:
                    print("ERROR: Wallet core still not initialized after waiting!")
                    self._show_loading_state(False)
                    svc_errors = getattr(self.app, '_services_errors', {}) or {}
                    if svc_errors:
                        self.app.show_snackbar(
                            f"Wallet core not initialized. Details: {svc_errors}",
                            "error"
                        )
                    else:
                        self.app.show_snackbar("Wallet core not initialized. Please restart the app.", "error")
                    return
                # Ensure SM4 wallet encryption is used (lunalib 2.4.0+)
                try:
                    import os
                    os.environ.setdefault("LUNALIB_WALLET_CIPHER", "sm4")
                    os.environ.setdefault("LUNALIB_SM4_USE_GPU", "1")
                except Exception:
                    pass
                # Create the wallet
                wallet_data = self.app.wallet_core.create_wallet(wallet_name, password)
                print(f"DEBUG: Wallet creation result: {wallet_data}")
                if wallet_data:
                    print("DEBUG: Wallet created successfully!")
                    
                    # Save to storage for persistence
                    try:
                        self.app.save_wallet_data(force_save=True)
                        print("DEBUG: Wallet saved to storage")
                    except Exception as db_save_ex:
                        print(f"DEBUG: Failed to save wallet to storage: {db_save_ex}")
                    
                    # Set app state to unlocked
                    self.app.is_locked = False
                    self.app.last_activity_time = time.time()
                    def update_ui():
                        try:
                            self._show_loading_state(False)
                            self.app.show_snackbar("Wallet created successfully!", "success")
                            if self.on_wallet_created:
                                self.on_wallet_created()
                            else:
                                print("DEBUG: No callback found, going to wallet page directly")
                                self.app.show_wallet_page()
                            if hasattr(self.app, 'wallet_page') and self.app.wallet_page:
                                if hasattr(self.app.wallet_page, '_refresh_sidebar_wallets'):
                                    self.app.wallet_page._refresh_sidebar_wallets()
                        except Exception as ui_error:
                            print(f"DEBUG: UI update error: {ui_error}")
                            if self.on_wallet_created:
                                self.on_wallet_created()
                    if hasattr(self.app, 'page') and self.app.page:
                        self.app.page.run_thread(update_ui)
                    else:
                        update_ui()
                else:
                    def update_ui_fail():
                        self._show_loading_state(False)
                        self.app.show_snackbar("Failed to create wallet", "error")
                    if hasattr(self.app, 'page') and self.app.page:
                        self.app.page.run_thread(update_ui_fail)
                    else:
                        update_ui_fail()
            except Exception as ex:
                print(f"DEBUG: Exception in wallet creation: {str(ex)}")
                import traceback
                traceback.print_exc()
                def show_error(err=ex):
                    self._show_loading_state(False)
                    self.app.show_snackbar(f"Error creating wallet: {str(err)}", "error")
                if hasattr(self.app, 'page') and self.app.page:
                    self.app.page.run_thread(show_error)
                else:
                    show_error()
        
        # Start the wallet creation thread
        threading.Thread(target=create_and_unlock, daemon=True).start()
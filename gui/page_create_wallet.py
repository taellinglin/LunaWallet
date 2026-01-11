import flet as ft
import threading
import time
class CreateWalletPage:
    def __init__(self, app, on_back, on_wallet_created):
        self.app = app
        self.on_back = on_back
        self.on_wallet_created = on_wallet_created
        
        # Form fields
        self.wallet_name = ft.TextField(
            label="Wallet Name",
            hint_text="My Wallet",
            value="My Wallet",  # Default value
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
        
        # Create button reference for updating state
        self.create_button = ft.ElevatedButton(
            "Create Wallet",
            on_click=self.create_wallet,
            style=ft.ButtonStyle(
                color="#ffffff",
                bgcolor="#dc3545",
                padding=ft.padding.symmetric(horizontal=30, vertical=15),
            ),
            width=200
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
                        
                        # Create button with progress indicator
                        ft.Row([
                            self.create_button,
                            self.progress_indicator
                        ], alignment=ft.MainAxisAlignment.CENTER, spacing=10)
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                    padding=30,
                    alignment=ft.Alignment(0, 0)
                ),
            ]),
            expand=True,
            padding=20,
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
        
        # Show loading state
        self._show_loading_state(True)
        
        def create_and_unlock():
            try:
                print("DEBUG: Starting wallet creation...")
                
                # Create the wallet
                wallet_data = self.app.wallet_core.create_new_wallet(wallet_name, password)
                print(f"DEBUG: Wallet creation result: {wallet_data}")
                
                if wallet_data:
                    print("DEBUG: Wallet created successfully!")
                    
                    # Set app state to unlocked
                    self.app.is_locked = False
                    self.app.last_activity_time = time.time()
                    
                    def update_ui():
                        try:
                            # Clear loading state
                            self._show_loading_state(False)
                            
                            # Show success message
                            self.app.show_snackbar("Wallet created successfully!", "success")
                            
                            # Call the success callback
                            if self.on_wallet_created:
                                self.on_wallet_created()
                            else:
                                print("DEBUG: No callback found, going to wallet page directly")
                                self.app.show_wallet_page()
                                
                        except Exception as ui_error:
                            print(f"DEBUG: UI update error: {ui_error}")
                            # Force transition anyway
                            if self.on_wallet_created:
                                self.on_wallet_created()
                    
                    # Update UI on main thread
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
                
                def show_error():
                    self._show_loading_state(False)
                    self.app.show_snackbar(f"Error creating wallet: {str(ex)}", "error")
                
                if hasattr(self.app, 'page') and self.app.page:
                    self.app.page.run_thread(show_error)
                else:
                    show_error()
        
        # Start the wallet creation thread
        threading.Thread(target=create_and_unlock, daemon=True).start()
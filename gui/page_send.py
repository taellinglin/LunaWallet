import flet as ft

class SendPage:
    def __init__(self, app, on_back, on_send_complete, from_address=None):
        self.app = app
        self.on_back = on_back
        self.on_send_complete = on_send_complete
        self.from_address = from_address
        
        # Form fields
        field_width = 400 if not app.is_mobile else 300
        self.recipient = ft.TextField(
            label="👤 Recipient Address", 
            hint_text="Enter Luna address", 
            width=field_width
        )
        self.amount = ft.TextField(
            label="💰 Amount (LUNA)", 
            hint_text="0.00", 
            width=field_width
        )
        self.memo = ft.TextField(
            label="📝 Memo (Optional)", 
            hint_text="Add a note", 
            width=field_width
        )
        self.password = ft.TextField(
            label="🔒 Confirm Password", 
            password=True, 
            can_reveal_password=True,
            hint_text="Enter your password", 
            width=field_width
        )
        

    def _prepare_wallet_for_sending(self, password):
        """Ensure wallet is ready for transaction sending"""
        try:
            wallet = self.app.wallet_core

            # If we have a specific from_address, switch to it
            if self.from_address and self.from_address != getattr(wallet, 'address', None):
                print(f"DEBUG: Switching to wallet: {self.from_address}")
                if hasattr(wallet, 'switch_wallet'):
                    switch_success = wallet.switch_wallet(self.from_address, password)
                    if not switch_success:
                        print("DEBUG: Failed to switch wallet")
                        return False, "Failed to switch to specified wallet"
                else:
                    return False, "Wallet switching not supported"

            # Ensure wallet is unlocked
            if getattr(wallet, 'is_locked', True):
                print("DEBUG: Wallet is locked, attempting to unlock...")
                if hasattr(wallet, 'unlock_wallet'):
                    current_address = getattr(wallet, 'address', None) or getattr(wallet, 'current_wallet_address', None)
                    if current_address and password:
                        unlock_success = wallet.unlock_wallet(current_address, password)
                        if not unlock_success:
                            return False, "Failed to unlock wallet with provided password"
                    else:
                        return False, "No wallet address found or password missing"
                else:
                    return False, "Wallet unlock method not available"

            # Verify private key is available
            if not hasattr(wallet, 'private_key') or not wallet.private_key:
                return False, "No private key available for signing"

            # Refresh balances to ensure we have latest state
            wallet.refresh_balance()

            return True, "Wallet ready for sending"

        except Exception as e:
            error_msg = f"Wallet preparation error: {str(e)}"
            print(f"DEBUG: {error_msg}")
            return False, error_msg
    def get_available_balance(self):
        """Get current wallet available balance"""
        try:
            if hasattr(self.app, 'wallet_core') and self.app.wallet_core:
                # Calculate available balance (total - pending)
                return self.app.wallet_core.get_available_balance()
            return 0.0
        except Exception as e:
            print(f"DEBUG: Error getting available balance: {e}")
            return 0.0
    def _debug_wallet_state(self):
        """Debug wallet state before sending"""
        print("=" * 50)
        print("DEBUG: Wallet State Check")
        print("=" * 50)
        
        if not hasattr(self.app, 'wallet_core') or not self.app.wallet_core:
            print("❌ No wallet_core found")
            return False
            
        wallet = self.app.wallet_core
        
        # Check basic wallet state
        print(f"Wallet Address: {getattr(wallet, 'address', 'None')}")
        print(f"Wallet Locked: {getattr(wallet, 'is_locked', 'Unknown')}")
        print(f"Current Wallet Address: {getattr(wallet, 'current_wallet_address', 'None')}")
        
        # Check balances
        total_balance = self.get_current_balance()
        available_balance = self.get_available_balance()
        print(f"Total Balance: {total_balance}")
        print(f"Available Balance: {available_balance}")
        
        # Check private key availability
        has_private_key = hasattr(wallet, 'private_key') and wallet.private_key
        print(f"Private Key Available: {has_private_key}")
        if has_private_key:
            print(f"Private Key Length: {len(wallet.private_key)}")
        
        # Check if wallet has send methods
        has_send = hasattr(wallet, 'send_transaction')
        has_send_from = hasattr(wallet, 'send_transaction_from')
        print(f"Has send_transaction: {has_send}")
        print(f"Has send_transaction_from: {has_send_from}")
        
        # Check wallets collection
        if hasattr(wallet, 'wallets'):
            print(f"Wallets in collection: {len(wallet.wallets)}")
            if wallet.wallets:
                for addr, w_data in list(wallet.wallets.items())[:3]:  # Show first 3
                    print(f"  - {addr}: balance={w_data.get('balance', 0)}, locked={w_data.get('is_locked', True)}")
        
        print("=" * 50)
        return True
    def send_transaction(self, e):
        """Send transaction using the updated LunaWallet system"""
        print("DEBUG: Send transaction initiated")
        
        # Get values from form fields
        recipient = self.recipient.value.strip()
        amount_str = self.amount.value.strip()
        memo = self.memo.value.strip()
        password = self.password.value
        
        # Basic validation
        if not recipient:
            self.app.show_snackbar("Please enter recipient address", "error")
            return
        if not amount_str:
            self.app.show_snackbar("Please enter amount", "error")
            return
        if not password:
            self.app.show_snackbar("Please enter password", "error")
            return
        
        # Amount validation
        try:
            amount = float(amount_str)
            if amount <= 0:
                self.app.show_snackbar("Amount must be positive", "error")
                return
                
        except ValueError:
            self.app.show_snackbar("Invalid amount format", "error")
            return
        
        # Debug wallet state
        if not self._debug_wallet_state():
            self.app.show_snackbar("Wallet not properly initialized", "error")
            return
        
        try:
            # Prepare wallet for sending
            prep_success, prep_message = self._prepare_wallet_for_sending(password)
            if not prep_success:
                self.app.show_snackbar(prep_message, "error")
                return
            
            wallet = self.app.wallet_core
            
            # Check available balance
            available_balance = self.get_available_balance()
            if amount > available_balance:
                self.app.show_snackbar(
                    f"Insufficient available balance. Available: {available_balance:.6f} LUNA", 
                    "error"
                )
                return
            
            print(f"DEBUG: Sending {amount} LUNA from {wallet.address} to {recipient}")
            
            # Send transaction using wallet core
            success = wallet.send_transaction(recipient, amount, memo, password)
            
            # Handle result
            if success:
                print("DEBUG: Transaction sent successfully!")
                
                # Refresh balances to get updated state
                wallet.refresh_balance()
                
                # Save wallet state
                if hasattr(self.app, 'save_wallet_data'):
                    self.app.save_wallet_data(force_save=True)
                
                # Clear form
                self.recipient.value = ""
                self.amount.value = ""
                self.memo.value = ""
                self.password.value = ""
                
                # Update UI if controls exist
                if hasattr(self.recipient, 'update'):
                    self.recipient.update()
                    self.amount.update()
                    self.memo.update()
                    self.password.update()
                
                # Show success message
                success_msg = "✅ Transaction sent to mempool successfully!"
                self.app.show_snackbar(success_msg, "success")
                
                # Update balance display
                if hasattr(self, 'page') and self.page:
                    self.page.update()
                
                # Call completion callback
                self.on_send_complete()
                
            else:
                print("DEBUG: Send failed")
                self.app.show_snackbar("Failed to send transaction", "error")
                
        except Exception as ex:
            error_msg = f"Unexpected error: {str(ex)}"
            print(f"DEBUG: Unexpected error in send_transaction: {error_msg}")
            import traceback
            traceback.print_exc()
            self.app.show_snackbar(f"Error sending transaction: {str(ex)}", "error")
    def create(self):
        balance = self.get_current_balance()
        
        return ft.Container(
            content=ft.Column([
                # Header
                ft.Row([
                    ft.IconButton(
                        ft.Icons.ARROW_BACK, 
                        icon_color="#f8d7da", 
                        on_click=lambda e: self.on_back()
                    ),
                    ft.Text("📤 Send Luna", size=24, weight="bold", color="#f8d7da"),
                    ft.Container(expand=True)
                ]),
                ft.Divider(color="#5c2e2e"),
                
                # Centered form container with 128px padding
                ft.Container(
                    content=ft.Column([
                        ft.Text(
                            f"💰 Available: {balance:.6f} LUNA", 
                            size=16, 
                            color="#90EE90",
                            weight="bold"
                        ),
                        ft.Container(height=20),
                        self.recipient,
                        ft.Container(height=10),
                        self.amount,
                        ft.Container(height=10),
                        self.memo,
                        ft.Container(height=10),
                        self.password,
                        ft.Container(height=30),
                        ft.ElevatedButton(
                            "🚀 Send Transaction", 
                            on_click=self.send_transaction,
                            style=ft.ButtonStyle(
                                color="#ffffff", 
                                bgcolor="#dc3545", 
                                padding=20
                            ),
                            width=200
                        )
                    ], 
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=0
                    ),
                    padding=128,  # 128px padding as requested
                    margin=0,
                    bgcolor="#1a0f0f",
                    border_radius=15,
                    alignment=ft.alignment.center,
                    expand=True
                )
            ]),
            expand=True,
            padding=0,
            bgcolor="#2c1a1a",
            alignment=ft.alignment.center
        )
    
    def get_current_balance(self):
        """Get current wallet balance with error handling"""
        try:
            if self.from_address and hasattr(self.app.wallet_core, 'wallets'):
                if isinstance(self.app.wallet_core.wallets, dict) and self.from_address in self.app.wallet_core.wallets:
                    return self.app.wallet_core.wallets[self.from_address].get('balance', 0)
                elif isinstance(self.app.wallet_core.wallets, list):
                    for wallet in self.app.wallet_core.wallets:
                        if isinstance(wallet, dict) and wallet.get('address') == self.from_address:
                            return wallet.get('balance', 0)
            if hasattr(self.app.wallet_core, 'get_wallet_info'):
                wallet_info = self.app.wallet_core.get_wallet_info()
                return wallet_info.get('balance', 0) if wallet_info else 0
            return 0
        except Exception as e:
            print(f"DEBUG: Error getting balance: {e}")
            return 0
    
    def _debug_transaction_parameters(self, recipient, amount, memo, password):
        """Debug transaction parameters before sending"""
        print("=" * 50)
        print("DEBUG: Transaction Send Parameters")
        print("=" * 50)
        print(f"From Address: {self.from_address}")
        print(f"To Address: {recipient}")
        print(f"Amount: {amount}")
        print(f"Memo: {memo}")
        print(f"Password Length: {len(password) if password else 0}")
        
        # Check wallet state
        print(f"Wallet Locked: {self.app.is_locked}")
        print(f"Current Balance: {self.get_current_balance()}")
        
        # Check wallet core state
        if hasattr(self.app.wallet_core, 'is_locked'):
            print(f"Wallet Core Locked: {self.app.wallet_core.is_locked}")
        if hasattr(self.app.wallet_core, 'private_key'):
            pk_available = bool(self.app.wallet_core.private_key)
            print(f"Private Key Available: {pk_available}")
            if pk_available:
                print(f"Private Key Length: {len(self.app.wallet_core.private_key)}")
        
        # Check available methods
        methods = []
        if hasattr(self.app.wallet_core, 'send_transaction_from'):
            methods.append('send_transaction_from')
        if hasattr(self.app.wallet_core, 'send_transaction'):
            methods.append('send_transaction')
        print(f"Available Send Methods: {methods}")
        
        print("=" * 50)
    
    
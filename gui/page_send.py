import flet as ft
from utils import calculate_wallet_balances

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
            label="💰 Amount (LKC)", 
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
        # サウンド再生用のパス（PyInstaller対応）
        import sys
        import os
        if hasattr(sys, '_MEIPASS'):
            self.send_sound_path = os.path.join(sys._MEIPASS, "sounds", "send.wav")
        else:
            self.send_sound_path = os.path.join("assets", "sounds", "send.wav")
        

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
                        
                        # CRITICAL FIX: Ensure public_key is set after unlock
                        # This fixes the "Invalid cryptographic keys" error
                        print(f"DEBUG: Checking cryptographic keys after unlock...")
                        print(f"DEBUG: - private_key exists: {bool(hasattr(wallet, 'private_key') and wallet.private_key)}")
                        print(f"DEBUG: - public_key exists: {bool(hasattr(wallet, 'public_key') and wallet.public_key)}")
                        
                        if not hasattr(wallet, 'public_key') or not wallet.public_key:
                            print("DEBUG: public_key missing after unlock, attempting to retrieve/regenerate")
                            
                            # Try to get from wallet data first
                            if hasattr(wallet, 'wallets') and current_address in wallet.wallets:
                                wallet_data = wallet.wallets[current_address]
                                if 'public_key' in wallet_data and wallet_data['public_key']:
                                    wallet.public_key = wallet_data['public_key']
                                    print(f"DEBUG: Set public_key from wallet data: {wallet.public_key[:20]}...")
                                else:
                                    # If no public_key in wallet data, derive from private key
                                    print("DEBUG: No public_key in wallet data, deriving from private key")
                                    try:
                                        from lunalib.core.crypto import KeyManager
                                        key_manager = KeyManager()
                                        # Derive public key from private key
                                        derived_public_key = key_manager.derive_public_key(wallet.private_key)
                                        wallet.public_key = derived_public_key
                                        wallet_data['public_key'] = derived_public_key
                                        print(f"DEBUG: Derived public_key: {derived_public_key[:20]}...")
                                    except Exception as key_error:
                                        print(f"DEBUG: Failed to derive public key: {key_error}")
                                        import traceback
                                        traceback.print_exc()
                                        return False, f"Failed to derive public key: {key_error}"
                        
                        print(f"DEBUG: Final key check - private_key length: {len(wallet.private_key) if hasattr(wallet, 'private_key') and wallet.private_key else 0}")
                        print(f"DEBUG: Final key check - public_key length: {len(wallet.public_key) if hasattr(wallet, 'public_key') and wallet.public_key else 0}")
                    else:
                        return False, "No wallet address found or password missing"
                else:
                    return False, "Wallet unlock method not available"

            # Verify private key is available
            if not hasattr(wallet, 'private_key') or not wallet.private_key:
                return False, "No private key available for signing"
            
            # CRITICAL FIX: Remove 'priv_' prefix from private key if present
            # SM2 requires a 64-character hex string without prefix
            if wallet.private_key.startswith('priv_'):
                print(f"DEBUG: Removing 'priv_' prefix from private key")
                wallet.private_key = wallet.private_key[5:]  # Remove 'priv_' (5 characters)
                print(f"DEBUG: Private key length after cleanup: {len(wallet.private_key)}")
                
                # Update wallet data as well
                if hasattr(wallet, 'wallets') and hasattr(wallet, 'address') and wallet.address in wallet.wallets:
                    wallet.wallets[wallet.address]['private_key'] = wallet.private_key
            
            # Verify private key format (must be 64-character hex)
            if len(wallet.private_key) != 64:
                return False, f"Invalid private key format: expected 64 characters, got {len(wallet.private_key)}"
            
            try:
                int(wallet.private_key, 16)  # Verify it's valid hex
            except ValueError:
                return False, "Invalid private key: not a valid hexadecimal string"
            
            # Verify public key is also available (required for SM2 signing)
            if not hasattr(wallet, 'public_key') or not wallet.public_key:
                return False, "No public key available for cryptographic operations"

            # Refresh balances to ensure we have latest state
            wallet.refresh_balance()

            return True, "Wallet ready for sending"

        except Exception as e:
            error_msg = f"Wallet preparation error: {str(e)}"
            print(f"DEBUG: {error_msg}")
            return False, error_msg
    def get_available_balance(self):
        """Get current wallet available balance from wallet_core or transactions"""
        try:
            if not hasattr(self.app, 'wallet_core') or not self.app.wallet_core:
                return 0.0
            
            # Determine which address to use
            wallet_address = self.from_address or getattr(self.app.wallet_core, 'current_wallet_address', None)
            if not wallet_address:
                return 0.0
            
            # First try to get from wallet_core cache
            if hasattr(self.app.wallet_core, 'wallets') and isinstance(self.app.wallet_core.wallets, dict):
                wallet_data = self.app.wallet_core.wallets.get(wallet_address, {})
                confirmed_balance = wallet_data.get('confirmed_balance')
                
                if confirmed_balance is not None and confirmed_balance > 0:
                    print(f"DEBUG SendPage: Using cached balance from wallet_core - {confirmed_balance:.6f} LKC")
                    return confirmed_balance
            
            # If no cache, calculate from transactions
            print(f"DEBUG SendPage: Cache miss, calculating balance from transactions...")
            confirmed_balance = 0.0
            wallet_addr_lower = wallet_address.lower()
            
            # Get transactions from database
            if hasattr(self.app, 'database'):
                try:
                    # Try to get wallet transactions
                    if hasattr(self.app.database, 'get_wallet_transactions'):
                        all_txs = self.app.database.get_wallet_transactions(wallet_address, limit=10000)
                    elif hasattr(self.app.database, 'get_transactions'):
                        all_txs = self.app.database.get_transactions(wallet_address)
                    else:
                        all_txs = []
                    
                    # Calculate balance from transactions
                    for tx in all_txs:
                        tx_status = tx.get('status', 'confirmed').lower()
                        if tx_status != 'confirmed':
                            continue
                        
                        tx_from = tx.get('from', '').lower()
                        tx_to = tx.get('to', '').lower()
                        reward_addr = tx.get('reward_address', '').lower()
                        tx_type = tx.get('type', 'transfer').lower()
                        amount = float(tx.get('amount', 0))
                        fee = float(tx.get('fee', 0))
                        
                        # Mining reward
                        if tx_type == 'reward':
                            if (tx_to == wallet_addr_lower or reward_addr == wallet_addr_lower):
                                confirmed_balance += amount
                        # Incoming transfer
                        elif tx_to == wallet_addr_lower:
                            confirmed_balance += amount
                        # Outgoing transfer
                        elif tx_from == wallet_addr_lower:
                            confirmed_balance -= (amount + fee)
                    
                    confirmed_balance = max(0.0, confirmed_balance)
                    print(f"DEBUG SendPage: Calculated balance - {confirmed_balance:.6f} LKC from {len(all_txs)} transactions")
                    
                except Exception as db_err:
                    print(f"DEBUG SendPage: Error getting transactions: {db_err}")
            
            # Return available (confirmed) balance
            return confirmed_balance
            
        except Exception as e:
            print(f"DEBUG: Error getting available balance: {e}")
            import traceback
            traceback.print_exc()
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
                    f"Insufficient available balance. Available: {available_balance:.6f} LKC", 
                    "error"
                )
                return
            
            print(f"DEBUG: Sending {amount} LKC from {wallet.address} to {recipient}")
            
            # BYPASS lunalib's send_transaction to avoid _verify_wallet_integrity issues
            # Instead, use TransactionManager directly
            try:
                from lunalib.transactions.transactions import TransactionManager
                tx_manager = TransactionManager(network_endpoints=["https://bank.linglin.art"])
                
                # Create transaction
                print("[SEND] Creating transaction with TransactionManager...")
                transaction = tx_manager.create_transaction(
                    from_address=wallet.address,
                    to_address=recipient,
                    amount=amount,
                    private_key=wallet.private_key,
                    memo=memo,
                    transaction_type="transfer"
                )
                
                print(f"[SEND] Transaction created: {transaction.get('hash', 'no_hash')[:16]}...")
                
                # Validate transaction
                is_valid, message = tx_manager.validate_transaction(transaction)
                if not is_valid:
                    print(f"[SEND] Validation failed: {message}")
                    self.app.show_snackbar(f"Transaction validation failed: {message}", "error")
                    return
                
                print("[SEND] Transaction validated successfully")
                
                # Broadcast transaction
                success, broadcast_message = tx_manager.send_transaction(transaction)
                
                if not success:
                    print(f"[SEND] Broadcast failed: {broadcast_message}")
                    self.app.show_snackbar(f"Failed to broadcast: {broadcast_message}", "error")
                    return
                
                print(f"[SEND] Transaction broadcast successful: {broadcast_message}")
                # デバッグ: 送信直後のトランザクション履歴を表示
                try:
                    if hasattr(self.app, 'database') and hasattr(wallet, 'address'):
                        txs = self.app.database.get_wallet_transactions(wallet.address, limit=20)
                        print(f"[DEBUG] Transactions for {wallet.address} after send:")
                        for tx in txs:
                            print(tx)
                except Exception as e:
                    print(f"[DEBUG] Could not print transactions: {e}")
                
                # 残高の手動減算は不要。update_all_wallet_balancesで一元管理。
                
                # Transaction sent successfully!
                print("DEBUG: Transaction sent successfully!")
                
                # Refresh balances to get updated state
                wallet.refresh_balance()
                
                # Save wallet state
                if hasattr(self.app, 'save_wallet_data'):
                    self.app.save_wallet_data(force_save=True)
                
                # For inter-wallet transfers: refresh all wallet balances
                # This ensures the recipient wallet's balance is also updated
                print("DEBUG: Refreshing all wallet balances to account for inter-wallet transfer...")
                try:
                    from utils import update_all_wallet_balances
                    if hasattr(self.app, 'wallet_core') and hasattr(self.app.wallet_core, 'wallets'):
                        database = getattr(self.app.wallet_core, 'database', None)
                        mempool_manager = getattr(self.app.wallet_core, 'mempool_manager', None)
                        update_all_wallet_balances(self.app.wallet_core.wallets, database, mempool_manager)
                except Exception as e:
                    print(f"DEBUG: Error updating all wallet balances: {e}")
                
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
                
            except Exception as tx_error:
                print(f"[SEND] Transaction error: {tx_error}")
                import traceback
                traceback.print_exc()
                self.app.show_snackbar(f"Transaction error: {str(tx_error)}", "error")
                return
                
        except Exception as ex:
            error_msg = f"Unexpected error: {str(ex)}"
            print(f"DEBUG: Unexpected error in send_transaction: {error_msg}")
            import traceback
            traceback.print_exc()
            self.app.show_snackbar(f"Error sending transaction: {str(ex)}", "error")
            
    def create(self):
        balance = self.get_available_balance()
        
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
                
                # Centered form container - scrollable to fit content
                ft.Container(
                    content=ft.Column([
                        ft.Text(
                            "💡 Instructions:\n"
                            "1. Enter the recipient's wallet address\n"
                            "2. Specify the amount to send\n"
                            "3. Add an optional memo\n"
                            "4. Enter your password to confirm\n"
                            "5. Click Send Transaction",
                            size=12, 
                            color="#f8d7da",
                            weight="normal"
                        ),
                        ft.Container(height=20),
                        ft.Text(
                            f"💰 Available: {balance:.6f} LKC", 
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
                    spacing=0,
                    scroll=ft.ScrollMode.AUTO
                    ),
                    padding=20,
                    margin=0,
                    bgcolor="#1a0f0f",
                    border_radius=15,
                    alignment=ft.Alignment(0, 0),
                    expand=True
                )
            ]),
            expand=True,
            padding=0,
            bgcolor="#2c1a1a",
            alignment=ft.Alignment(0, 0)
        )
    
    def get_current_balance(self):
        """Get current wallet total balance using unified calculation system"""
        try:
            if not hasattr(self.app, 'wallet_core') or not self.app.wallet_core:
                return 0.0
            
            # Determine which address to use
            wallet_address = self.from_address or getattr(self.app.wallet_core, 'current_wallet_address', None)
            if not wallet_address:
                return 0.0
            
            # Use unified balance calculation system
            try:
                from lunalib.core.mempool import MempoolManager
                mempool_manager = MempoolManager()
            except:
                mempool_manager = None
            
            database = self.app.database if hasattr(self.app, 'database') else None
            
            # Calculate using unified system
            balances = calculate_wallet_balances(
                wallet_address,
                database=database,
                mempool_manager=mempool_manager
            )
            
            # Return total balance (available + pending)
            return balances['total']
            
        except Exception as e:
            print(f"DEBUG: Error getting total balance: {e}")
            return 0.0
    
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
    
    
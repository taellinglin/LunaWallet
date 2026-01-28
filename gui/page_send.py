import flet as ft
from utils import calculate_wallet_balances, format_amount, format_amount_with_unit
import threading

class SendPage:
    def __init__(self, app, on_back, on_send_complete, from_address=None):
        self.app = app
        self.on_back = on_back
        self.on_send_complete = on_send_complete
        self.from_address = from_address
        
        # Form fields
        field_width = 420 if not app.is_mobile else 320
        self.recipient = ft.TextField(
            label="Recipient Address",
            hint_text="Enter Luna address",
            width=field_width,
            bgcolor="#1a0f0f",
            border_color="#5c2e2e",
            focused_border_color="#dc3545",
            color="#f8d7da",
            label_style=ft.TextStyle(color="#f8d7da"),
            text_style=ft.TextStyle(color="#f8d7da"),
            prefix_icon=ft.Icons.PERSON,
            on_submit=self._send_transaction_thread,
        )
        self.amount = ft.TextField(
            label="Amount (LKC)",
            hint_text="0.00",
            width=field_width,
            bgcolor="#1a0f0f",
            border_color="#5c2e2e",
            focused_border_color="#dc3545",
            color="#f8d7da",
            label_style=ft.TextStyle(color="#f8d7da"),
            text_style=ft.TextStyle(color="#f8d7da"),
            prefix_icon=ft.Icons.ATTACH_MONEY,
            on_submit=self._send_transaction_thread,
        )
        self.memo = ft.TextField(
            label="Memo (Optional)",
            hint_text="Add a note",
            width=field_width,
            bgcolor="#1a0f0f",
            border_color="#5c2e2e",
            focused_border_color="#dc3545",
            color="#f8d7da",
            label_style=ft.TextStyle(color="#f8d7da"),
            text_style=ft.TextStyle(color="#f8d7da"),
            prefix_icon=ft.Icons.NOTE_ALT,
        )
        self.password = ft.TextField(
            label="Password",
            password=True,
            can_reveal_password=True,
            hint_text="Enter your password",
            width=field_width,
            bgcolor="#1a0f0f",
            border_color="#5c2e2e",
            focused_border_color="#dc3545",
            color="#f8d7da",
            label_style=ft.TextStyle(color="#f8d7da"),
            text_style=ft.TextStyle(color="#f8d7da"),
            prefix_icon=ft.Icons.LOCK,
            on_submit=self._send_transaction_thread,
        )
        # サウンド再生用のパス（PyInstaller対応）
        import sys
        import os
        if hasattr(sys, '_MEIPASS'):
            self.send_sound_path = os.path.join(sys._MEIPASS, "sounds", "send.wav")
        else:
            self.send_sound_path = os.path.join("assets", "sounds", "send.wav")
        self.loading_ring = ft.ProgressRing(visible=False, width=20, height=20)
        self.send_button = ft.ElevatedButton(
            "Send",
            on_click=self._send_transaction_thread,
            style=ft.ButtonStyle(
                color="#ffffff",
                bgcolor="#dc3545",
                padding=ft.padding.symmetric(horizontal=18, vertical=12),
                shape=ft.RoundedRectangleBorder(radius=8)
            ),
            width=160
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

    def _should_try_direct_broadcast(self, message) -> bool:
        text = str(message or "")
        lowered = text.lower()
        return (
            "Failed to decode JSON object" in text
            or "invalid start byte" in text
            or "utf-8" in text
            or "ssl" in lowered
            or "certificate" in lowered
            or "tls" in lowered
            or "handshake" in lowered
            or "connection" in lowered
        )

    def _broadcast_transaction_direct(self, transaction: dict, mempool_url: str):
        try:
            import os
            import requests
            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Accept-Encoding": "identity",
            }
            verify = os.environ.get("SSL_CERT_FILE") or os.environ.get("REQUESTS_CA_BUNDLE")
            if verify and not os.path.exists(verify):
                verify = None
            try:
                if not verify:
                    import certifi
                    verify = certifi.where()
            except Exception:
                verify = None

            response = requests.post(
                mempool_url,
                json=transaction,
                headers=headers,
                timeout=30,
                verify=verify if verify else True,
            )
            status = response.status_code
            try:
                payload = response.json()
            except Exception:
                payload = {"raw": response.text}

            if status >= 400:
                return False, f"HTTP {status}: {payload}"

            if isinstance(payload, dict):
                if payload.get("success") is True:
                    return True, payload.get("message") or "Broadcasted"
                if payload.get("success") is False:
                    return False, payload.get("error") or str(payload)

            return True, str(payload)
        except Exception as e:
            return False, f"Direct broadcast error: {e}"
    def get_available_balance(self):
        """Get current wallet available balance from transactions (bypassing LunaLib WalletManager)"""
        try:
            if not hasattr(self.app, 'wallet_core') or not self.app.wallet_core:
                return 0.0
            wallet_address = self.from_address or getattr(self.app.wallet_core, 'current_wallet_address', None)
            if not wallet_address:
                return 0.0

            # Prefer cached confirmed balance if available
            try:
                wallets = getattr(self.app.wallet_core, 'wallets', None)
                if isinstance(wallets, dict) and wallet_address in wallets:
                    cached_confirmed = wallets[wallet_address].get('confirmed_balance', None)
                    if isinstance(cached_confirmed, (int, float)):
                        return float(cached_confirmed)
            except Exception:
                pass
            
            # Calculate balance from transactions directly (avoid LunaLib WalletManager issues)
            confirmed_balance = 0.0
            wallet_addr_lower = wallet_address.lower()
            min_confirmations = 6
            latest_height = None
            try:
                if hasattr(self.app, 'blockchain_manager') and self.app.blockchain_manager:
                    if hasattr(self.app.blockchain_manager, 'get_latest_block'):
                        block = self.app.blockchain_manager.get_latest_block()
                        if block and isinstance(block, dict):
                            latest_height = int(block.get('index', 0) or 0)
                    if latest_height is None and hasattr(self.app.blockchain_manager, 'get_blockchain_height'):
                        latest_height = int(self.app.blockchain_manager.get_blockchain_height() or 0)
            except Exception:
                latest_height = None
            
            # Get transactions from storage (preferred)
            all_txs = []
            if hasattr(self.app, 'get_wallet_transactions'):
                try:
                    all_txs = self.app.get_wallet_transactions(wallet_address)
                except Exception as storage_err:
                    print(f"DEBUG SendPage: Error getting transactions from storage: {storage_err}")

            # Fallback to database
            if not all_txs and hasattr(self.app, 'database'):
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
                        block_height = tx.get('block_height', None)
                        confirmations = None
                        if block_height is not None and latest_height is not None:
                            try:
                                confirmations = max(0, int(latest_height) - int(block_height) + 1)
                            except Exception:
                                confirmations = None
                        if tx_status != 'confirmed' or (confirmations is not None and confirmations < min_confirmations):
                            continue
                        
                        # Handle both field name formats
                        tx_from = tx.get('from', tx.get('from_address', '')).lower()
                        tx_to = tx.get('to', tx.get('to_address', '')).lower()
                        reward_addr = tx.get('reward_address', '').lower()
                        recipient_addr = tx.get('recipient', '').lower()
                        tx_type = tx.get('type', tx.get('tx_type', 'transfer')).lower()
                        amount = float(tx.get('amount', 0))
                        fee = float(tx.get('fee', 0))
                        
                        # Mining reward
                        if tx_type == 'reward':
                            if (tx_to == wallet_addr_lower or reward_addr == wallet_addr_lower):
                                confirmed_balance += amount
                        # Fee distribution (additional reward type)
                        elif tx_type == 'fee_distribution':
                            if (tx_to == wallet_addr_lower or reward_addr == wallet_addr_lower or recipient_addr == wallet_addr_lower):
                                confirmed_balance += amount
                        # Incoming transfer
                        elif tx_to == wallet_addr_lower:
                            confirmed_balance += amount
                        # Outgoing transfer
                        elif tx_from == wallet_addr_lower:
                            confirmed_balance -= (amount + fee)
                    
                    confirmed_balance = max(0.0, confirmed_balance)
                    print(f"DEBUG SendPage: Calculated balance - {format_amount_with_unit(confirmed_balance)} from {len(all_txs)} transactions")
                    
                except Exception as db_err:
                    print(f"DEBUG SendPage: Error getting transactions: {db_err}")
            
            # Return available (confirmed) balance
            return confirmed_balance
            
        except Exception as e:
            print(f"DEBUG: Error calculating available balance: {e}")
            import traceback
            traceback.print_exc()
            return 0.0
    def _debug_wallet_state(self):
        """Debug wallet state before sending"""
        print("=" * 50)
        print("DEBUG: Wallet State Check")
        print("=" * 50)
        
        if not hasattr(self.app, 'wallet_core') or not self.app.wallet_core:
            print("Error: No wallet_core found")
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
                    f"Insufficient available balance. Available: {format_amount_with_unit(available_balance)}", 
                    "error"
                )
                return
            
            # Lunaアドレスのバリデーション
            from utils import validate_luna_address
            is_valid, reason = validate_luna_address(recipient)
            if not is_valid:
                from app.core import _global_trace
                _global_trace(f"RECIPIENT VALIDATION - {reason}: {recipient}", "SEND_ERROR")
                self.app.show_snackbar(f"Invalid recipient address: {reason}", "error")
                return
            
            print(f"DEBUG: Sending {amount} LKC from {wallet.address} to {recipient}")
            
            # Log current wallet state before sending
            from app.core import _global_trace
            try:
                # Try to get UTXO info if available
                if hasattr(wallet, 'get_balance'):
                    balances = wallet.get_balance()
                    _global_trace(f"WALLET STATE - Confirmed: {balances.get('confirmed', 0)}, Pending: {balances.get('pending', 0)}", "SEND")
                if hasattr(wallet, 'get_utxos'):
                    utxos = wallet.get_utxos()
                    _global_trace(f"WALLET UTXOS - Count: {len(utxos) if utxos else 0}", "SEND")
            except Exception as state_err:
                _global_trace(f"WALLET STATE ERROR - {str(state_err)}", "SEND")
            
            # BYPASS lunalib's send_transaction to avoid _verify_wallet_integrity issues
            # Instead, use TransactionManager directly
            try:
                from lunalib.transactions.transactions import TransactionManager
                
                # Log network endpoint information
                from app.core import _global_trace
                # Use the base URL only - TransactionManager will append the path
                network_endpoints = ["https://bank.linglin.art"]
                mempool_url = "https://bank.linglin.art/mempool/add"
                _global_trace(f"NETWORK - Using base endpoint: {network_endpoints[0]}, Mempool: {mempool_url}, Environment: {'BUILD' if hasattr(self.app, 'is_build_version') else 'DEV'}", "SEND")
                
                tx_manager = TransactionManager(network_endpoints=network_endpoints)
                
                # Create transaction
                print("[SEND] Creating transaction...")
                
                # Log detailed transaction parameters
                _global_trace(f"SEND DETAILS - From: {wallet.address}, To: {recipient}, Amount: {amount}, Memo: {memo}", "SEND")
                
                transaction = tx_manager.create_transaction(
                    from_address=wallet.address,
                    to_address=recipient,
                    amount=amount,
                    private_key=wallet.private_key,
                    memo=memo,
                    transaction_type="transfer"
                )
                
                print(f"[SEND] Transaction created")
                # Log transaction hash and type
                tx_hash = transaction.get('hash', 'unknown')
                tx_fee = transaction.get('fee', 0)
                tx_type = transaction.get('type', 'transfer')
                
                # Log complete transaction structure for debugging
                import json as json_module
                try:
                    tx_json = json_module.dumps(transaction, default=str, indent=2)
                    _global_trace(f"TX OBJECT: {tx_json[:200]}...", "SEND")  # Log first 200 chars
                except Exception as json_err:
                    _global_trace(f"TX OBJECT: {str(transaction)[:200]}...", "SEND")
                
                _global_trace(f"TX Hash: {tx_hash}, Type: {tx_type}, Fee: {tx_fee}", "SEND")
                
                # Validate transaction
                is_valid, message = tx_manager.validate_transaction(transaction)
                if not is_valid:
                    print(f"[SEND] Validation failed: {message}")
                    _global_trace(f"VALIDATION ERROR - {message} - TX: {tx_hash}", "SEND_ERROR")
                    _global_trace(f"VALIDATION ERROR DETAILS - Recipient: {recipient}, From: {wallet.address}, Amount: {amount}", "SEND_ERROR")
                    self.app.show_snackbar(f"Transaction validation failed: {message}", "error")
                    return
                
                print("[SEND] Transaction validated")
                _global_trace(f"VALIDATION OK - TX: {tx_hash}, Recipient: {recipient}", "SEND")
                
                # Broadcast transaction via lunalib only
                print("[SEND] Broadcasting transaction...")
                try:
                    # Log transaction inputs for mempool debugging
                    _global_trace(f"PRE-BROADCAST - Wallet Balance Available: {available_balance}, TX Amount + Fee: {amount + tx_fee}", "SEND")
                    
                    # Try using TransactionManager's send_transaction
                    _global_trace(f"BROADCAST - Attempting via TransactionManager", "SEND")
                    success, broadcast_message = tx_manager.send_transaction(transaction)
                    print(f"[SEND] TransactionManager result: success={success}, message={broadcast_message}")

                    if not success and self._should_try_direct_broadcast(broadcast_message):
                        _global_trace("BROADCAST - Decode error detected, trying direct POST", "SEND")
                        success, direct_message = self._broadcast_transaction_direct(transaction, mempool_url)
                        broadcast_message = direct_message
                        print(f"[SEND] Direct broadcast result: success={success}, message={broadcast_message}")
                    
                    print(f"[SEND] Final broadcast result: success={success}, message={broadcast_message}")
                    
                    if not success:
                        _global_trace(f"BROADCAST FAILED - Error: {broadcast_message}", "SEND_ERROR")
                        _global_trace(f"BROADCAST FAILED DETAILS - TX Hash: {tx_hash}, Recipient: {recipient}, Amount: {amount}, Fee: {tx_fee}", "SEND_ERROR")
                        self.app.show_snackbar(f"Failed to broadcast: {broadcast_message}", "error")
                        return
                    else:
                        _global_trace(f"BROADCAST SUCCESS - TX: {tx_hash}, Message: {broadcast_message}", "SEND")
                    
                except Exception as broadcast_err:
                    print(f"[SEND] Broadcast exception: {broadcast_err}")
                    import traceback
                    tb_str = traceback.format_exc()
                    _global_trace(f"BROADCAST EXCEPTION - {str(broadcast_err)}", "SEND_ERROR")
                    _global_trace(f"BROADCAST TRACEBACK - {tb_str[:500]}", "SEND_ERROR")
                    traceback.print_exc()

                    # Try direct broadcast on transport/SSL errors
                    if self._should_try_direct_broadcast(str(broadcast_err)):
                        _global_trace("BROADCAST - Exception detected, trying direct POST", "SEND")
                        success, direct_message = self._broadcast_transaction_direct(transaction, mempool_url)
                        if success:
                            _global_trace(f"BROADCAST SUCCESS - TX: {tx_hash}, Message: {direct_message}", "SEND")
                            broadcast_message = direct_message
                        else:
                            self.app.show_snackbar(f"Broadcast error: {str(broadcast_err)}", "error")
                            return
                    else:
                        self.app.show_snackbar(f"Broadcast error: {str(broadcast_err)}", "error")
                        return
                
                print(f"[SEND] Broadcast successful")
                _global_trace(f"BROADCAST SUCCESS - TX: {tx_hash}, Message: {broadcast_message}", "SEND")

                # Save pending transaction to local storage so outgoing shows immediately
                try:
                    tx_record = dict(transaction)
                    tx_record.setdefault('status', 'pending')
                    tx_record.setdefault('timestamp', time.time())
                    tx_record.setdefault('hash', tx_hash)
                    tx_record.setdefault('from', wallet.address)
                    tx_record.setdefault('to', recipient)
                    tx_record.setdefault('amount', amount)
                    tx_record.setdefault('fee', tx_fee)

                    if hasattr(self.app, '_store_transaction'):
                        self.app._store_transaction(wallet.address, tx_record, status='pending')

                        # If recipient is one of our wallets, save there too
                        if hasattr(self.app.wallet_core, 'wallets') and isinstance(self.app.wallet_core.wallets, dict):
                            for addr in self.app.wallet_core.wallets.keys():
                                if addr.lower() == recipient.lower():
                                    self.app._store_transaction(addr, tx_record, status='pending')
                                    break

                    # Legacy database path (if present)
                    if hasattr(self.app, 'database') and self.app.database:
                        sender_record = dict(tx_record)
                        sender_record['hash'] = f"{tx_hash}_{wallet.address}" if tx_hash else wallet.address
                        self.app.database.save_transaction(sender_record, wallet.address)

                        if hasattr(self.app.wallet_core, 'wallets') and isinstance(self.app.wallet_core.wallets, dict):
                            for addr in self.app.wallet_core.wallets.keys():
                                if addr.lower() == recipient.lower():
                                    receiver_record = dict(tx_record)
                                    receiver_record['hash'] = f"{tx_hash}_{addr}" if tx_hash else addr
                                    self.app.database.save_transaction(receiver_record, addr)
                                    break
                except Exception as save_err:
                    print(f"DEBUG: Failed to save pending transaction: {save_err}")
                
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
                if hasattr(self.app, '_play_sound'):
                    self.app._play_sound("send")
                
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
                    ft.Column([
                        ft.Text("Send", size=22, weight="bold", color="#f8d7da"),
                        ft.Text("Transfer funds to another address", size=12, color="#a8a8a8"),
                    ], spacing=2),
                    ft.Container(expand=True)
                ]),
                ft.Divider(color="#5c2e2e"),
                
                # Centered form container - scrollable to fit content
                ft.Container(
                    content=ft.Column([
                        ft.Text(f"Available: {format_amount_with_unit(balance)}", size=12, color="#f0c2c2"),
                        ft.Text("Minimum confirmations: 6", size=10, color="#8d6e6e"),
                        ft.Container(height=12),
                        self.recipient,
                        ft.Container(height=10),
                        self.amount,
                        ft.Container(height=10),
                        self.memo,
                        ft.Container(height=10),
                        self.password,
                        ft.Container(height=16),
                        ft.Row(
                            [
                                self.send_button,
                                self.loading_ring,
                            ],
                            alignment=ft.MainAxisAlignment.CENTER,
                        )
                    ], 
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=0,
                    scroll=ft.ScrollMode.AUTO
                    ),
                    padding=20,
                    margin=ft.margin.symmetric(vertical=6),
                    bgcolor="#1a0f0f",
                    border_radius=12,
                    border=ft.border.all(1, "#5c2e2e"),
                    alignment=ft.Alignment(0, 0),
                    expand=True
                )
            ]),
            expand=True,
            padding=10,
            bgcolor="#2c1a1a",
            alignment=ft.Alignment(0, 0)
        )

    def _set_sending_state(self, is_sending: bool):
        self.loading_ring.visible = is_sending
        self.send_button.disabled = is_sending
        self.recipient.disabled = is_sending
        self.amount.disabled = is_sending
        self.memo.disabled = is_sending
        self.password.disabled = is_sending
        if hasattr(self.app, 'page') and self.app.page:
            self.app.page.update()

    def _send_transaction_thread(self, e):
        """Run send in a background thread and show loading indicator."""
        recipient = self.recipient.value.strip()
        from utils import validate_luna_address
        is_valid, reason = validate_luna_address(recipient)
        if not is_valid:
            self.app.show_snackbar(f"Invalid recipient address: {reason}", "error")
            return

        self._set_sending_state(True)

        def _run():
            try:
                self.send_transaction(e)
            finally:
                self._set_sending_state(False)

        threading.Thread(target=_run, daemon=True).start()
    
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
    
    
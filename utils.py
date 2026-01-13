import base64
import io
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from PIL import Image
import requests
import socket

# Import from lunalib
from lunalib.transactions.transactions import TransactionManager
from lunalib.transactions.security import TransactionSecurity
from lunalib.core.crypto import KeyManager
from lunalib.storage.encryption import EncryptionManager
from lunalib.core.wallet import LunaWallet
from lunalib.core.p2p import HybridBlockchainClient
from lunalib.core.blockchain import BlockchainManager
from lunalib.core.mempool import MempoolManager

# Initialize managers with corrected configurations
try:
    blockchain = BlockchainManager(endpoint_url="https://bank.linglin.art/api/blockchain/full")
    print("DEBUG: BlockchainManager initialized with endpoint: https://bank.linglin.art/api/blockchain/full")
    mempool = MempoolManager(["https://bank.linglin.art"])
    client = HybridBlockchainClient(
        "https://bank.linglin.art",
        blockchain,
        mempool
    )
    client.start()
except Exception as e:
    print(f"ERROR: Failed to initialize blockchain client: {e}")
    blockchain = None
    mempool = None

# ============================================================================
# UNIFIED BALANCE CALCULATION SYSTEM
# ============================================================================

# Refactor calculate_wallet_balances to use enhanced client methods
def calculate_wallet_balances(wallet_address: str) -> Dict[str, float]:
    """
    Calculate both available (confirmed blockchain) and pending (mempool) balances for a wallet.
    
    Args:
        wallet_address: The wallet address to calculate balances for
        
    Returns:
        Dict with keys: 'available', 'pending', 'total'
    """
    print(f"DEBUG: calculate_wallet_balances called for {wallet_address[:8]}")

    # Get confirmed balance from blockchain transactions
    confirmed_balance = _calculate_confirmed_balance(wallet_address, client.database if hasattr(client, 'database') else None)
    
    # Get pending balance from mempool
    pending_balance = _calculate_pending_balance(wallet_address)

    total_balance = confirmed_balance + pending_balance

    return {
        'available': confirmed_balance,
        'pending': pending_balance,
        'total': total_balance,
        'confirmed': confirmed_balance  # Alias for clarity
    }


def _calculate_confirmed_balance(wallet_address: str, database) -> float:
    """
    Calculate confirmed balance from blockchain transactions stored in database.
    Ensures ALL reward transactions are counted, regardless of storage format.
    Supports multiple wallets each with incoming/outgoing/pending/confirmed/transfers/rewards.
    
    Args:
        wallet_address: Wallet address (original case, not lowercased)
        database: The database instance
        
    Returns:
        Confirmed balance amount
    """
    confirmed_balance = 0.0
    reward_transactions_count = 0
    transfer_in_count = 0
    transfer_out_count = 0
    fee_dist_count = 0
    
    wallet_address_lower = wallet_address.lower()
    
    try:
        # Check if database is None
        if database is None:
            print(f"WARNING: database is None, cannot calculate balance")
            return 0.0
        
        # Get wallet transactions from database - use get_wallet_transactions() which takes wallet address
        try:
            # Note: get_wallet_transactions returns transactions for a specific wallet
            # Use the original address case as database expects it
            wallet_txs = database.get_wallet_transactions(wallet_address, limit=1000)  # Get up to 1000 transactions
        except AttributeError as e:
            print(f"WARNING: database.get_wallet_transactions() not available: {e}")
            return 0.0
        
        if not wallet_txs:
            print(f"DEBUG BALANCE: No transactions in database for {wallet_address[:12]}")
            return 0.0
        
        print(f"DEBUG BALANCE: Database has {len(wallet_txs)} transactions for {wallet_address[:12]}")
        print(f"DEBUG BALANCE: Looking for wallet (lowercased): {wallet_address_lower}")
        
        # Process each confirmed transaction
        for tx in wallet_txs:
            tx_from = tx.get('from', '').lower()
            tx_to = tx.get('to', '').lower()
            tx_type = tx.get('type', 'transfer').lower()
            tx_amount = float(tx.get('amount', 0))
            tx_fee = float(tx.get('fee', 0))
            tx_status = tx.get('status', 'confirmed').lower()
            reward_addr = tx.get('reward_address', '').lower()
            recipient_addr = tx.get('recipient', '').lower()
            
            print(f"  TX: type={tx_type}, from={tx_from[:12] if tx_from else 'none'}, to={tx_to[:12] if tx_to else 'none'}, amount={tx_amount}, status={tx_status}")
            
            # Only count confirmed (blockchain) transactions
            if tx_status == 'confirmed':
                # Handle mining rewards (multiple storage formats)
                if tx_type == 'reward':
                    # Incoming reward - check all possible ways wallet address is referenced
                    if (reward_addr == wallet_address_lower or 
                        (tx_from == 'network' and tx_to == wallet_address_lower) or
                        (tx_to == wallet_address_lower and tx_from in ['network', '']) or
                        (tx_from == '' and tx_to == wallet_address_lower)):
                        print(f"    -> COUNTED as reward received: +{tx_amount}")
                        confirmed_balance += tx_amount
                        reward_transactions_count += 1
                    # Outgoing reward (sent from this wallet - rare but possible)
                    elif tx_from == wallet_address_lower:
                        print(f"    -> COUNTED as reward sent: -{tx_amount} (fee: -{tx_fee})")
                        confirmed_balance -= tx_amount
                        confirmed_balance -= tx_fee
                        reward_transactions_count += 1
                    else:
                        print(f"    -> NOT counted reward (no match)")
                
                # Handle fee distributions (mining rewards variant)
                elif tx_type == 'fee_distribution':
                    # Incoming fee distribution
                    if (recipient_addr == wallet_address_lower or 
                        reward_addr == wallet_address_lower or
                        tx_to == wallet_address_lower):
                        print(f"    -> COUNTED as fee distribution received: +{tx_amount}")
                        confirmed_balance += tx_amount
                        fee_dist_count += 1
                    # Outgoing fee distribution
                    elif tx_from == wallet_address_lower:
                        print(f"    -> COUNTED as fee distribution sent: -{tx_amount} (fee: -{tx_fee})")
                        confirmed_balance -= tx_amount
                        confirmed_balance -= tx_fee
                        fee_dist_count += 1
                
                # Handle regular transfers, stakes, delegations, etc.
                elif tx_type in ['transfer', 'stake', 'delegate', 'gtx_genesis', 'send', 'receive']:
                    # Incoming transaction
                    if tx_to == wallet_address_lower:
                        print(f"    -> COUNTED as incoming transfer: +{tx_amount}")
                        confirmed_balance += tx_amount
                        transfer_in_count += 1
                    # Outgoing transaction
                    elif tx_from == wallet_address_lower:
                        print(f"    -> COUNTED as outgoing transfer: -{tx_amount} (fee: -{tx_fee})")
                        confirmed_balance -= tx_amount
                        confirmed_balance -= tx_fee
                        transfer_out_count += 1
                    else:
                        print(f"    -> NOT COUNTED (tx_to={tx_to[:12]}, tx_from={tx_from[:12]}, wallet={wallet_address_lower})")
                else:
                    # Other transaction types
                    if tx_to == wallet_address_lower:
                        print(f"    -> COUNTED as {tx_type} received: +{tx_amount}")
                        confirmed_balance += tx_amount
                    elif tx_from == wallet_address_lower:
                        print(f"    -> COUNTED as {tx_type} sent: -{tx_amount} (fee: -{tx_fee})")
                        confirmed_balance -= tx_amount
                        confirmed_balance -= tx_fee
                    else:
                        print(f"    -> NOT COUNTED ({tx_type}, no match)")
            else:
                print(f"    -> NOT COUNTED (status={tx_status}, not confirmed)")
    
    except Exception as e:
        print(f"ERROR: Failed to calculate confirmed balance: {e}")
        import traceback
        traceback.print_exc()
        return 0.0
    
    print(f"DEBUG BALANCE: Final confirmed balance for {wallet_address_lower[:8]}: {confirmed_balance:.6f}")
    print(f"DEBUG BALANCE: Transaction count breakdown:")
    print(f"  - Reward transactions: {reward_transactions_count}")
    print(f"  - Fee distributions: {fee_dist_count}")
    print(f"  - Transfers received: {transfer_in_count}")
    print(f"  - Transfers sent: {transfer_out_count}")
    print(f"  - Total transactions processed: {transfer_in_count + transfer_out_count + reward_transactions_count + fee_dist_count}")
    return max(0.0, confirmed_balance)


def _calculate_pending_balance(wallet_address: str) -> float:
    """
    Calculate pending balance from mempool transactions.
    
    Args:
        wallet_address: Wallet address
        
    Returns:
        Pending balance amount (can be negative for net outgoing transactions)
    """
    try:
        # Try to get pending transactions for this address
        if mempool is not None and hasattr(mempool, 'get_pending_transactions_for_addresses'):
            # Use the batch method
            pending_txs = mempool.get_pending_transactions_for_addresses([wallet_address])
            if isinstance(pending_txs, dict):
                pending_txs = pending_txs.get(wallet_address, [])
        elif mempool is not None and hasattr(mempool, 'get_pending_transactions'):
            # Fallback to single method
            pending_txs = mempool.get_pending_transactions(wallet_address)
        else:
            pending_txs = []
        
        # Calculate net pending balance from transactions
        pending_balance = 0.0
        wallet_address_lower = wallet_address.lower()
        
        for tx in pending_txs:
            tx_from = tx.get('from', '').lower()
            tx_to = tx.get('to', '').lower()
            tx_amount = float(tx.get('amount', 0))
            tx_fee = float(tx.get('fee', 0))
            
            if tx_from == wallet_address_lower:
                # Outgoing transaction
                pending_balance -= (tx_amount + tx_fee)
            elif tx_to == wallet_address_lower:
                # Incoming transaction
                pending_balance += tx_amount
        
        return pending_balance
    except Exception as e:
        print(f"DEBUG: Error calculating pending balance: {e}")
        return 0.0


def update_all_wallet_balances(wallets: Dict, database=None, mempool_manager=None) -> Dict:
    """
    Update balances for all wallets, accounting for inter-wallet transfers.
    This function recalculates balances for ALL wallets to ensure that when
    one wallet sends funds to another, both balances are properly updated.
    
    Args:
        wallets: Dictionary of wallet data keyed by address
        database: The database instance (optional)
        mempool_manager: The mempool manager (optional)
        
    Returns:
        Updated wallets dictionary with balance fields
    """
    print(f"\n=== UPDATE ALL WALLET BALANCES ===")
    print(f"Updating {len(wallets)} wallets...")
    
    # Calculate and update balance for each wallet
    for wallet_addr, wallet_data in wallets.items():
        balances = calculate_wallet_balances(wallet_addr)
        
        # Update wallet data with calculated balances
        wallet_data['balance'] = balances['total']
        wallet_data['confirmed_balance'] = balances['available']
        wallet_data['available_balance'] = balances['available']
        wallet_data['pending_balance'] = balances['pending']
        
        print(f"  {wallet_addr[:12]}: Confirmed: {balances['available']:.6f}, Pending: {balances['pending']:.6f}, Total: {balances['total']:.6f}")
    
    print(f"=== ALL WALLETS UPDATED ===\n")
    return wallets


def format_balance_display(available: float, pending: float = None, decimals: int = 6) -> Tuple[str, str]:
    """
    Format balances for UI display.
    
    Args:
        available: Available (confirmed) balance
        pending: Pending balance (optional)
        decimals: Number of decimal places
        
    Returns:
        Tuple of (available_text, pending_text)
    """
    available_text = f"{available:.{decimals}f} LKC"
    
    if pending is not None:
        pending_text = f"{pending:.{decimals}f} LKC"
    else:
        pending_text = "0.000000 LKC"
    
    return (available_text, pending_text)


def get_balance_summary(available: float, pending: float) -> str:
    """
    Get a summary string of available and pending balances.
    
    Args:
        available: Available balance
        pending: Pending balance
        
    Returns:
        Summary string
    """
    total = available + pending
    return f"Available: {available:.6f} LKC | Pending: {pending:.6f} LKC | Total: {total:.6f} LKC"

def generate_qr_code(data: str, size: int = 200) -> str:
    """Generate QR code as base64 string using lunalib wallet"""
    try:
        # Create temporary wallet instance to use its QR generation
        wallet = LunaWallet()
        return wallet.generate_qr_code(data, size)
    except:
        return None

def format_address(address: str, prefix_length: int = 8, suffix_length: int = 6) -> str:
    """Format address for display with ellipsis"""
    if len(address) <= prefix_length + suffix_length:
        return address
    return f"{address[:prefix_length]}...{address[-suffix_length:]}"

def format_balance(balance: float, decimals: int = 6) -> str:
    """Format balance with specified decimal places"""
    return f"{balance:.{decimals}f}"

def format_timestamp(timestamp: float, format_str: str = "%Y-%m-%d %H:%M") -> str:
    """Format timestamp to readable string"""
    if timestamp == 0:
        return "Unknown"
    return datetime.fromtimestamp(timestamp).strftime(format_str)

def validate_password(password: str) -> tuple[bool, str]:
    """Validate password strength using lunalib encryption"""
    encryption = EncryptionManager()
    return encryption.validate_password_strength(password)

def validate_private_key(private_key: str) -> tuple[bool, str]:
    """Validate private key format using lunalib crypto"""
    key_manager = KeyManager()
    return key_manager.validate_private_key(private_key)

def calculate_fee(amount: float, fee_rate: float = 0.001) -> float:
    """Calculate transaction fee using lunalib transactions"""
    tx_manager = TransactionManager()
    return tx_manager.calculate_fee(amount, fee_rate)

def is_valid_address(address: str) -> bool:
    """Validate wallet address format using lunalib wallet"""
    wallet = LunaWallet()
    return wallet.validate_address_format(address)

def get_transaction_color(transaction: Dict, our_addresses: List[str]) -> str:
    """Get color for transaction based on type and direction"""
    tx_type = transaction.get('type', 'transfer')
    
    if tx_type == 'reward':
        return "#00ff00"  # Green for rewards
    
    to_addr = transaction.get('to', '')
    if to_addr and to_addr.lower() in [addr.lower() for addr in our_addresses]:
        return "#00ff00"  # Green for incoming
    else:
        return "#ff4444"  # Red for outgoing

def get_transaction_icon(transaction: Dict, our_addresses: List[str]) -> str:
    """Get icon for transaction based on type and direction"""
    tx_type = transaction.get('type', 'transfer')
    
    if tx_type == 'reward':
        return "💰"
    
    to_addr = transaction.get('to', '')
    if to_addr and to_addr.lower() in [addr.lower() for addr in our_addresses]:
        return "📥"
    else:
        return "📤"


def diagnose_wallet_rewards_balance(wallet_address: str, database=None):
    """
    Diagnostic function to identify why a rewards wallet balance might be capped.
    Provides detailed breakdown of all reward transactions.
    
    Args:
        wallet_address: The wallet address to diagnose
        database: The database instance
    """
    wallet_addr_lower = wallet_address.lower()
    print(f"\n{'='*70}")
    print(f"REWARDS WALLET DIAGNOSTIC for {wallet_address}")
    print(f"{'='*70}\n")
    
    if not database:
        print("ERROR: No database provided for diagnosis")
        return
    
    try:
        all_txs = database.get_all_transactions()
        print(f"Total transactions in database: {len(all_txs)}\n")
        
        # Find all transactions involving this wallet
        relevant_txs = [tx for tx in all_txs if
                       (tx.get('from', '').lower() == wallet_addr_lower or 
                        tx.get('to', '').lower() == wallet_addr_lower or
                        tx.get('reward_address', '').lower() == wallet_addr_lower)]
        
        print(f"Total transactions for this wallet: {len(relevant_txs)}\n")
        
        # Separate reward vs non-reward transactions
        reward_txs = [tx for tx in relevant_txs if tx.get('type', '').lower() == 'reward']
        other_txs = [tx for tx in relevant_txs if tx.get('type', '').lower() != 'reward']
        
        print(f"REWARD TRANSACTIONS: {len(reward_txs)}")
        print(f"OTHER TRANSACTIONS: {len(other_txs)}\n")
        
        # Analyze reward transactions
        total_rewards = 0.0
        if reward_txs:
            print("REWARD TRANSACTION DETAILS:")
            print("-" * 70)
            for i, tx in enumerate(reward_txs, 1):
                amount = float(tx.get('amount', 0))
                total_rewards += amount
                block_height = tx.get('block_height', 'N/A')
                status = tx.get('status', 'unknown')
                tx_from = tx.get('from', 'unknown')
                tx_to = tx.get('to', 'unknown')
                reward_addr = tx.get('reward_address', 'N/A')
                
                print(f"\n  [{i}] REWARD TRANSACTION")
                print(f"      Amount: {amount:.6f} LKC")
                print(f"      Block Height: {block_height}")
                print(f"      Status: {status}")
                print(f"      From: {tx_from}")
                print(f"      To: {tx_to}")
                print(f"      Reward Address: {reward_addr}")
                print(f"      For this wallet: {reward_addr.lower() == wallet_addr_lower or (tx_from == 'network' and tx_to.lower() == wallet_addr_lower)}")
            
            print(f"\n  TOTAL REWARDS SUM: {total_rewards:.6f} LKC")
        else:
            print("NO REWARD TRANSACTIONS FOUND!")
        
        # Analyze non-reward transactions
        if other_txs:
            print(f"\n\nOTHER TRANSACTIONS ({len(other_txs)}):")
            print("-" * 70)
            total_from = 0.0
            total_to = 0.0
            total_fees = 0.0
            
            for tx in other_txs:
                amount = float(tx.get('amount', 0))
                fee = float(tx.get('fee', 0))
                tx_type = tx.get('type', 'unknown')
                
                if tx.get('from', '').lower() == wallet_addr_lower:
                    total_from += amount + fee
                if tx.get('to', '').lower() == wallet_addr_lower:
                    total_to += amount
            
            print(f"  Total Sent Out (with fees): -{total_from:.6f} LKC")
            print(f"  Total Received: +{total_to:.6f} LKC")
        
        # Calculate final balance
        print(f"\n\nBALANCE CALCULATION:")
        print("-" * 70)
        balance = total_rewards
        print(f"  Starting with Rewards: {total_rewards:.6f} LKC")
        if other_txs:
            print(f"  Plus Received: +{total_to:.6f} LKC")
            print(f"  Minus Sent Out: -{total_from:.6f} LKC")
            balance = total_rewards + total_to - total_from
        print(f"  FINAL BALANCE: {max(0, balance):.6f} LKC")
        
        print(f"\n{'='*70}\n")
        
    except Exception as e:
        print(f"ERROR during diagnosis: {e}")
        import traceback
        traceback.print_exc()

def format_amount(amount: float, is_incoming: bool = True) -> str:
    """Format amount with sign based on direction"""
    sign = "+" if is_incoming else "-"
    return f"{sign}{amount:.6f}"

def assess_transaction_risk(transaction: Dict) -> tuple[str, str]:
    """Assess transaction risk using lunalib security"""
    security = TransactionSecurity()
    return security.assess_risk(transaction)

def validate_transaction_security(transaction: Dict) -> tuple[bool, str]:
    """Validate transaction security using lunalib"""
    security = TransactionSecurity()
    return security.validate_transaction_security(transaction)

# Optimize blockchain scanning to use incremental updates

def scan_blockchain_incrementally():
    """Perform incremental blockchain scanning using lunalib 1.6.6."""
    try:
        print("DEBUG: Starting incremental blockchain scan...")
        client.blockchain.scan_for_updates()
        print("DEBUG: Incremental blockchain scan completed.")
    except Exception as e:
        print(f"ERROR: Blockchain scan failed: {e}")

def trigger_scan_if_behind():
    """Trigger a blockchain or mempool scan only if behind the current height."""
    try:
        current_blockchain_height = client.blockchain.get_current_height()
        latest_blockchain_height = client.blockchain.get_latest_height()

        current_mempool_height = client.mempool.get_current_height()
        latest_mempool_height = client.mempool.get_latest_height()

        if current_blockchain_height < latest_blockchain_height:
            print("DEBUG: Blockchain is behind. Triggering scan...")
            client.blockchain.scan_for_updates()

        if current_mempool_height < latest_mempool_height:
            print("DEBUG: Mempool is behind. Triggering scan...")
            client.mempool.scan_for_updates()

    except Exception as e:
        print(f"ERROR: Failed to check or trigger scan: {e}")

def _register_with_primary(self):
        """Register this node with the primary daemon using the updated endpoint."""
        max_retries = 3
        retry_delay = 5  # seconds

        for attempt in range(max_retries):
            try:
                peer_info = {
                    'node_id': self.node_id,
                    'timestamp': time.time(),
                    'capabilities': ['sync', 'relay'],
                    'peer_url': f"https://{socket.gethostname()}:{8545}"  # Example peer URL
                }

                print(f"DEBUG: Attempting registration with payload: {peer_info}")
                response = requests.post(
                    f"{self.primary_node}/peer/add",
                    json=peer_info,
                    timeout=10
                )

                print(f"DEBUG: Server response: {response.status_code} - {response.text}")

                if response.status_code == 200:
                    print(f"✅ Registered with primary node as peer: {self.node_id}")
                    return True
                else:
                    print(f"⚠️  Registration failed (Attempt {attempt + 1}/{max_retries}): {response.status_code}")

            except requests.exceptions.RequestException as e:
                print(f"❌ Registration error (Attempt {attempt + 1}/{max_retries}): {e}")

            # Wait before retrying
            time.sleep(retry_delay)

        print("❌ Registration failed after maximum retries. Continuing without registration.")
        return False

def get_p2p_status(self) -> Dict:
        """Get P2P network status"""
        if not self.p2p_client:
            return {
                'connected': False,
                'peers': 0,
                'peer_list': [],
                'status': 'P2P not available'
            }

        try:
            # Get peers from client or our local list
            peer_count = len(self.peers) if self.peers else 0
            if hasattr(self.p2p_client, 'peers') and self.p2p_client.peers:
                peer_count = len(self.p2p_client.peers)

            return {
                'connected': self.p2p_client.is_running if hasattr(self.p2p_client, 'is_running') else True,
                'peers': peer_count,
                'peer_list': self.peers[:10],  # Return first 10 peers
                'status': 'connected'
            }
        except Exception as e:
            return {
                'connected': False,
                'peers': 0,
                'peer_list': [],
                'status': f'Error: {e}'
            }

def _fetch_peers_from_daemon(self):
        try:
            # Try common P2P daemon endpoints with short timeout
            endpoints = [
                f"{self.config.node_url}/api/peers",
                f"{self.config.node_url}/peers",
                f"{self.config.node_url}/api/p2p/peers",
            ]

            for endpoint in endpoints:
                try:
                    response = requests.get(endpoint, timeout=5)
                    if response.status_code == 200:
                        data = response.json()

                        # Handle different response formats
                        if isinstance(data, list):
                            self.peers = data
                        elif isinstance(data, dict):
                            self.peers = data.get('peers', data.get('nodes', data.get('data', [])))

                        if self.peers:
                            print(f"[DEBUG] Fetched {len(self.peers)} peers from {endpoint}")

                            # Register peers with P2P client if available
                            if self.p2p_client and hasattr(self.p2p_client, 'add_peers'):
                                try:
                                    self.p2p_client.add_peers(self.peers)
                                except:
                                    pass

                            return True
                except:
                    continue

            # No peers found - this is OK, not an error
            print("[DEBUG] No P2P peers available from daemon")
            return False

        except Exception as e:
            print(f"[DEBUG] Peer fetch skipped: {e}")
            return False

def refresh_peers(self) -> Dict:
    """Manually refresh peer list from daemon"""
    success = self._fetch_peers_from_daemon()
    return {
        'success': success,
        'peers': len(self.peers),
        'peer_list': self.peers[:10]
    }

def register_as_peer(self, my_address: str = None, my_port: int = None) -> bool:
    """Register this node as a peer with the daemon (optional, may not be supported)"""
    try:
        # Get local address if not provided
        if not my_address:
            try:
                hostname = socket.gethostname()
                my_address = socket.gethostbyname(hostname)
            except:
                my_address = "127.0.0.1"

        if not my_port:
            my_port = 8545  # Default P2P port

        # Try to register with daemon
        endpoints = [
            f"{self.config.node_url}/api/peers/register",
            f"{self.config.node_url}/peers/register",
        ]

        registration_data = {
            'address': my_address,
            'port': my_port,
            'node_type': 'miner',
            'version': '1.0.0'
        }

        for endpoint in endpoints:
            try:
                response = requests.post(endpoint, json=registration_data, timeout=5)
                if response.status_code in [200, 201]:
                    print(f"[DEBUG] Registered as peer: {my_address}:{my_port}")
                    return True
            except:
                continue

        # Registration not supported - this is OK
        return False

    except Exception as e:
        print(f"[DEBUG] Peer registration skipped: {e}")
        return False
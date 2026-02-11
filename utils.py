import base64
import io
import os
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple


# Import from lunalib (except database)
from lunalib.transactions.transactions import TransactionManager
from lunalib.transactions.security import TransactionSecurity
from lunalib.core.crypto import KeyManager
from lunalib.storage.encryption import EncryptionManager
from lunalib.core.wallet import LunaWallet
try:
    from lunalib.core.p2p import HybridBlockchainClient
except Exception:
    HybridBlockchainClient = None
from lunalib.core.blockchain import BlockchainManager
try:
    from lunalib.core.mempool import MempoolManager
except Exception:
    MempoolManager = None

# Import Storage abstraction
from app.storage import Storage, is_web

blockchain = None
mempool = None
client = None

def _ensure_clients():
    """Lazily initialize blockchain/mempool clients to avoid blocking UI on import."""
    global blockchain, mempool, client
    if blockchain is not None or mempool is not None:
        return blockchain, mempool
    try:
        endpoint = os.getenv("LUNALIB_ENDPOINT_URL") or os.getenv("LUNA_NODE_URL") or os.getenv("PRIMARY_NODE_URL")
        endpoint = endpoint or "https://bank.linglin.art/api/blockchain/full"
        blockchain = BlockchainManager(endpoint_url=endpoint)
        disable_endpoint_calls = str(os.getenv("LUNA_DISABLE_ENDPOINT_CALLS", "1")).strip().lower() in ("1", "true", "yes")

        # Normalize latest block responses (some endpoints return a list)
        try:
            _orig_get_latest_block = blockchain.get_latest_block

            def _safe_get_latest_block():
                try:
                    if disable_endpoint_calls:
                        cache = getattr(blockchain, "cache", None)
                        if cache and hasattr(cache, "get_highest_cached_height"):
                            height = cache.get_highest_cached_height()
                            if isinstance(height, int) and height >= 0:
                                return {"index": height}
                        return None
                    result = _orig_get_latest_block()
                    if isinstance(result, list) and result:
                        return result[-1]
                    return result
                except Exception as e:
                    print(f"DEBUG: _safe_get_latest_block error: {e}")
                    return None

            blockchain.get_latest_block = _safe_get_latest_block
        except Exception as e:
            print(f"DEBUG: Failed to patch get_latest_block: {e}")

        if disable_endpoint_calls:
            try:
                _orig_get_block = getattr(blockchain, "get_block", None)

                def _safe_get_block(height):
                    cache = getattr(blockchain, "cache", None)
                    if cache and hasattr(cache, "get_block"):
                        try:
                            return cache.get_block(height)
                        except Exception:
                            return None
                    return None

                if _orig_get_block:
                    blockchain.get_block = _safe_get_block
            except Exception:
                pass

        mempool_endpoint = os.getenv("LUNALIB_ENDPOINT_URL") or os.getenv("LUNA_NODE_URL") or os.getenv("PRIMARY_NODE_URL")
        mempool = MempoolManager([mempool_endpoint]) if (MempoolManager is not None and mempool_endpoint) else (MempoolManager() if MempoolManager is not None else None)

        # Do not auto-start HybridBlockchainClient to avoid UI hangs
        client = None
    except Exception as e:
        print(f"ERROR: Failed to initialize blockchain client: {e}")
        blockchain = None
        mempool = None
    return blockchain, mempool

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

    _ensure_clients()

    # Get confirmed balance from blockchain transactions

    storage = None
    if client is not None and hasattr(client, 'storage'):
        storage = client.storage
    if storage is None:
        try:
            storage = Storage()
        except Exception as e:
            print(f"WARNING: Could not initialize Storage fallback: {e}")
            storage = None

    confirmed_balance = _calculate_confirmed_balance(wallet_address, storage)

    # Get pending balance from mempool + low-confirmation mined txs
    pending_balance = _calculate_pending_balance(wallet_address)
    pending_balance += _calculate_pending_from_db(wallet_address, storage, min_confirmations=6)

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
    
    def _tx_involves_wallet(tx: dict, wallet_lower: str) -> bool:
        try:
            address_fields = ['from', 'to', 'reward_address', 'recipient', 'sender', 'receiver']
            for field in address_fields:
                value = tx.get(field, '')
                if isinstance(value, str) and value.lower() == wallet_lower:
                    return True
            # Special handling for reward transactions
            if str(tx.get('type', '')).lower() == 'reward':
                reward_address = tx.get('reward_address', '')
                if isinstance(reward_address, str) and reward_address.lower() == wallet_lower:
                    return True
            return False
        except Exception:
            return False

    try:
        # Check if database is None
        if database is None:
            print(f"WARNING: database is None, cannot calculate balance")
            return 0.0
        
        # Get wallet transactions from database - avoid 100-tx limit by preferring get_all_transactions
        wallet_txs = []
        try:
            db_methods = ['get_all_transactions', 'get_transactions', 'get_wallet_transactions']
            for method in db_methods:
                if hasattr(database, method):
                    try:
                        if method == 'get_all_transactions':
                            wallet_txs = getattr(database, method)()
                            print(f"DEBUG BALANCE: Database returned {len(wallet_txs)} total transactions (NO LIMIT)")
                        elif method == 'get_wallet_transactions':
                            wallet_txs = getattr(database, method)(wallet_address, limit=10000)
                        else:
                            wallet_txs = getattr(database, method)(wallet_address)
                        if wallet_txs:
                            break
                    except Exception as e:
                        print(f"WARNING: database.{method} failed: {e}")
                        continue
        except AttributeError as e:
            print(f"WARNING: database transaction retrieval not available: {e}")
            return 0.0
        
        if not wallet_txs:
            print(f"DEBUG BALANCE: No transactions in database for {wallet_address[:12]}")
            return 0.0
        
        # Filter to wallet only (needed when using get_all_transactions)
        if wallet_txs:
            wallet_txs = [tx for tx in wallet_txs if _tx_involves_wallet(tx, wallet_address_lower)]

        print(f"DEBUG BALANCE: Database has {len(wallet_txs)} transactions for {wallet_address[:12]}")
        print(f"DEBUG BALANCE: Looking for wallet (lowercased): {wallet_address_lower}")
        
        # Resolve latest height for confirmations check
        latest_height = None
        try:
            if blockchain is not None:
                if hasattr(blockchain, 'get_latest_height'):
                    latest_height = blockchain.get_latest_height()
                elif hasattr(blockchain, 'get_blockchain_height'):
                    latest_height = blockchain.get_blockchain_height()
                elif hasattr(blockchain, 'get_latest_block'):
                    blk = blockchain.get_latest_block()
                    if isinstance(blk, dict):
                        latest_height = blk.get('index')
        except Exception:
            latest_height = None

        # Process each confirmed transaction
        for tx in wallet_txs:
            # Handle both field name formats
            tx_from = tx.get('from', tx.get('from_address', '')).lower()
            tx_to = tx.get('to', tx.get('to_address', '')).lower()
            tx_type = tx.get('type', tx.get('tx_type', 'transfer')).lower()
            tx_amount = float(tx.get('amount', 0))
            tx_fee = float(tx.get('fee', 0))
            status_raw = tx.get('status', None)
            tx_status = str(status_raw).lower() if status_raw is not None else 'confirmed'
            reward_addr = tx.get('reward_address', '').lower()
            recipient_addr = tx.get('recipient', '').lower()
            
            print(f"  TX: type={tx_type}, from={tx_from[:12] if tx_from else 'none'}, to={tx_to[:12] if tx_to else 'none'}, amount={tx_amount}, status={tx_status}")
            
            # Only count confirmed (blockchain) transactions
            block_height = tx.get('block_height', None)
            confirmations = None
            if block_height is not None and latest_height is not None:
                try:
                    confirmations = max(0, int(latest_height) - int(block_height) + 1)
                except Exception:
                    confirmations = None

            if tx_status not in ('pending', 'unconfirmed', 'mempool') and not (confirmations is not None and confirmations < 6):
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


def _calculate_pending_from_db(wallet_address: str, database, min_confirmations: int = 6) -> float:
    """Treat mined txs with <min_confirmations as pending balance."""
    if database is None:
        return 0.0

    pending_balance = 0.0
    wallet_address_lower = wallet_address.lower()

    # Resolve latest height for confirmations check
    latest_height = None
    try:
        if blockchain is not None:
            if hasattr(blockchain, 'get_latest_height'):
                latest_height = blockchain.get_latest_height()
            elif hasattr(blockchain, 'get_blockchain_height'):
                latest_height = blockchain.get_blockchain_height()
            elif hasattr(blockchain, 'get_latest_block'):
                blk = blockchain.get_latest_block()
                if isinstance(blk, dict):
                    latest_height = blk.get('index')
    except Exception:
        latest_height = None

    # Get transactions
    txs = []
    try:
        if hasattr(database, 'get_all_transactions'):
            txs = database.get_all_transactions()
        elif hasattr(database, 'get_transactions'):
            txs = database.get_transactions(wallet_address)
        elif hasattr(database, 'get_wallet_transactions'):
            txs = database.get_wallet_transactions(wallet_address, limit=10000)
    except Exception:
        txs = []

    if not txs or latest_height is None:
        return 0.0

    # Filter to this wallet
    def _tx_involves_wallet(tx: dict) -> bool:
        address_fields = ['from', 'to', 'reward_address', 'recipient', 'sender', 'receiver']
        for field in address_fields:
            value = tx.get(field, '')
            if isinstance(value, str) and value.lower() == wallet_address_lower:
                return True
        if str(tx.get('type', '')).lower() == 'reward':
            reward_address = tx.get('reward_address', '')
            if isinstance(reward_address, str) and reward_address.lower() == wallet_address_lower:
                return True
        return False

    txs = [tx for tx in txs if _tx_involves_wallet(tx)]

    for tx in txs:
        block_height = tx.get('block_height', None)
        if block_height is None:
            continue
        try:
            confirmations = max(0, int(latest_height) - int(block_height) + 1)
        except Exception:
            continue
        if confirmations >= min_confirmations:
            continue

        tx_from = tx.get('from', tx.get('from_address', '')).lower()
        tx_to = tx.get('to', tx.get('to_address', '')).lower()
        reward_addr = tx.get('reward_address', '').lower()
        recipient_addr = tx.get('recipient', '').lower()
        tx_type = tx.get('type', tx.get('tx_type', 'transfer')).lower()
        tx_amount = float(tx.get('amount', 0))
        tx_fee = float(tx.get('fee', 0))

        if tx_type == 'reward':
            if (reward_addr == wallet_address_lower or tx_to == wallet_address_lower):
                pending_balance += tx_amount
        elif tx_type == 'fee_distribution':
            if (recipient_addr == wallet_address_lower or reward_addr == wallet_address_lower or tx_to == wallet_address_lower):
                pending_balance += tx_amount
        elif tx_from == wallet_address_lower:
            pending_balance -= (tx_amount + tx_fee)
        elif tx_to == wallet_address_lower:
            pending_balance += tx_amount

    return pending_balance


def _calculate_pending_balance(wallet_address: str) -> float:
    """
    Calculate pending balance from mempool transactions.
    
    Args:
        wallet_address: Wallet address
        
    Returns:
        Pending balance amount (can be negative for net outgoing transactions)
    """
    try:
        _ensure_clients()
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


def format_balance_display(available: float, pending: float = None, decimals: int = 2) -> Tuple[str, str]:
    """
    Format balances for UI display.
    
    Args:
        available: Available (confirmed) balance
        pending: Pending balance (optional)
        decimals: Number of decimal places
        
    Returns:
        Tuple of (available_text, pending_text)
    """
    available_text = format_amount_with_unit(available, decimals=decimals)
    
    if pending is not None:
        pending_text = format_amount_with_unit(pending, decimals=decimals)
    else:
        pending_text = "0.000000LKC"
    
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
    return (
        f"Available: {format_amount_with_unit(available)} | "
        f"Pending: {format_amount_with_unit(pending)} | "
        f"Total: {format_amount_with_unit(total)}"
    )

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

def _trim_number(value_str: str) -> str:
    """Trim trailing zeros and dot from a numeric string."""
    if "." in value_str:
        value_str = value_str.rstrip("0").rstrip(".")
    return value_str


def _compact_amount(value: float, decimals: int = 2) -> tuple[str, str]:
    """Return (number_text, prefix) using 1000-based compact units."""
    prefixes = [
        ("", 1),
        ("k", 1_000),
        ("m", 1_000_000),
        ("g", 1_000_000_000),
        ("t", 1_000_000_000_000),
        ("p", 1_000_000_000_000_000),
        ("e", 1_000_000_000_000_000_000),
    ]

    abs_value = abs(value)
    prefix = ""
    scale = 1
    for p, s in prefixes:
        if abs_value >= s:
            prefix = p
            scale = s
    scaled = value / scale
    number_text = _trim_number(f"{scaled:.{decimals}f}")
    return number_text, prefix


def format_amount(value: float, decimals: int = 2, show_sign: bool = False, compact: bool = True) -> str:
    """Format numeric amounts with optional compact units and sign (no unit suffix)."""
    try:
        number = float(value)
    except Exception:
        number = 0.0

    if compact and abs(number) >= 1000:
        number_text, _ = _compact_amount(number, decimals=decimals)
    else:
        number_text = _trim_number(f"{number:,.{decimals}f}")

    if show_sign and not number_text.startswith("-"):
        number_text = f"+{number_text}"
    return number_text


def format_amount_with_unit(value: float, decimals: int = 2, show_sign: bool = False, compact: bool = True, unit: str = "LKC") -> str:
    """Format amount with LKC unit using lunalib formatting (supports tiny units)."""
    try:
        number = float(value)
    except Exception:
        number = 0.0

    # Flat LKC display (no compact units, full decimals)
    try:
        if os.getenv("LUNAWALLET_FLAT_LKC") == "1":
            text = f"{number:.11f}".rstrip("0").rstrip(".")
            return f"{text}{unit}"
    except Exception:
        pass

    # Prefer lunalib formatter for tiny units (m/μ/n/p) and large units (k/M/G/T)
    try:
        from lunalib.utils.formatting import format_amount as lunalib_format_amount

        text = lunalib_format_amount(number, unit=unit)
        # Remove space for base unit only (e.g., "1 LKC" -> "1LKC")
        if unit and text.endswith(f" {unit}"):
            text = text[:-len(unit)-1] + unit
        return text
    except Exception:
        pass

    # Fallback to local compact formatting
    if compact and abs(number) >= 1000:
        number_text, prefix = _compact_amount(number, decimals=decimals)
        unit_text = f"{prefix}{unit}"
        return f"{number_text} {unit_text}"

    number_text = format_amount(number, decimals=decimals, show_sign=show_sign, compact=False)
    return f"{number_text}{unit}"

def format_balance(balance: float, decimals: int = 2, with_unit: bool = False, show_sign: bool = False) -> str:
    """Format balance with optional compact unit and sign."""
    if with_unit:
        return format_amount_with_unit(balance, decimals=decimals, show_sign=show_sign)
    return format_amount(balance, decimals=decimals, show_sign=show_sign)

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
    if hasattr(key_manager, "validate_private_key"):
        return key_manager.validate_private_key(private_key)
    # Fallback: accept 64-char hex strings only
    if not isinstance(private_key, str):
        return False, "Private key must be a string"
    key = private_key.strip()
    if len(key) != 64:
        return False, f"Expected 64 hex characters, got {len(key)}"
    try:
        int(key, 16)
    except ValueError:
        return False, "Private key must be hexadecimal"
    return True, "OK"

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

def format_amount_signed(amount: float, is_incoming: bool = True, decimals: int = 6) -> str:
    """Format amount with sign based on direction (no unit)."""
    sign = "+" if is_incoming else "-"
    return f"{sign}{amount:.{decimals}f}"

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


# Additional utilities
def format_address(address):
    return address[:6] + "..." + address[-6:] if address else ""

# Lunaアドレスのバリデーション
def validate_luna_address(address: str) -> (bool, str):
    """
    Lunaアドレスのバリデーション。形式・長さ・プレフィックス・文字種をチェック。
    Returns: (is_valid, reason)
    """
    if not address or not isinstance(address, str):
        return False, "Address is empty or not a string"
    if len(address) < 20:
        return False, "Address is too short (minimum 20 characters)"
    if not address.startswith("LUN_"):
        return False, "Address must start with 'LUN_'"
    # 文字種チェック（英数字と一部記号のみ許可）
    import re
    if not re.match(r'^LUN_[A-Za-z0-9]+$', address):
        return False, "Address contains invalid characters"
    # 追加のチェック（例: ブラックリストや自分自身への送金禁止など）
    # ...
    return True, "Valid address"
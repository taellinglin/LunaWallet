import base64
import io
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from PIL import Image

# Import from lunalib
from lunalib.transactions.transactions import TransactionManager
from lunalib.transactions.security import TransactionSecurity
from lunalib.core.crypto import KeyManager
from lunalib.storage.encryption import EncryptionManager
from lunalib.core.wallet import LunaWallet
from lunalib.core.mempool import MempoolManager

# ============================================================================
# UNIFIED BALANCE CALCULATION SYSTEM
# ============================================================================

def calculate_wallet_balances(wallet_address: str, database=None, mempool_manager=None) -> Dict[str, float]:
    """
    Calculate both available (confirmed blockchain) and pending (mempool) balances for a wallet.
    
    Args:
        wallet_address: The wallet address to calculate balances for
        database: The database instance to query confirmed transactions
        mempool_manager: The mempool manager to query pending transactions
        
    Returns:
        Dict with keys: 'available', 'pending', 'total'
    """
    print(f"DEBUG: calculate_wallet_balances called for {wallet_address[:8]} with database={database is not None}, mempool={mempool_manager is not None}")
    
    available_balance = 0.0
    pending_balance = 0.0
    
    wallet_addr_lower = wallet_address.lower()
    
    # Calculate available balance from confirmed blockchain transactions
    if database:
        try:
            available_balance = _calculate_confirmed_balance(wallet_addr_lower, database)
        except Exception as e:
            print(f"ERROR: Failed to calculate confirmed balance: {e}")
            available_balance = 0.0
    
    # Calculate pending balance from mempool
    # NOTE: Pass the ORIGINAL address (not lowercased) to mempool as it may be case-sensitive
    if mempool_manager:
        try:
            pending_balance = _calculate_pending_balance(wallet_address, mempool_manager)
        except Exception as e:
            print(f"ERROR: Failed to calculate pending balance: {e}")
            pending_balance = 0.0
    
    # Ensure balances don't go negative
    available_balance = max(0.0, available_balance)
    pending_balance = max(0.0, pending_balance)  # Note: pending can go negative (net outgoing)
    
    total_balance = available_balance + pending_balance
    
    return {
        'available': available_balance,
        'pending': pending_balance,
        'total': total_balance,
        'confirmed': available_balance  # Alias for clarity
    }


def _calculate_confirmed_balance(wallet_address_lower: str, database) -> float:
    """
    Calculate confirmed balance from blockchain transactions stored in database.
    
    Args:
        wallet_address_lower: Wallet address in lowercase
        database: The database instance
        
    Returns:
        Confirmed balance amount
    """
    confirmed_balance = 0.0
    
    try:
        # Get all transactions from database
        all_txs = database.get_all_transactions()
        
        # Filter transactions for this wallet
        wallet_txs = [tx for tx in all_txs if 
                      (tx.get('from', '').lower() == wallet_address_lower or 
                       tx.get('to', '').lower() == wallet_address_lower or
                       tx.get('reward_address', '').lower() == wallet_address_lower)]
        
        print(f"DEBUG BALANCE: Calculating for {wallet_address_lower[:8]} - Found {len(wallet_txs)} relevant transactions")
        
        # Process each confirmed transaction
        for tx in wallet_txs:
            tx_from = tx.get('from', '').lower()
            tx_to = tx.get('to', '').lower()
            tx_type = tx.get('type', 'transfer').lower()
            tx_amount = float(tx.get('amount', 0))
            tx_fee = float(tx.get('fee', 0))
            tx_status = tx.get('status', 'confirmed')
            reward_addr = tx.get('reward_address', '').lower()
            
            print(f"  TX: type={tx_type}, from={tx_from[:8] if tx_from else 'none'}, to={tx_to[:8] if tx_to else 'none'}, reward_addr={reward_addr[:8] if reward_addr else 'none'}, amount={tx_amount}, status={tx_status}")
            
            # Only count confirmed (blockchain) transactions
            if tx_status == 'confirmed':
                # Handle mining rewards (saved with 'to' field when from='network' OR with 'reward_address')
                if tx_type == 'reward':
                    # Check if this reward is for us (either via reward_address or to field if from is 'network')
                    if reward_addr == wallet_address_lower or (tx_from == 'network' and tx_to == wallet_address_lower):
                        print(f"    -> COUNTED as reward: +{tx_amount}")
                        confirmed_balance += tx_amount
                    else:
                        print(f"    -> NOT reward for us (reward_addr={reward_addr}, to={tx_to})")
                # Handle fee distributions
                elif tx_type == 'fee_distribution' and reward_addr == wallet_address_lower:
                    print(f"    -> COUNTED as fee distribution: +{tx_amount}")
                    confirmed_balance += tx_amount
                # Handle regular transfers
                elif tx_type in ['transfer', 'stake', 'delegate', 'gtx_genesis']:
                    # Incoming transaction
                    if tx_to == wallet_address_lower:
                        print(f"    -> COUNTED as incoming transfer: +{tx_amount}")
                        confirmed_balance += tx_amount
                    # Outgoing transaction
                    elif tx_from == wallet_address_lower:
                        print(f"    -> COUNTED as outgoing transfer: -{tx_amount} (fee: -{tx_fee})")
                        confirmed_balance -= tx_amount
                        confirmed_balance -= tx_fee
                else:
                    print(f"    -> NOT COUNTED (type mismatch)")
            else:
                print(f"    -> NOT COUNTED (status={tx_status}, not confirmed)")
    
    except Exception as e:
        print(f"ERROR: Failed to calculate confirmed balance: {e}")
        import traceback
        traceback.print_exc()
        return 0.0
    
    print(f"DEBUG BALANCE: Final confirmed balance for {wallet_address_lower[:8]}: {confirmed_balance}")
    return max(0.0, confirmed_balance)


def _calculate_pending_balance(wallet_address: str, mempool_manager) -> float:
    """
    Calculate pending balance from mempool transactions.
    
    Args:
        wallet_address: Wallet address (original case, as lunalib might be case-sensitive)
        mempool_manager: The MempoolManager instance
        
    Returns:
        Pending balance amount (can be negative if net outgoing)
    """
    pending_balance = 0.0
    wallet_addr_lower = wallet_address.lower()
    
    try:
        print(f"\nDEBUG MEMPOOL: Getting pending txs for {wallet_address[:8]}...")
        
        # Get pending transactions from mempool
        pending_txs = mempool_manager.get_pending_transactions(wallet_address)
        
        print(f"DEBUG MEMPOOL: mempool_manager.get_pending_transactions() returned: {pending_txs}")
        print(f"DEBUG MEMPOOL: Type: {type(pending_txs)}, Length: {len(pending_txs) if pending_txs else 0}")
        
        if pending_txs:
            print(f"DEBUG MEMPOOL: Processing {len(pending_txs)} pending transactions...")
            # Process each pending transaction
            for i, tx in enumerate(pending_txs):
                tx_from = tx.get('from', '').lower()
                tx_to = tx.get('to', '').lower()
                tx_amount = float(tx.get('amount', 0))
                tx_fee = float(tx.get('fee', 0))
                tx_hash = tx.get('hash', 'unknown')
                
                print(f"  [TX {i}] hash={tx_hash[:8] if isinstance(tx_hash, str) else tx_hash}")
                print(f"    from={tx_from[:8] if tx_from else 'none'}, to={tx_to[:8] if tx_to else 'none'}")
                print(f"    amount={tx_amount}, fee={tx_fee}")
                
                # Incoming transaction
                if tx_to == wallet_addr_lower:
                    print(f"    -> COUNTED as incoming: +{tx_amount}")
                    pending_balance += tx_amount
                # Outgoing transaction
                elif tx_from == wallet_addr_lower:
                    print(f"    -> COUNTED as outgoing: -{tx_amount} (fee: -{tx_fee})")
                    pending_balance -= tx_amount
                    pending_balance -= tx_fee
                else:
                    print(f"    -> NOT COUNTED (wallet not in from/to)")
        else:
            print(f"DEBUG MEMPOOL: No pending transactions found")
    
    except Exception as e:
        print(f"ERROR: Failed to calculate pending balance: {e}")
        import traceback
        traceback.print_exc()
        return 0.0
    
    print(f"DEBUG MEMPOOL: Final pending balance: {pending_balance}\n")
    return pending_balance


def update_all_wallet_balances(wallets: Dict, database=None, mempool_manager=None) -> Dict:
    """
    Update balances for all wallets.
    
    Args:
        wallets: Dictionary of wallet data keyed by address
        database: The database instance
        mempool_manager: The mempool manager
        
    Returns:
        Updated wallets dictionary with balance fields
    """
    # Initialize mempool manager if not provided
    if mempool_manager is None:
        try:
            mempool_manager = MempoolManager()
        except:
            mempool_manager = None
    
    # Calculate and update balance for each wallet
    for wallet_addr, wallet_data in wallets.items():
        balances = calculate_wallet_balances(wallet_addr, database, mempool_manager)
        
        # Update wallet data with calculated balances
        wallet_data['balance'] = balances['total']
        wallet_data['confirmed_balance'] = balances['available']
        wallet_data['available_balance'] = balances['available']
        wallet_data['pending_balance'] = balances['pending']
    
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
    available_text = f"{available:.{decimals}f} LUN"
    
    if pending is not None:
        pending_text = f"{pending:.{decimals}f} LUN"
    else:
        pending_text = "0.000000 LUN"
    
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
    return f"Available: {available:.6f} LUN | Pending: {pending:.6f} LUN | Total: {total:.6f} LUN"

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
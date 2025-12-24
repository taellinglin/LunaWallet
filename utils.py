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
            available_balance = _calculate_confirmed_balance(wallet_address, database)
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
    
    # Ensure available balance doesn't go negative
    available_balance = max(0.0, available_balance)
    # NOTE: pending_balance CAN be negative for net outgoing transactions
    # This is intentional - shows pending debits (outgoing transfers/fees)
    
    total_balance = available_balance + pending_balance
    
    return {
        'available': available_balance,
        'pending': pending_balance,
        'total': total_balance,
        'confirmed': available_balance  # Alias for clarity
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


def _calculate_pending_balance(wallet_address: str, mempool_manager) -> float:
    """
    Calculate pending balance from mempool transactions.
    Accounts for both incoming and outgoing transactions, including inter-wallet transfers.
    
    Args:
        wallet_address: Wallet address (original case, as lunalib might be case-sensitive)
        mempool_manager: The MempoolManager instance
        
    Returns:
        Pending balance amount (can be negative for net outgoing transactions)
    """
    pending_balance = 0.0
    wallet_addr_lower = wallet_address.lower()
    incoming_count = 0
    outgoing_count = 0
    
    try:
        print(f"\nDEBUG MEMPOOL: Getting pending txs for {wallet_address[:12]}...")
        print(f"DEBUG MEMPOOL: Wallet (lowercased): {wallet_addr_lower}")
        
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
                tx_type = tx.get('type', 'transfer').lower()
                tx_hash = tx.get('hash', 'unknown')
                
                print(f"  [TX {i}] hash={tx_hash[:12] if isinstance(tx_hash, str) else tx_hash}, type={tx_type}")
                print(f"    from={tx_from[:12] if tx_from else 'none'}, to={tx_to[:12] if tx_to else 'none'}")
                print(f"    amount={tx_amount}, fee={tx_fee}")
                print(f"    wallet_addr_lower={wallet_addr_lower[:12]}")
                
                # Incoming transaction (inter-wallet or external)
                if tx_to == wallet_addr_lower:
                    print(f"    -> COUNTED as incoming: +{tx_amount} (to this wallet)")
                    pending_balance += tx_amount
                    incoming_count += 1
                # Outgoing transaction (inter-wallet or external)
                elif tx_from == wallet_addr_lower:
                    print(f"    -> COUNTED as outgoing: -{tx_amount} (from this wallet), fee: -{tx_fee}")
                    pending_balance -= tx_amount
                    pending_balance -= tx_fee
                    outgoing_count += 1
                else:
                    print(f"    -> NOT COUNTED (neither from nor to this wallet)")
                    print(f"       tx_from={tx_from[:16] if tx_from else 'none'} vs {wallet_addr_lower}")
                    print(f"       tx_to={tx_to[:16] if tx_to else 'none'} vs {wallet_addr_lower}")
        else:
            print(f"DEBUG MEMPOOL: No pending transactions found")
    
    except Exception as e:
        print(f"ERROR: Failed to calculate pending balance: {e}")
        import traceback
        traceback.print_exc()
        return 0.0
    
    print(f"DEBUG MEMPOOL: Pending balance summary for {wallet_address[:12]}:")
    print(f"  - Incoming: {incoming_count} transactions")
    print(f"  - Outgoing: {outgoing_count} transactions")
    print(f"  - Net pending balance: {pending_balance}\n")
    return pending_balance


def update_all_wallet_balances(wallets: Dict, database=None, mempool_manager=None) -> Dict:
    """
    Update balances for all wallets, accounting for inter-wallet transfers.
    This function recalculates balances for ALL wallets to ensure that when
    one wallet sends funds to another, both balances are properly updated.
    
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
    
    print(f"\n=== UPDATE ALL WALLET BALANCES ===")
    print(f"Updating {len(wallets)} wallets...")
    
    # Calculate and update balance for each wallet
    for wallet_addr, wallet_data in wallets.items():
        balances = calculate_wallet_balances(wallet_addr, database, mempool_manager)
        
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
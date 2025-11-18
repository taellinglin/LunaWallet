import base64
import io
import time
from datetime import datetime
from typing import Dict, List, Optional
from PIL import Image

# Import from lunalib
from lunalib.transactions.transactions import TransactionManager
from lunalib.transactions.security import TransactionSecurity
from lunalib.core.crypto import KeyManager
from lunalib.storage.encryption import EncryptionManager
from lunalib.core.wallet import LunaWallet

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
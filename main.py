import flet as ft
import threading
import time
import os
import json
import shutil
from datetime import datetime
import base64
from typing import Dict, List
import sqlite3
from pathlib import Path

# Import unified balance utilities
from utils import (
    calculate_wallet_balances,
    update_all_wallet_balances,
    format_balance_display,
    get_balance_summary
)

# FIX: Ensure cache directory exists with proper permissions
def setup_cache_directory():
    """Create cache directory for lunalib with proper permissions"""
    try:
        # Try multiple possible cache locations
        cache_locations = [
            Path.home() / "AppData" / "Local" / "lunalib" / "cache",
            Path.home() / ".lunalib" / "cache", 
            Path("./.lunalib_cache"),
            Path("/tmp/lunalib_cache")  # For Unix-like systems
        ]
        
        for cache_dir in cache_locations:
            try:
                cache_dir.mkdir(parents=True, exist_ok=True)
                
                # Test if we can create a file in this directory
                test_file = cache_dir / "test_write.tmp"
                with open(test_file, 'w') as f:
                    f.write("test")
                os.remove(test_file)
                
                print(f"DEBUG: Using cache directory: {cache_dir}")
                
                # Set environment variable for lunalib
                os.environ['LUNALIB_CACHE_DIR'] = str(cache_dir)
                return str(cache_dir)
                
            except (PermissionError, OSError) as e:
                print(f"DEBUG: Cache directory {cache_dir} not accessible: {e}")
                continue
        
        # If all else fails, use current directory
        fallback_dir = Path("./lunalib_cache")
        fallback_dir.mkdir(exist_ok=True)
        os.environ['LUNALIB_CACHE_DIR'] = str(fallback_dir)
        print(f"DEBUG: Using fallback cache directory: {fallback_dir}")
        return str(fallback_dir)
        
    except Exception as e:
        print(f"DEBUG: Critical error setting up cache: {e}")
        # Last resort - use temp directory
        import tempfile
        temp_dir = tempfile.mkdtemp(prefix="lunalib_cache_")
        os.environ['LUNALIB_CACHE_DIR'] = temp_dir
        print(f"DEBUG: Using temp cache directory: {temp_dir}")
        return temp_dir

# Initialize cache directory before any lunalib imports
CACHE_DIR = setup_cache_directory()

# Now import lunalib components after cache is set up
from gui.page_create_wallet import CreateWalletPage
from gui.page_export_key import ExportKeyPage
from gui.page_import_wallet import ImportWalletPage
from gui.page_lock import LockPage
from gui.page_receive import ReceivePage
from gui.page_send import SendPage
from gui.page_wallet import WalletPage
from gui.page_settings import SettingsPage
from gui.tab_menu import MenuTab
from gui.tab_transactions import TransactionsTab
from gui.tab_wallets import WalletsTab

# Import lunalib components
from lunalib.core.wallet import LunaWallet
from lunalib.core.blockchain import BlockchainManager
from lunalib.transactions.transactions import TransactionManager
from lunalib.storage.encryption import EncryptionManager
from lunalib.storage.database import WalletDatabase

# Import utils
from utils import format_address, format_balance, format_timestamp, get_transaction_color, get_transaction_icon
import os
import sqlite3
from pathlib import Path

# Ensure cache directory exists
cache_dir = Path.home() / "AppData" / "Local" / "lunalib" / "cache"
cache_dir.mkdir(parents=True, exist_ok=True)

class LunaWalletApp:
    """Luna Wallet Application with Red Theme - Responsive Mobile Support"""
    
    def __init__(self):
        self._patch_lunalib_cache()
        self.wallet_core = LunaWallet()
        self.blockchain_manager = BlockchainManager(endpoint_url="https://bank.linglin.art")
        self.transaction_manager = TransactionManager(network_endpoints=["https://bank.linglin.art"])
        self.encryption_manager = EncryptionManager()
        self.database = WalletDatabase()
        self._patch_blockchain_scanner()
        self.minimized_to_tray = False
        self.current_tab_index = 0
        self.snack_bar = None
        self.selected_wallet_index = 0
        self.last_activity_time = time.time()
        self.auto_lock_minutes = 30
        self.is_locked = True
        self.is_mobile = False
        self.is_landscape = False
        self.current_layout = "desktop"
        self.sidebar_collapsed = False
        self.sidebar_width = 240
        self.sidebar_collapsed_width = 60

        # Refs for UI elements
        self.refs = {}

        # Initialize page references
        self.current_page = None
        self.current_lock_page = None
        self.pages = {}

        # Wallet persistence state - ENHANCED
        self.wallet_file_path = self._get_wallet_file_path()
        self.last_save_time = 0
        self.save_cooldown = 2  # seconds between saves to prevent too frequent saves
        self.backup_count = 0
        self.max_backups = 5
        
        self.sound_enabled = True
        
        # NEW: Initialize data directory and load any existing wallet metadata
        self._ensure_data_directory()
        self._load_wallet_metadata()
        
        # Background sync state
        self.background_sync_active = False
        self.last_background_sync_time = 0
        self.background_sync_interval = 60 * 60  # 60 minutes in seconds
        
        # NEW: Continuous blockchain scanning state
        self.continuous_scan_active = False
        self.last_scanned_block = 0
        self.wallet_balances_cache = {}  # Cache of wallet balances to detect changes
        self.scan_interval = 30  # Scan every 30 seconds
    def debug_transaction_detection(self):
        """Debug method to see what transactions are being detected"""
        if not self.wallet_core.current_wallet_address:
            print("❌ No wallet address")
            return
        
        address = self.wallet_core.current_wallet_address
        print(f"\n🔍 DEBUG TRANSACTION DETECTION for {address}")
        print("=" * 60)
        
        # Get latest block
        latest_block = self.blockchain_manager.get_latest_block()
        if latest_block:
            print(f"Latest block: #{latest_block.get('index')}")
            print(f"Transactions in block: {len(latest_block.get('transactions', []))}")
            
            # Show all transactions in latest block
            for i, tx in enumerate(latest_block.get('transactions', [])):
                print(f"\nTX {i}:")
                for key, value in tx.items():
                    if isinstance(value, str) and len(value) > 20:  # Likely an address
                        print(f"  {key}: {value[:20]}...")
                    else:
                        print(f"  {key}: {value}")
        
        # Try to scan
        try:
            print(f"\n📡 Scanning for transactions...")
            transactions = self.blockchain_manager.scan_transactions_for_address(address)
            print(f"Found {len(transactions)} transactions")
            
            for tx in transactions:
                direction = tx.get('direction', 'unknown')
                print(f"\n{direction.upper()}: {tx.get('hash', '')[:16]}...")
                print(f"  From: {tx.get('from', 'unknown')}")
                print(f"  To: {tx.get('to', 'unknown')}")
                print(f"  Amount: {tx.get('amount', 0)}")
                print(f"  Fee: {tx.get('fee', 0)}")
        except Exception as e:
            print(f"❌ Scan error: {e}")
    def _create_enhanced_blockchain_manager(self):
        """Create an enhanced BlockchainManager with proper outgoing transaction detection"""
        # Create the blockchain manager
        from lunalib.core.blockchain import BlockchainManager as BaseBlockchainManager
        
        class EnhancedBlockchainManager(BaseBlockchainManager):
            """Enhanced blockchain manager that properly detects outgoing transactions"""
            
            def _find_address_transactions(self, block: Dict, address: str) -> List[Dict]:
                """Find transactions in block that involve the address - FIXED FOR OUTGOING"""
                transactions = []
                address_lower = address.lower()
                
                # Debug: Show what we're looking for
                print(f"🔍 Scanning block #{block.get('index')} for address: {address}")
                
                # Check block reward (miner rewards)
                miner = block.get('miner', '').lower()
                reward_address = block.get('reward_address', '').lower()
                if miner == address_lower or reward_address == address_lower:
                    reward_tx = {
                        'type': 'reward',
                        'from': 'network',
                        'to': address,
                        'amount': block.get('reward', 0),
                        'block_height': block.get('index'),
                        'timestamp': block.get('timestamp'),
                        'hash': f"reward_{block.get('index')}_{address}",
                        'status': 'confirmed',
                        'description': f'Mining reward for block #{block.get("index")}',
                        'direction': 'incoming'
                    }
                    transactions.append(reward_tx)
                    print(f"🎁 Found mining reward: {block.get('reward', 0)} LKC")
                
                # Check all transactions in the block
                block_transactions = block.get('transactions', [])
                print(f"  Block has {len(block_transactions)} transactions")
                
                for tx_index, tx in enumerate(block_transactions):
                    # Get addresses from transaction
                    from_addr = (tx.get('from') or '').lower()
                    to_addr = (tx.get('to') or '').lower()
                    amount = tx.get('amount', 0)
                    fee = tx.get('fee', 0)
                    tx_hash = tx.get('hash', '')
                    tx_type = tx.get('type', 'transfer')
                    
                    # Check if this transaction involves our address
                    is_outgoing = from_addr == address_lower
                    is_incoming = to_addr == address_lower
                    
                    if is_outgoing or is_incoming:
                        enhanced_tx = tx.copy()
                        enhanced_tx['block_height'] = block.get('index')
                        enhanced_tx['status'] = 'confirmed'
                        enhanced_tx['tx_index'] = tx_index
                        
                        if is_outgoing:
                            # This is an OUTGOING transaction - WE sent it
                            enhanced_tx['direction'] = 'outgoing'
                            enhanced_tx['effective_amount'] = -(float(amount) + float(fee))
                            print(f"    ⬇️ FOUND OUTGOING TRANSACTION!")
                            print(f"      From: {from_addr} (OUR ADDRESS)")
                            print(f"      To: {to_addr}")
                            print(f"      Amount: {amount}")
                            print(f"      Fee: {fee}")
                            print(f"      Total: {float(amount) + float(fee)}")
                            print(f"      Hash: {tx_hash[:16]}...")
                            print(f"      Memo: {tx.get('memo', 'None')}")
                        else:
                            # This is an INCOMING transaction - WE received it
                            enhanced_tx['direction'] = 'incoming'
                            enhanced_tx['effective_amount'] = float(amount)
                            print(f"    ⬆️ Found incoming: {amount} from {from_addr}")
                        
                        transactions.append(enhanced_tx)
                
                print(f"  Total transactions found for address: {len(transactions)}")
                return transactions
            
            def _handle_regular_transfers(self, tx: Dict, address_lower: str) -> Dict:
                """Handle regular transfer transactions - FIXED VERSION"""
                enhanced_tx = tx.copy()
                
                # Try to extract addresses from various possible field names
                possible_from_fields = ['from', 'sender', 'from_address', 'source', 'payer']
                possible_to_fields = ['to', 'receiver', 'to_address', 'destination', 'payee']
                possible_amount_fields = ['amount', 'value', 'quantity', 'transfer_amount', 'total_amount']
                possible_fee_fields = ['fee', 'gas', 'transaction_fee', 'gas_fee', 'network_fee']
                
                # Find from address
                from_addr = ''
                for field in possible_from_fields:
                    if field in tx:
                        field_value = tx.get(field, '')
                        if field_value:
                            from_addr = str(field_value).lower()
                            enhanced_tx['from'] = field_value  # Keep original case
                            break
                
                # Find to address
                to_addr = ''
                for field in possible_to_fields:
                    if field in tx:
                        field_value = tx.get(field, '')
                        if field_value:
                            to_addr = str(field_value).lower()
                            enhanced_tx['to'] = field_value  # Keep original case
                            break
                
                # Find amount
                amount = 0.0
                for field in possible_amount_fields:
                    if field in tx:
                        try:
                            amount = float(tx.get(field, 0))
                        except (ValueError, TypeError):
                            amount = 0.0
                        enhanced_tx['amount'] = amount
                        break
                
                # Find fee
                fee = 0.0
                for field in possible_fee_fields:
                    if field in tx:
                        try:
                            fee = float(tx.get(field, 0))
                        except (ValueError, TypeError):
                            fee = 0.0
                        enhanced_tx['fee'] = fee
                        break
                
                # Set direction
                if from_addr == address_lower:
                    enhanced_tx['direction'] = 'outgoing'
                    enhanced_tx['effective_amount'] = -(amount + fee)
                elif to_addr == address_lower:
                    enhanced_tx['direction'] = 'incoming'
                    enhanced_tx['effective_amount'] = amount
                else:
                    # If we can't determine direction from addresses, check other fields
                    enhanced_tx['direction'] = 'unknown'
                    enhanced_tx['effective_amount'] = amount
                
                # Set type if not present
                if not enhanced_tx.get('type'):
                    if 'bill_type' in tx:
                        enhanced_tx['type'] = tx.get('bill_type').lower()
                    else:
                        enhanced_tx['type'] = 'transfer'
                
                return enhanced_tx
    def _patch_lunalib_cache(self):
            """Patch lunalib cache to use our designated directory"""
            try:
                from lunalib.storage import cache as luna_cache
                
                # Override the cache file path
                original_init = luna_cache.BlockchainCache.__init__
                
                def patched_init(self, *args, **kwargs):
                    # Use our cache directory
                    cache_file = Path(CACHE_DIR) / "blockchain_cache.db"
                    self.cache_file = str(cache_file)
                    
                    # Ensure directory exists
                    cache_file.parent.mkdir(parents=True, exist_ok=True)
                    
                    # Initialize the cache
                    self._init_cache()
                
                # Apply the patch
                luna_cache.BlockchainCache.__init__ = patched_init
                print(f"DEBUG: Patched lunalib cache to use: {CACHE_DIR}")
                
            except Exception as e:
                print(f"DEBUG: Error patching lunalib cache: {e}")
    def _play_sound(self, sound_type):
        """Play sound using Flet's audio capabilities (mobile compatible)"""
        if not self.sound_enabled:
            return
            
        try:
            # Use Flet audio for mobile compatibility
            if sound_type == "transaction":
                # You can use Flet's Audio control for mobile
                audio = ft.Audio(
                    src="transaction.wav",
                    autoplay=True,
                )
                self.page.overlay.append(audio)
                print("play transaction sound")
                self.page.update()
            elif sound_type == "send":
                audio = ft.Audio(
                    src="send.wav", 
                    autoplay=True,
                )
                self.page.overlay.append(audio)
                print("play send sound")
                self.page.update()
        except Exception as e:
            print(f"Sound error: {e}")
    def _load_wallet_metadata(self):
        """Load basic wallet metadata without requiring password"""
        try:
            if os.path.exists(self.wallet_file_path):
                print(f"DEBUG: Wallet file exists at: {self.wallet_file_path}")
                
                # Check file size first
                file_size = os.path.getsize(self.wallet_file_path)
                print(f"DEBUG: Wallet file size: {file_size} bytes")
                
                if file_size == 0:
                    print("DEBUG: Wallet file is empty")
                    self.wallet_count = 0
                    self.existing_wallet_address = None
                    return
                
                with open(self.wallet_file_path, 'r', encoding='utf-8') as f:
                    wallet_data = json.load(f)
                
                # Store basic info for UI display
                if 'wallets' in wallet_data:
                    # Handle both dict and list formats
                    wallets = wallet_data['wallets']
                    if isinstance(wallets, dict):
                        self.wallet_count = len(wallets)
                        if self.wallet_count > 0:
                            # Get first wallet address from dict keys
                            first_address = list(wallets.keys())[0]
                            self.existing_wallet_address = first_address
                            print(f"DEBUG: Found {self.wallet_count} wallets (dict format), first address: {self.existing_wallet_address}")
                        else:
                            self.wallet_count = 0
                            self.existing_wallet_address = None
                            print("DEBUG: Wallet file exists but has 0 wallets (dict)")
                    elif isinstance(wallets, list):
                        self.wallet_count = len(wallets)
                        if self.wallet_count > 0:
                            # Get first wallet address from list
                            first_wallet = wallets[0]
                            if isinstance(first_wallet, dict):
                                self.existing_wallet_address = first_wallet.get('address', '')
                            else:
                                self.existing_wallet_address = str(first_wallet)
                            print(f"DEBUG: Found {self.wallet_count} wallets (list format), first address: {self.existing_wallet_address}")
                        else:
                            self.wallet_count = 0
                            self.existing_wallet_address = None
                            print("DEBUG: Wallet file exists but has 0 wallets (list)")
                    else:
                        self.wallet_count = 0
                        self.existing_wallet_address = None
                        print(f"DEBUG: Unexpected wallets format: {type(wallets)}")
                else:
                    self.wallet_count = 0
                    self.existing_wallet_address = None
                    print("DEBUG: Wallet file exists but no 'wallets' key found")
                    
            else:
                self.wallet_count = 0
                self.existing_wallet_address = None
                print(f"DEBUG: No wallet file found at: {self.wallet_file_path}")
        except Exception as e:
            print(f"DEBUG: Error loading wallet metadata: {e}")
            import traceback
            traceback.print_exc()
            self.wallet_count = 0
            self.existing_wallet_address = None

    def _get_wallet_file_path(self):
        """Get the path for wallet data file"""
        data_dir = self._get_data_directory()
        wallet_file = os.path.join(data_dir, "wallet_data.json")
        return wallet_file

    def _get_backup_path(self, backup_id):
        """Get path for backup file"""
        data_dir = self._get_data_directory()
        backup_dir = os.path.join(data_dir, "backups")
        os.makedirs(backup_dir, exist_ok=True)
        return os.path.join(backup_dir, f"wallet_backup_{backup_id}.json")

    def _ensure_data_directory(self):
        """Ensure data directory exists"""
        data_dir = self._get_data_directory()
        os.makedirs(data_dir, exist_ok=True)
        backup_dir = os.path.join(data_dir, "backups")
        os.makedirs(backup_dir, exist_ok=True)
        return data_dir

    def _get_data_directory(self):
        """Get the application data directory"""
        try:
            # Try to get data directory from database or wallet core
            if hasattr(self.database, 'data_dir') and self.database.data_dir:
                return self.database.data_dir
            elif hasattr(self.wallet_core, 'data_dir') and self.wallet_core.data_dir:
                return self.wallet_core.data_dir
            else:
                # Default data directories to check
                default_dirs = [
                    os.path.join(os.path.expanduser("~"), ".luna_wallet"),
                    os.path.join(os.path.expanduser("~"), "LunaWallet"),
                    os.path.join(os.path.dirname(os.path.abspath(__file__)), "data"),
                    "./data"
                ]
                for dir_path in default_dirs:
                    if os.path.exists(dir_path):
                        return dir_path
                # Create the first default if none exist
                os.makedirs(default_dirs[0], exist_ok=True)
                return default_dirs[0]
        except Exception as e:
            print(f"DEBUG: Error getting data directory: {e}")
            fallback_dir = os.path.join(os.path.expanduser("~"), ".luna_wallet")
            os.makedirs(fallback_dir, exist_ok=True)
            return fallback_dir

    def save_wallet_data(self, force_save=False, is_backup=False):
        """Save wallet data to persistent storage"""
        try:
            current_time = time.time()
            
            # Rate limiting for normal saves
            if not force_save and not is_backup:
                if current_time - self.last_save_time < self.save_cooldown:
                    return True
            
            if self.is_locked:
                print("DEBUG: Wallet is locked, skipping save")
                return False
            
            # Ensure data directory exists
            self._ensure_data_directory()
            
            # Prepare wallet data for saving
            wallet_data = self._prepare_wallet_data()
            if not wallet_data:
                print("DEBUG: No wallet data to save")
                return False
            
            # Determine file path
            if is_backup:
                self.backup_count = (self.backup_count % self.max_backups) + 1
                save_path = self._get_backup_path(self.backup_count)
            else:
                save_path = self.wallet_file_path
            
            # Create temporary file first for atomic write
            temp_path = save_path + ".tmp"
            
            try:
                # Save to temporary file
                with open(temp_path, 'w', encoding='utf-8') as f:
                    json.dump(wallet_data, f, indent=2, ensure_ascii=False)
                
                # Atomic replace
                if os.path.exists(save_path):
                    os.replace(temp_path, save_path)
                else:
                    os.rename(temp_path, save_path)
                
                self.last_save_time = current_time
                
                if not is_backup:
                    print(f"DEBUG: Wallet data saved successfully to {save_path}")
                else:
                    print(f"DEBUG: Wallet backup created: {save_path}")
                
                return True
                
            except Exception as e:
                # Clean up temporary file on error
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                raise e
                
        except Exception as e:
            print(f"DEBUG: Error saving wallet data: {e}")
            return False

    def _prepare_wallet_data(self):
        """Prepare wallet data for saving - compatible with LunaWallet structure"""
        try:
            wallet_data = {
                'version': '1.0',
                'timestamp': datetime.now().isoformat(),
                'last_sync': getattr(self, 'last_sync_time', None),
                'wallets': {},
                'current_wallet_address': None,
                'settings': {
                    'auto_lock_minutes': self.auto_lock_minutes,
                    'selected_wallet_index': self.selected_wallet_index
                }
            }
            
            # Get wallet information from LunaWallet
            if hasattr(self.wallet_core, 'wallets') and self.wallet_core.wallets:
                # LunaWallet stores wallets as dict: {address: wallet_data}
                for address, wallet_info in self.wallet_core.wallets.items():
                    # Convert wallet info to serializable format
                    serializable_wallet = wallet_info.copy()
                    
                    # Handle encrypted_private_key - ensure it's bytes for LunaWallet
                    encrypted_key = serializable_wallet.get('encrypted_private_key')
                    if encrypted_key and isinstance(encrypted_key, bytes):
                        # Keep as bytes for LunaWallet compatibility
                        serializable_wallet['encrypted_private_key'] = base64.b64encode(encrypted_key).decode('utf-8')
                    
                    wallet_data['wallets'][address] = serializable_wallet
                
                print(f"DEBUG: Prepared {len(wallet_data['wallets'])} wallets for saving")
            
            # Get current wallet address
            if hasattr(self.wallet_core, 'current_wallet_address') and self.wallet_core.current_wallet_address:
                wallet_data['current_wallet_address'] = self.wallet_core.current_wallet_address
            
            return wallet_data
            
        except Exception as e:
            print(f"DEBUG: Error preparing wallet data: {e}")
            import traceback
            traceback.print_exc()
            return None

    def load_wallet_data(self):
        """Load wallet data from persistent storage - compatible with LunaWallet"""
        try:
            if not os.path.exists(self.wallet_file_path):
                print("DEBUG: No wallet data file found")
                return False
            
            print(f"DEBUG: Loading wallet data from: {self.wallet_file_path}")
            
            with open(self.wallet_file_path, 'r', encoding='utf-8') as f:
                wallet_data = json.load(f)
            
            print("DEBUG: Wallet data loaded from file")
            
            # Restore wallet information to LunaWallet
            if 'wallets' in wallet_data and wallet_data['wallets']:
                # Clear existing wallets
                if hasattr(self.wallet_core, 'wallets'):
                    self.wallet_core.wallets = {}
                
                # Load each wallet
                for address, wallet_info in wallet_data['wallets'].items():
                    # Convert back to proper format for LunaWallet
                    restored_wallet = wallet_info.copy()
                    
                    # Keep cached balances from saved wallet data - DO NOT RESET TO 0
                    # (Placeholder or previous cached value will show until recalculated)
                    
                    # Handle encrypted_private_key - convert back to bytes
                    encrypted_key = restored_wallet.get('encrypted_private_key')
                    if encrypted_key and isinstance(encrypted_key, str):
                        try:
                            restored_wallet['encrypted_private_key'] = base64.b64decode(encrypted_key)
                        except:
                            # If it's already bytes or in different format, keep as is
                            pass
                    
                    self.wallet_core.wallets[address] = restored_wallet
                
                print(f"DEBUG: Restored {len(wallet_data['wallets'])} wallets to LunaWallet")
                
                # Restore current wallet address
                if 'current_wallet_address' in wallet_data and wallet_data['current_wallet_address']:
                    current_address = wallet_data['current_wallet_address']
                    self.wallet_core.current_wallet_address = current_address
                    
                    # Set current wallet data if it exists
                    if current_address in self.wallet_core.wallets:
                        self.wallet_core._set_current_wallet(self.wallet_core.wallets[current_address])
                        print(f"DEBUG: Restored current wallet: {current_address}")
                
                return True
            
            print("DEBUG: No wallets found in loaded data")
            return False
            
        except Exception as e:
            print(f"DEBUG: Error loading wallet data: {e}")
            import traceback
            traceback.print_exc()
            return False
    def _load_from_backup(self):
        """Try to load wallet data from backup files"""
        try:
            backup_dir = os.path.join(self._get_data_directory(), "backups")
            if not os.path.exists(backup_dir):
                return False
            
            # Get all backup files sorted by modification time (newest first)
            backup_files = []
            for file in os.listdir(backup_dir):
                if file.startswith("wallet_backup_") and file.endswith(".json"):
                    file_path = os.path.join(backup_dir, file)
                    backup_files.append((file_path, os.path.getmtime(file_path)))
            
            backup_files.sort(key=lambda x: x[1], reverse=True)
            
            # Try each backup file until one works
            for backup_path, _ in backup_files:
                try:
                    with open(backup_path, 'r', encoding='utf-8') as f:
                        wallet_data = json.load(f)
                    
                    # Restore from backup
                    if 'wallets' in wallet_data and wallet_data['wallets']:
                        if hasattr(self.wallet_core, 'wallets'):
                            self.wallet_core.wallets = wallet_data['wallets']
                        
                        # Copy backup to main file
                        shutil.copy2(backup_path, self.wallet_file_path)
                        print(f"DEBUG: Restored wallet from backup: {backup_path}")
                        return True
                        
                except Exception as e:
                    print(f"DEBUG: Failed to load backup {backup_path}: {e}")
                    continue
            
            return False
            
        except Exception as e:
            print(f"DEBUG: Error loading from backups: {e}")
            return False

    def create_backup(self):
        """Create a backup of wallet data"""
        return self.save_wallet_data(force_save=True, is_backup=True)

    def auto_save_wallet(self):
        """Auto-save wallet data with rate limiting"""
        try:
            if not self.is_locked:
                self.save_wallet_data(force_save=False)
        except Exception as e:
            print(f"DEBUG: Auto-save error: {e}")

    def check_existing_wallets(self):
        """Check if there's an actual primary wallet created"""
        try:
            print("DEBUG: Checking for primary wallet...")
            
            # First try to load from persistent storage
            if self.load_wallet_data():
                print("DEBUG: Wallet data loaded from persistent storage")
                return True
            
            # Method 1: Check if wallet core has a primary wallet with address
            if hasattr(self.wallet_core, 'wallets') and self.wallet_core.wallets:
                if len(self.wallet_core.wallets) > 0:
                    first_wallet = self.wallet_core.wallets[0]
                    if first_wallet.get('address'):
                        print("DEBUG: Found primary wallet in memory")
                        # Save the loaded wallet data
                        self.save_wallet_data(force_save=True)
                        return True
            
            # Method 2: Try to get the current wallet address from core
            if hasattr(self.wallet_core, 'current_wallet_address'):
                if self.wallet_core.current_wallet_address:
                    print("DEBUG: Found current wallet address")
                    return True
            
            # Method 3: Check if we can detect any wallet creation
            if hasattr(self.wallet_core, 'is_wallet_created'):
                if self.wallet_core.is_wallet_created():
                    print("DEBUG: Wallet core indicates wallet is created")
                    return True
            
            print("DEBUG: No primary wallet found")
            return False
            
        except Exception as e:
            print(f"DEBUG: Error checking wallets: {e}")
            return False

    def _is_database_initialized_but_empty(self):
        """Check if database exists but has no actual wallet data"""
        try:
            data_dir = self._get_data_directory()
            db_path = os.path.join(data_dir, "wallets.db")
            wallet_json_path = os.path.join(data_dir, "wallet_data.json")
            
            # Check if we have JSON wallet data
            if os.path.exists(wallet_json_path) and os.path.getsize(wallet_json_path) > 100:
                return False
                
            if not os.path.exists(db_path):
                return False
                
            # Check file size - very small files are likely empty
            if os.path.getsize(db_path) < 1024:  # Less than 1KB
                return True
                
            # Try to query for actual wallet data
            if hasattr(self.database, 'get_all_wallets'):
                wallets = self.database.get_all_wallets()
                if not wallets or len(wallets) == 0:
                    return True
                    
            return False
        except:
            return False

    def on_balance_changed(self):
        """Handle balance changes with auto-save"""
        self.update_balance_display()
        self.save_wallet_data(force_save=True)  # Force save on balance changes
        self._play_sound("transaction")
        self.create_backup()  # Create backup for important changes

    def on_sync_progress(self, progress, message):
        if not self.is_locked and hasattr(self, 'page'):
            if 'progress_sync' in self.refs and self.refs['progress_sync'].current:
                self.refs['progress_sync'].current.value = progress / 100
                self.refs['progress_sync'].current.visible = True
            if 'lbl_sync_status' in self.refs and self.refs['lbl_sync_status'].current:
                self.refs['lbl_sync_status'].current.value = f"Status: {message}"
            self.update_refs()

    def on_transaction_received(self):
        """Handle incoming transactions with auto-save"""
        self.update_transaction_history()
        self.show_snackbar("New transaction received", "success")
        
        # Play transaction sound
        self._play_sound("transaction")
        print("Played Transaction Sound")
        
        self.save_wallet_data(force_save=True)
        self.create_backup()
        
    def on_sync_complete(self):
        """Handle sync completion with auto-save"""
        self.update_balance_display()
        self.update_transaction_history()
        self.show_snackbar("Blockchain sync completed", "success")
        self.save_wallet_data(force_save=True)  # Force save after sync
        self.create_backup()  # Create backup after sync
        
    def on_error(self, error_msg):
        self.show_snackbar(f"Error: {error_msg}", "error")

    def create_main_ui(self, page: ft.Page):
        self.page = page
        
        # Detect if we're on mobile
        self.is_mobile = page.platform in ["ios", "android"]
        self.detect_orientation()
        
        page.title = "Luna Wallet"
        page.theme_mode = ft.ThemeMode.DARK
        page.padding = 0
        
        if not self.is_mobile:
            page.window.width = 1024
            page.window.height = 768
            page.window.min_width = 768
            page.window.min_height = 768
            page.window.center()
            
        page.window.icon = "./wallet_icon.png"
        
        page.on_resize = self.on_page_resize
        
        # Check for existing wallets and show appropriate screen
        self.initialize_wallet_state()

    def initialize_wallet_state(self):
        """Initialize wallet state and show appropriate screen"""
        try:
            print("=" * 50)
            print("DEBUG: Initializing wallet state...")
            
            # Use the pre-loaded metadata to determine wallet existence
            has_existing_wallets = self.wallet_count > 0
            
            print(f"DEBUG: Wallet detection result: {has_existing_wallets}")
            print(f"DEBUG: Existing wallet address: {self.existing_wallet_address}")
            
            if has_existing_wallets:
                print("DEBUG: Wallets found in persistence - showing unlock screen")
                # Show unlock screen with existing wallet message
                self.show_lock_page(
                    title="Welcome Back", 
                    subtitle=f"Unlock your existing wallet\n{self.existing_wallet_address}",
                    wallet_exists=True,
                    show_create=False
                )
            else:
                print("DEBUG: No wallets found - showing create screen")
                # Show create wallet screen for new users
                self.show_lock_page(
                    title="Welcome to Luna Wallet", 
                    subtitle="Create your first wallet to get started", 
                    show_create=True,
                    wallet_exists=False
                )
            print("=" * 50)
                
        except Exception as e:
            print(f"DEBUG: Error in initialize_wallet_state: {e}")
            import traceback
            traceback.print_exc()
            # Fallback to create wallet screen
            self.show_lock_page(show_create=True, wallet_exists=False)

    def detect_orientation(self):
        if not self.is_mobile:
            self.is_landscape = False
            self.current_layout = "desktop"
            return
            
        if hasattr(self.page, 'window') and self.page.window:
            width = self.page.window.width
            height = self.page.window.height
            self.is_landscape = width > height if width and height else False
            self.current_layout = "mobile_landscape" if self.is_landscape else "mobile_portrait"

    def on_page_resize(self, e):
        self.detect_orientation()
        self.update_layout()

    def update_layout(self):
        if not hasattr(self, 'page') or not self.page:
            return
            
        self.page.controls.clear()
        self.show_current_page()
        self.page.update()

    def show_current_page(self):
        self.page.controls.clear()
        if self.current_page:
            # For lock and create pages, center them
            if isinstance(self.current_page, (LockPage, CreateWalletPage, ImportWalletPage)):
                centered_content = ft.Container(
                    content=self.current_page,
                    expand=True,
                    alignment=ft.Alignment(0, 0),
                    padding=20
                )
                self.page.add(centered_content)
            else:
                # For wallet pages, use full layout
                self.page.add(self.current_page)
        else:
            self.show_lock_page()
        self.page.update()

    def show_lock_page(self, title="Welcome to Luna Wallet", subtitle="Access your wallet", show_create=True, wallet_exists=False):
        """Show lock page with appropriate options based on wallet existence"""
        print(f"DEBUG: Showing lock page - title: {title}, show_create: {show_create}, wallet_exists: {wallet_exists}")
        
        # If no wallets exist, force show_create to True to display create/import options
        if not wallet_exists:
            show_create = True
            print("DEBUG: No wallets exist - forcing show_create to True")
        
        lock_page = LockPage(
            self, 
            on_unlock=self.unlock_wallet,
            onCreate_wallet=self.show_create_wallet,
            wallet_exists=wallet_exists,
            title=title,
            subtitle=subtitle,
            show_create_option=show_create
        )
        self.current_lock_page = lock_page
        self.current_page = lock_page.create()
        
        # Clear and add with proper centering
        self.page.controls.clear()
        centered_content = ft.Container(
            content=self.current_page,
            expand=True,
            alignment=ft.Alignment(0, 0),
            padding=20
        )
        self.page.add(centered_content)
        self.page.update()

    def attempt_wallet_load(self):
        """Attempt to load wallet metadata without password to confirm existence"""
        try:
            # Try to load from persistent storage first
            if self.load_wallet_data():
                return True
            
            # Try to see if we can detect wallet structure without unlocking
            if hasattr(self.wallet_core, 'get_wallet_info'):
                info = self.wallet_core.get_wallet_info()
                return info is not None
            
            # Check if we can access any wallet properties that don't require password
            if hasattr(self.wallet_core, 'wallets') and self.wallet_core.wallets:
                return True
                
            return False
        except Exception as e:
            print(f"DEBUG: Wallet load attempt failed: {e}")
            return False

    def unlock_wallet(self, password):
        """Unlock existing wallet with password using LunaWallet core methods"""
        def unlock_thread():
            try:
                print("DEBUG: Starting unlock process...")
                print(f"DEBUG: Password length: {len(password)}")
                
                success = False
                
                # Load wallet data from persistence first
                print("DEBUG: Loading wallet data from file...")
                load_success = self.load_wallet_data()
                print(f"DEBUG: Wallet data load result: {load_success}")
                
                if not load_success:
                    print("DEBUG: Failed to load wallet data")
                    def show_load_error():
                        self.show_snackbar("Failed to load wallet data", "error")
                        if hasattr(self, 'current_lock_page') and self.current_lock_page:
                            self.current_lock_page.hide_loading()
                    self.page.run_thread(show_load_error)
                    return
                
                # Check if we have wallets in the core
                if hasattr(self.wallet_core, 'wallets') and self.wallet_core.wallets:
                    print(f"DEBUG: Found {len(self.wallet_core.wallets)} wallets in core")
                    
                    # Try to unlock each wallet using the core's unlock_wallet method
                    for wallet_address in self.wallet_core.wallets.keys():
                        try:
                            print(f"DEBUG: Attempting to unlock wallet: {wallet_address}")
                            
                            # Use LunaWallet's unlock_wallet method
                            unlock_success = self.wallet_core.unlock_wallet(wallet_address, password)
                            
                            if unlock_success:
                                print(f"DEBUG: SUCCESS! Unlocked wallet: {wallet_address}")
                                
                                # Switch to this wallet to make it current
                                switch_success = self.wallet_core.switch_wallet(wallet_address)
                                if switch_success:
                                    print(f"DEBUG: Successfully switched to wallet: {wallet_address}")
                                else:
                                    print(f"DEBUG: Failed to switch to wallet: {wallet_address}")
                                
                                success = True
                                break
                            else:
                                print(f"DEBUG: Failed to unlock wallet: {wallet_address}")
                                
                        except Exception as wallet_error:
                            print(f"DEBUG: Error unlocking wallet {wallet_address}: {wallet_error}")
                            continue
                
                # Fallback: Try to load from file directly if core methods didn't work
                if not success:
                    print("DEBUG: Core unlock failed, trying load_from_file...")
                    try:
                        if hasattr(self.wallet_core, 'load_from_file'):
                            success = self.wallet_core.load_from_file("wallet_data.json", password)
                            print(f"DEBUG: load_from_file result: {success}")
                    except Exception as load_error:
                        print(f"DEBUG: load_from_file failed: {load_error}")

                print(f"DEBUG: Final unlock result: {success}")
                
                def update_ui():
                    if success:
                        print("DEBUG: Unlock successful - transitioning to wallet page")
                        self.is_locked = False
                        self.last_activity_time = time.time()
                        self.show_snackbar("Wallet unlocked successfully", "success")
                        
                        # Verify the wallet state
                        if hasattr(self.wallet_core, 'is_locked'):
                            print(f"DEBUG: Core is_locked: {self.wallet_core.is_locked}")
                        if hasattr(self.wallet_core, 'private_key') and self.wallet_core.private_key:
                            print("DEBUG: Private key is available in core")
                        if hasattr(self.wallet_core, 'current_wallet_address'):
                            print(f"DEBUG: Current wallet address: {self.wallet_core.current_wallet_address}")
                        
                        # Save wallet state after successful unlock
                        save_success = self.save_wallet_data(force_save=True)
                        if save_success:
                            print("DEBUG: Wallet state saved after unlock")
                        
                        self.show_wallet_page()
                        # Start blockchain sync
                        self.start_blockchain_sync()
                    else:
                        print("DEBUG: Unlock failed - showing error")
                        self.show_snackbar("Failed to unlock wallet - wrong password", "error")
                        if hasattr(self, 'current_lock_page') and self.current_lock_page:
                            self.current_lock_page.hide_loading()
                        # Keep the lock screen visible for retry
                    
                self.page.run_thread(update_ui)
                
            except Exception as e:
                print(f"DEBUG: Unlock error: {e}")
                import traceback
                traceback.print_exc()
                def show_error():
                    self.show_snackbar(f"Unlock error: {str(e)}", "error")
                    if hasattr(self, 'current_lock_page') and self.current_lock_page:
                        self.current_lock_page.hide_loading()
                self.page.run_thread(show_error)
        
        threading.Thread(target=unlock_thread, daemon=True).start()





    def start_blockchain_sync(self):
        """Start blockchain synchronization for all wallets"""
        try:
            print("DEBUG: Starting blockchain sync for all wallets...")
            
            def sync_thread():
                try:
                    self.scan_all_wallets_for_changes(force_full_scan=True)
                    print("DEBUG: Blockchain sync completed for all wallets")
                    
                    # After initial sync, start continuous background monitoring
                    print("DEBUG: Starting continuous background monitoring...")
                    # Use a separate method so it runs in background
                    def start_monitoring():
                        time.sleep(1)  # Small delay to ensure UI is settled
                        self.start_continuous_blockchain_scan()
                    
                    threading.Thread(target=start_monitoring, daemon=True).start()
                    
                except Exception as e:
                    print(f"DEBUG: Blockchain sync error: {e}")
            
            threading.Thread(target=sync_thread, daemon=True).start()
            
        except Exception as e:
            print(f"DEBUG: Error starting blockchain sync: {e}")

    def scan_all_wallets_for_changes(self, force_full_scan=False):
        """
        Scan wallets for transactions.
        - If force_full_scan=True: Do complete blockchain scan from start, cache results, then update all balances
        - Otherwise: Only check for NEW transactions since last scan, update balances when new found
        """
        try:
            if not hasattr(self, 'wallet_core') or not self.wallet_core or not hasattr(self.wallet_core, 'wallets'):
                return
            
            wallet_addresses = list(self.wallet_core.wallets.keys())
            if not wallet_addresses:
                return
            
            # Get latest block height
            latest_block = self.blockchain_manager.get_latest_block()
            if not latest_block:
                return
                
            latest_height = latest_block.get('index', 0)
            
            # If this is the first scan OR force_full_scan is True, do complete blockchain scan
            if self.last_scanned_block == 0 or force_full_scan:
                print(f"DEBUG: Full blockchain scan - scanning from genesis to block {latest_height}")
                self._perform_full_blockchain_scan(wallet_addresses, latest_height)
                self.last_scanned_block = latest_height
                return
            
            # Check what's already cached to avoid redundant scanning
            cached_height = self.blockchain_manager.cache.get_highest_cached_height()
            
            # Determine start height for incremental scan (only new blocks since last scan)
            effective_start_height = max(self.last_scanned_block + 1, cached_height + 1)
            
            # If everything is already cached and scanned, no need to scan
            if effective_start_height > latest_height:
                return  # No new blocks to scan
            
            print(f"DEBUG: Incremental scan - checking blocks {effective_start_height} to {latest_height}")
            self._perform_incremental_scan(wallet_addresses, effective_start_height, latest_height)
            self.last_scanned_block = latest_height
            
        except Exception as e:
            print(f"DEBUG: Error in scan_all_wallets_for_changes: {e}")
            import traceback
            traceback.print_exc()

    def _perform_full_blockchain_scan(self, wallet_addresses, latest_height):
        """Perform complete blockchain scan from genesis using batch API"""
        try:
            print(f"DEBUG: Starting full blockchain scan using batch API (0 to {latest_height})")
            
            # Use new batch method: scan_transactions_for_addresses(addresses: List[str])
            # Returns Dict[str, List[Dict]] where keys are addresses
            if hasattr(self.blockchain_manager, 'scan_transactions_for_addresses'):
                print(f"✓ Using batch scan_transactions_for_addresses() for {len(wallet_addresses)} wallets")
                all_transactions = self.blockchain_manager.scan_transactions_for_addresses(wallet_addresses)
                
                # Process transactions for each wallet
                wallet_txs_count = {addr: {'reward': 0, 'transfer': 0, 'other': 0} for addr in wallet_addresses}
                
                for wallet_addr in wallet_addresses:
                    wallet_addr_lower = wallet_addr.lower()
                    wallet_txs = all_transactions.get(wallet_addr_lower, []) or all_transactions.get(wallet_addr, [])
                    
                    print(f"\n📨 Processing {len(wallet_txs)} transactions for {wallet_addr[:12]}...")
                    
                    for tx in wallet_txs:
                        tx_type = tx.get('type', 'transfer').lower()
                        block_height = tx.get('block_height', 0)
                        
                        # Save transaction with proper status
                        tx['status'] = 'confirmed'
                        if hasattr(self, 'database'):
                            self.database.save_transaction(tx, wallet_addr)
                        
                        # Count by type
                        if tx_type == 'reward':
                            wallet_txs_count[wallet_addr]['reward'] += 1
                            print(f"  ✓ Reward: {tx.get('amount')} LKC @ block {block_height}")
                        elif tx_type == 'fee_distribution':
                            wallet_txs_count[wallet_addr]['other'] += 1
                        else:
                            wallet_txs_count[wallet_addr]['transfer'] += 1
                
                # Print summary
                print(f"\n📊 BLOCKCHAIN SCAN SUMMARY:")
                for wallet_addr in wallet_addresses:
                    counts = wallet_txs_count[wallet_addr]
                    total = counts['reward'] + counts['transfer'] + counts['other']
                    print(f"  {wallet_addr[:12]}...: {counts['reward']} rewards, {counts['transfer']} transfers, {counts['other']} other = {total} total")
            else:
                # Fallback to legacy single-address method
                print(f"⚠ Batch scan not available, falling back to single-address scan")
                for wallet_addr in wallet_addresses:
                    txs = self.blockchain_manager.scan_transactions_for_address(wallet_addr)
                    print(f"  {wallet_addr[:12]}...: {len(txs)} transactions")
                    for tx in txs:
                        tx['status'] = 'confirmed'
                        if hasattr(self, 'database'):
                            self.database.save_transaction(tx, wallet_addr)
            
            # Check mempool for ALL pending transactions at once
            self._check_mempool_for_pending(wallet_addresses)
            
            # Detect new incoming transactions and play sound
            self._detect_new_incoming_transactions(wallet_addresses)
            
            # Update ALL wallet balances at once
            self._update_all_wallet_balances(wallet_addresses)
            
            # Refresh UI after full scan complete
            self._refresh_ui_after_scan(force_update=True)
            
        except Exception as e:
            print(f"DEBUG: Error in _perform_full_blockchain_scan: {e}")
            import traceback
            traceback.print_exc()

    def _scan_all_rewards_iteratively(self, wallet_addresses, max_iterations=5):
        """
        Iteratively scan for ALL reward transactions for all wallets.
        Handles case where cache has 100+ rewards but only returns 100 at a time.
        
        Args:
            wallet_addresses: List of wallet addresses to scan
            max_iterations: Maximum number of scan iterations per wallet
        """
        try:
            for wallet_addr in wallet_addresses:
                wallet_addr_lower = wallet_addr.lower()
                iteration = 0
                total_found = 0
                last_height = None
                
                print(f"\n🔄 Iterative scan for {wallet_addr[:12]}...")
                
                while iteration < max_iterations:
                    iteration += 1
                    
                    # Scan for this wallet's rewards
                    try:
                        # Use the enhanced scanner if available
                        if hasattr(self.blockchain_manager, 'scan_transactions_for_address'):
                            txs = self.blockchain_manager.scan_transactions_for_address(wallet_addr)
                        else:
                            txs = []
                        
                        # Filter for just reward transactions
                        reward_txs = [tx for tx in txs if tx.get('type', '').lower() == 'reward']
                        
                        if not reward_txs:
                            print(f"  Iteration {iteration}: No new rewards found, stopping scan")
                            break
                        
                        print(f"  Iteration {iteration}: Found {len(reward_txs)} reward transactions")
                        
                        # Process each reward
                        current_height_min = float('inf')
                        for tx in reward_txs:
                            block_height = tx.get('block_height', 0)
                            if block_height < current_height_min:
                                current_height_min = block_height
                            
                            # Save to database if not already saved
                            tx['status'] = 'confirmed'
                            if hasattr(self, 'database'):
                                self.database.save_transaction(tx, wallet_addr)
                            total_found += 1
                        
                        # If we got the same height range, we've found all rewards
                        if last_height is not None and current_height_min == last_height:
                            print(f"  Iteration {iteration}: Same height range as previous, all rewards found")
                            break
                        
                        last_height = current_height_min
                        
                    except Exception as e:
                        print(f"  Iteration {iteration}: Error during scan: {e}")
                        break
                
                print(f"  ✅ Total rewards found for {wallet_addr[:12]}...: {total_found}")
                
        except Exception as e:
            print(f"ERROR in _scan_all_rewards_iteratively: {e}")
            import traceback
            traceback.print_exc()

    def _perform_incremental_scan(self, wallet_addresses, start_height, latest_height):
        """Perform incremental scan for only NEW transactions since last scan using batch API"""
        try:
            print(f"DEBUG: Incremental scan from block {start_height} to {latest_height}")
            new_transactions_found = False
            
            wallet_txs_count = {addr: {'reward': 0, 'transfer': 0, 'other': 0} for addr in wallet_addresses}
            
            # Use new batch method to scan all wallets at once
            if hasattr(self.blockchain_manager, 'scan_transactions_for_addresses'):
                print(f"✓ Using batch scan_transactions_for_addresses() for new blocks {start_height}-{latest_height}")
                all_transactions = self.blockchain_manager.scan_transactions_for_addresses(
                    wallet_addresses, 
                    start_height=start_height, 
                    end_height=latest_height
                )
                
                for wallet_addr in wallet_addresses:
                    wallet_addr_lower = wallet_addr.lower()
                    wallet_txs = all_transactions.get(wallet_addr_lower, []) or all_transactions.get(wallet_addr, [])
                    
                    if wallet_txs:
                        new_transactions_found = True
                        print(f"\n📨 Processing {len(wallet_txs)} transactions for {wallet_addr[:12]}...")
                        
                        for tx in wallet_txs:
                            tx_type = tx.get('type', 'transfer').lower()
                            block_height = tx.get('block_height', 0)
                            
                            # Save transaction with proper status
                            tx['status'] = 'confirmed'
                            if hasattr(self, 'database'):
                                self.database.save_transaction(tx, wallet_addr)
                            
                            # Count by type
                            if tx_type == 'reward':
                                wallet_txs_count[wallet_addr]['reward'] += 1
                                print(f"  🎁 Reward: {tx.get('amount')} LKC @ block {block_height}")
                            elif tx_type == 'fee_distribution':
                                wallet_txs_count[wallet_addr]['other'] += 1
                            else:
                                wallet_txs_count[wallet_addr]['transfer'] += 1
                                print(f"  Found transaction in block {block_height} for {wallet_addr[:12]}...")
            else:
                # Fallback to legacy single-address method (shouldn't happen with 1.5.1)
                print(f"⚠ Batch scan not available, falling back to legacy method")
                for wallet_addr in wallet_addresses:
                    txs = self.blockchain_manager.scan_transactions_for_address(wallet_addr)
                    relevant_txs = [tx for tx in txs if start_height <= tx.get('block_height', 0) <= latest_height]
                    
                    if relevant_txs:
                        new_transactions_found = True
                        for tx in relevant_txs:
                            tx['status'] = 'confirmed'
                            if hasattr(self, 'database'):
                                self.database.save_transaction(tx, wallet_addr)
                            tx_type = tx.get('type', 'transfer').lower()
                            if tx_type == 'reward':
                                wallet_txs_count[wallet_addr]['reward'] += 1
                            else:
                                wallet_txs_count[wallet_addr]['transfer'] += 1
            
            # Print summary
            if new_transactions_found:
                print(f"\n📊 INCREMENTAL SCAN SUMMARY:")
                for wallet_addr in wallet_addresses:
                    counts = wallet_txs_count[wallet_addr]
                    total = counts['reward'] + counts['transfer'] + counts['other']
                    if total > 0:
                        print(f"  {wallet_addr[:12]}...: {counts['reward']} rewards, {counts['transfer']} transfers, {counts['other']} other")
            
            # Check mempool for pending transactions
            self._check_mempool_for_pending(wallet_addresses)
            
            # Detect new incoming transactions and play sound
            self._detect_new_incoming_transactions(wallet_addresses)
            
            # Only update UI and balances if new transactions were found
            if new_transactions_found:
                self._update_all_wallet_balances(wallet_addresses)
                self._refresh_ui_after_scan(force_update=True)
                self.show_snackbar("New transactions detected!", "success")
            
        except Exception as e:
            print(f"DEBUG: Error in _perform_incremental_scan: {e}")
            import traceback
            traceback.print_exc()

    def _check_mempool_for_pending(self, wallet_addresses):
        """Check mempool for pending transactions using batch API"""
        try:
            from lunalib.core.mempool import MempoolManager
            mempool_manager = MempoolManager()
            
            print(f"\n=== CHECKING MEMPOOL FOR {len(wallet_addresses)} WALLETS ===")
            
            # Use new batch method: get_pending_transactions_for_addresses(addresses: List[str])
            # Returns Dict[str, List[Dict]] where keys are addresses
            if hasattr(mempool_manager, 'get_pending_transactions_for_addresses'):
                print(f"✓ Using batch get_pending_transactions_for_addresses()")
                all_pending = mempool_manager.get_pending_transactions_for_addresses(wallet_addresses, fetch_remote=True)
                
                for wallet_addr in wallet_addresses:
                    wallet_addr_lower = wallet_addr.lower()
                    pending_txs = all_pending.get(wallet_addr_lower, []) or all_pending.get(wallet_addr, [])
                    
                    if pending_txs:
                        print(f"✓ Found {len(pending_txs)} pending transactions for {wallet_addr[:12]}...")
                        for i, tx in enumerate(pending_txs):
                            tx_hash = tx.get('hash', 'unknown')
                            tx_from = tx.get('from', 'unknown')
                            tx_to = tx.get('to', 'unknown')
                            tx_amount = tx.get('amount', 0)
                            print(f"  [{i+1}] hash={tx_hash[:8] if isinstance(tx_hash, str) else tx_hash}...")
                            print(f"      from={tx_from[:8] if isinstance(tx_from, str) else tx_from}... → to={tx_to[:8] if isinstance(tx_to, str) else tx_to}...")
                            print(f"      amount={tx_amount}")
                            
                            # Mark as pending and save to database
                            tx['status'] = 'pending'
                            if hasattr(self, 'database'):
                                self.database.save_pending_transaction(tx, wallet_addr)
                                print(f"      Saved to database")
                    else:
                        print(f"✓ No pending transactions for {wallet_addr[:12]}...")
            else:
                # Fallback to single-address method
                print(f"⚠ Batch mempool not available, falling back to single-address method")
                for wallet_addr in wallet_addresses:
                    try:
                        pending_txs = mempool_manager.get_pending_transactions(wallet_addr)
                        
                        if pending_txs:
                            print(f"✓ Found {len(pending_txs)} pending transactions for {wallet_addr[:12]}...")
                            for i, tx in enumerate(pending_txs):
                                tx_hash = tx.get('hash', 'unknown')
                                tx_from = tx.get('from', 'unknown')
                                tx_to = tx.get('to', 'unknown')
                                tx_amount = tx.get('amount', 0)
                                print(f"  [{i+1}] hash={tx_hash[:8] if isinstance(tx_hash, str) else tx_hash}...")
                                print(f"      from={tx_from[:8] if isinstance(tx_from, str) else tx_from}... → to={tx_to[:8] if isinstance(tx_to, str) else tx_to}...")
                                print(f"      amount={tx_amount}")
                                
                                # Mark as pending and save to database
                                tx['status'] = 'pending'
                                if hasattr(self, 'database'):
                                    self.database.save_pending_transaction(tx, wallet_addr)
                                    print(f"      Saved to database")
                        else:
                            print(f"✓ No pending transactions for {wallet_addr[:12]}...")
                            
                    except Exception as e:
                        print(f"✗ Mempool check error for {wallet_addr[:12]}...: {e}")
                        import traceback
                        traceback.print_exc()
            
            print(f"=== MEMPOOL CHECK COMPLETE ===\n")
                    
        except Exception as e:
            print(f"✗ Mempool check failed: {e}")
            import traceback
            traceback.print_exc()

    def _detect_new_incoming_transactions(self, wallet_addresses):
        """
        Detect NEW incoming transactions that haven't been seen before.
        Mark existing transactions as 'old' so we don't replay sound on rescan.
        Play sound for new incoming transactions.
        """
        try:
            print(f"\n=== DETECTING NEW TRANSACTIONS ===")
            
            if not hasattr(self, 'database'):
                return
            
            # Get all transactions from database
            try:
                all_txs = self.database.get_all_transactions()
            except:
                all_txs = []
            
            if not all_txs:
                print("No transactions in database")
                return
            
            # Process each wallet
            for wallet_addr in wallet_addresses:
                wallet_addr_lower = wallet_addr.lower()
                
                # Find transactions for this wallet
                wallet_txs = [tx for tx in all_txs if 
                             (tx.get('to', '').lower() == wallet_addr_lower or 
                              tx.get('reward_address', '').lower() == wallet_addr_lower or
                              tx.get('recipient', '').lower() == wallet_addr_lower)]
                
                print(f"\n  Checking {len(wallet_txs)} transactions for {wallet_addr[:12]}...")
                
                for tx in wallet_txs:
                    # Mark existing transactions as 'old'
                    if not tx.get('tx_age'):
                        # This is a NEW transaction (first time seeing it)
                        tx['tx_age'] = 'new'
                        
                        # Check if it's an incoming transaction
                        is_incoming = (tx.get('to', '').lower() == wallet_addr_lower or
                                      tx.get('reward_address', '').lower() == wallet_addr_lower or
                                      tx.get('recipient', '').lower() == wallet_addr_lower)
                        
                        tx_type = tx.get('type', 'transfer').lower()
                        amount = tx.get('amount', 0)
                        
                        if is_incoming:
                            print(f"    ✨ NEW incoming {tx_type}: {amount} LKC")
                            # Play sound for new incoming transaction
                            self._play_transaction_sound()
                        else:
                            tx['tx_age'] = 'old'  # Mark outgoing as old
                    else:
                        # Mark as old so sound doesn't replay on rescan
                        tx['tx_age'] = 'old'
            
            print(f"=== NEW TRANSACTION DETECTION COMPLETE ===\n")
            
        except Exception as e:
            print(f"Error detecting new transactions: {e}")
            import traceback
            traceback.print_exc()
    
    def _play_transaction_sound(self):
        """Play transaction notification sound"""
        try:
            import os
            sound_file = os.path.join(os.path.dirname(__file__), 'assets', 'sounds', 'transaction.wav')
            
            if os.path.exists(sound_file):
                print(f"Playing transaction sound: {sound_file}")
                # Try to play using platform-specific methods
                try:
                    import platform
                    system = platform.system()
                    
                    if system == 'Windows':
                        import winsound
                        winsound.PlaySound(sound_file, winsound.SND_FILENAME)
                    elif system == 'Darwin':  # macOS
                        os.system(f'afplay "{sound_file}"')
                    elif system == 'Linux':
                        os.system(f'paplay "{sound_file}"')
                except Exception as play_error:
                    print(f"Could not play sound with platform method: {play_error}")
                    # Fallback: try with pygame if available
                    try:
                        import pygame
                        pygame.mixer.init()
                        pygame.mixer.music.load(sound_file)
                        pygame.mixer.music.play()
                    except:
                        print("Could not play sound with pygame either")
            else:
                print(f"Sound file not found: {sound_file}")
        except Exception as e:
            print(f"Error playing sound: {e}")

    def _update_all_wallet_balances(self, wallet_addresses):
        """Update balances for all wallets using unified calculation"""
        try:
            from lunalib.core.mempool import MempoolManager
            mempool_manager = MempoolManager()
        except:
            mempool_manager = None
        
        print(f"\n=== UPDATING BALANCES FOR {len(wallet_addresses)} WALLETS ===")
        print(f"Database available: {hasattr(self, 'database')}")
        
        if hasattr(self, 'database'):
            try:
                all_txs = self.database.get_all_transactions()
                print(f"Database has {len(all_txs) if all_txs else 0} total transactions")
            except Exception as e:
                print(f"ERROR getting transactions from database: {e}")
        
        for wallet_addr in wallet_addresses:
            if wallet_addr in self.wallet_core.wallets:
                wallet_obj = self.wallet_core.wallets[wallet_addr]
                
                try:
                    balances = calculate_wallet_balances(
                        wallet_addr,
                        database=self.database if hasattr(self, 'database') else None,
                        mempool_manager=mempool_manager
                    )
                    
                    # Store in wallet_core.wallets
                    wallet_obj['confirmed_balance'] = balances['available']
                    wallet_obj['available_balance'] = balances['available']
                    wallet_obj['pending_balance'] = balances['pending']
                    wallet_obj['balance'] = balances['total']
                    
                    print(f"✓ {wallet_addr[:12]}...")
                    print(f"  available={balances['available']:.6f}, pending={balances['pending']:.6f}, total={balances['total']:.6f}")
                    print(f"  wallet_core.wallets[addr]['balance'] = {wallet_obj['balance']:.6f}")
                    
                except Exception as e:
                    print(f"✗ Error calculating balance for {wallet_addr[:12]}...: {e}")
                    import traceback
                    traceback.print_exc()
        
        print(f"=== BALANCE UPDATE COMPLETE ===\n")

    def _refresh_ui_after_scan(self, force_update=False):
        """Refresh UI after scan - must be called from scanning thread, schedules on main thread"""
        if not hasattr(self, 'page') or not self.page:
            return
        
        print(f"\n=== SCHEDULING UI REFRESH (from scan) ===")
        
        def update_ui():
            try:
                print(f">>> UI REFRESH STARTING (on main thread)")
                
                if hasattr(self, 'wallet_page') and self.wallet_page:
                    print(f">>> Refreshing sidebar...")
                    if hasattr(self.wallet_page, '_refresh_sidebar_wallets'):
                        self.wallet_page._refresh_sidebar_wallets()
                    
                    print(f">>> Recalculating balance from all transactions...")
                    if hasattr(self.wallet_page, 'recalculate_wallet_balances'):
                        if hasattr(self.wallet_core, 'current_wallet_address'):
                            self.wallet_page.recalculate_wallet_balances(self.wallet_core.current_wallet_address)
                    
                    print(f">>> Updating balance card...")
                    if hasattr(self.wallet_page, '_update_wallet_data_ui_only'):
                        self.wallet_page._update_wallet_data_ui_only()
                
                print(f">>> Updating transaction history...")
                self.update_balance_display()
                self.update_transaction_history()
                
                print(f">>> Calling page.update()...")
                self.page.update()
                
                print(f">>> UI REFRESH COMPLETE\n")
                
            except Exception as e:
                print(f"ERROR in UI refresh: {e}")
                import traceback
                traceback.print_exc()
        
        # Schedule UI update on main thread using run_thread (not run_task which expects async)
        self.page.run_thread(update_ui)
            
        # Save wallet data
        self.save_wallet_data(force_save=True)

    def start_continuous_blockchain_scan(self):
        """Start continuous blockchain scanning for all wallets in background"""
        if self.continuous_scan_active:
            print("DEBUG: Continuous scan already active")
            return
        
        self.continuous_scan_active = True
        print("DEBUG: Starting continuous blockchain scan (every 30 seconds)")
        
        def continuous_scan_loop():
            while self.continuous_scan_active and not self.is_locked:
                try:
                    current_time = time.time()
                    
                    # Scan all wallets for new transactions
                    self.scan_all_wallets_for_changes()
                    
                    # Sleep for scan interval
                    time.sleep(self.scan_interval)
                    
                except Exception as e:
                    print(f"DEBUG: Continuous scan error: {e}")
                    time.sleep(self.scan_interval)
        
        threading.Thread(target=continuous_scan_loop, daemon=True).start()

    def update_wallet_data(self):
        """Update wallet balance and transaction data"""
        try:
            print("DEBUG: Updating wallet data...")
            
            if not hasattr(self, 'wallet_core') or not self.wallet_core:
                print("DEBUG: No wallet core available")
                return
            
            # Get current wallet address
            if hasattr(self.wallet_core, 'current_wallet_address') and self.wallet_core.current_wallet_address:
                address = self.wallet_core.current_wallet_address
                print(f"DEBUG: Updating data for address: {address}")
                
                # Scan for transactions
                try:
                    transactions = self.blockchain_manager.scan_transactions_for_address(address)
                    print(f"DEBUG: Found {len(transactions)} transactions")
                    
                    # Update wallet balance
                    if hasattr(self.wallet_core, 'update_balance'):
                        self.wallet_core.update_balance()
                    
                    # Trigger UI update if wallet page is active
                    if hasattr(self, 'current_page') and self.current_page:
                        self.page.update()
                        
                except Exception as scan_error:
                    print(f"DEBUG: Transaction scan error: {scan_error}")
            else:
                print("DEBUG: No current wallet address")
                
        except Exception as e:
            print(f"DEBUG: Error updating wallet data: {e}")

    # Add this method to LunaWalletApp class
    def create_enhanced_blockchain_scanner(self):
        """Create an enhanced blockchain scanner that properly detects outgoing transactions"""
        
        # Monkey patch the blockchain manager's scan method
        original_scan = self.blockchain_manager.scan_transactions_for_address
        
        def enhanced_scan(address: str, start_height: int = 0, end_height: int = None) -> List[Dict]:
            """Enhanced scan that properly finds both incoming and outgoing transactions"""
            try:
                print(f"\n🚀 ENHANCED SCAN for {address}")
                print("=" * 60)
                
                # First get the original scan results
                original_txs = original_scan(address, start_height, end_height)
                print(f"Original scan found: {len(original_txs)} transactions")
                
                # Now do a direct query to get all transactions
                all_txs = []
                
                # Method 1: Try direct API endpoint for transactions
                try:
                    response = requests.get(
                        f"https://bank.linglin.art/transactions/address/{address}",
                        timeout=30
                    )
                    if response.status_code == 200:
                        api_txs = response.json()
                        if isinstance(api_txs, list):
                            all_txs.extend(api_txs)
                            print(f"Direct API found: {len(api_txs)} transactions")
                except:
                    pass
                
                # Method 2: Get blocks and scan manually
                if len(all_txs) == 0:
                    print("No direct API results, scanning blocks manually...")
                    
                    # Get blockchain height
                    latest_block = self.blockchain_manager.get_latest_block()
                    if latest_block:
                        latest_height = latest_block.get('index', 0)
                        print(f"Latest block: #{latest_height}")
                        
                        # Scan recent blocks (last 1000)
                        start = max(0, latest_height - 1000)
                        for height in range(start, latest_height + 1):
                            block = self.blockchain_manager.get_block(height)
                            if block:
                                txs = self.enhanced_find_txs_in_block(block, address)
                                all_txs.extend(txs)
                
                # Process all transactions to add direction info
                processed_txs = []
                for tx in all_txs:
                    processed_tx = self.process_transaction_direction(tx, address)
                    if processed_tx:
                        processed_txs.append(processed_tx)
                
                # Merge with original results
                seen_hashes = set()
                final_txs = []
                
                # Add enhanced results first
                for tx in processed_txs:
                    tx_hash = tx.get('hash')
                    if tx_hash and tx_hash not in seen_hashes:
                        seen_hashes.add(tx_hash)
                        final_txs.append(tx)
                
                # Add any unique original results
                for tx in original_txs:
                    tx_hash = tx.get('hash')
                    if tx_hash and tx_hash not in seen_hashes:
                        seen_hashes.add(tx_hash)
                        final_txs.append(tx)
                
                # Count statistics
                incoming = len([t for t in final_txs if t.get('direction') == 'incoming'])
                outgoing = len([t for t in final_txs if t.get('direction') == 'outgoing'])
                
                print(f"\n📊 FINAL RESULTS:")
                print(f"   Total: {len(final_txs)} transactions")
                print(f"   Incoming: {incoming}")
                print(f"   Outgoing: {outgoing}")
                
                # Debug: Show outgoing transactions
                if outgoing > 0:
                    print(f"\n🔍 OUTGOING TRANSACTIONS:")
                    for tx in final_txs:
                        if tx.get('direction') == 'outgoing':
                            print(f"  - From: {tx.get('from')} → To: {tx.get('to')}")
                            print(f"    Amount: {tx.get('amount')} + Fee: {tx.get('fee', 0)}")
                            print(f"    Hash: {tx.get('hash', '')[:16]}...")
                
                return final_txs
                
            except Exception as e:
                print(f"Enhanced scan error: {e}")
                import traceback
                traceback.print_exc()
                return original_scan(address, start_height, end_height)
        
        # Apply the patch
        self.blockchain_manager.scan_transactions_for_address = enhanced_scan
        print("[OK] Enhanced blockchain scanner activated")
        
        return enhanced_scan

    def enhanced_find_txs_in_block(self, block: Dict, address: str) -> List[Dict]:
        """Enhanced block scanning for transactions - FIXED FOR OUTGOING"""
        transactions = []
        address_lower = address.lower()
        
        block_transactions = block.get('transactions', [])
        
        for tx in block_transactions:
            # Get sender and receiver addresses
            from_addr = (tx.get('from', '') or '').lower()
            to_addr = (tx.get('to', '') or '').lower()
            
            # Skip if neither address matches
            if address_lower not in [from_addr, to_addr]:
                continue
            
            enhanced_tx = tx.copy()
            enhanced_tx['block_height'] = block.get('index')
            enhanced_tx['status'] = 'confirmed'
            
            # Determine direction
            if from_addr == address_lower:
                # THIS IS OUR OUTGOING TRANSACTION
                enhanced_tx['direction'] = 'outgoing'
                enhanced_tx['from'] = from_addr
                enhanced_tx['to'] = to_addr
                
                # Get amount and fee
                amount = float(tx.get('amount', 0))
                fee = float(tx.get('fee', 0))
                enhanced_tx['amount'] = amount
                enhanced_tx['fee'] = fee
                enhanced_tx['effective_amount'] = -(amount + fee)  # Negative for outgoing
                
                print(f"[OK] FOUND OUTGOING in block #{block.get('index')}:")
                print(f"   From: {from_addr} (OURS)")
                print(f"   To: {to_addr}")
                print(f"   Amount: {amount}")
                print(f"   Fee: {fee}")
                print(f"   Total Deducted: {amount + fee}")
                
            elif to_addr == address_lower:
                # This is incoming
                enhanced_tx['direction'] = 'incoming'
                enhanced_tx['from'] = from_addr
                enhanced_tx['to'] = to_addr
                enhanced_tx['amount'] = float(tx.get('amount', 0))
                enhanced_tx['effective_amount'] = float(tx.get('amount', 0))
                print(f"⬆️ Found INCOMING in block #{block.get('index')}: {tx.get('amount')} LKC")
            
            transactions.append(enhanced_tx)
        
        return transactions

    def process_transaction_direction(self, tx: Dict, address: str) -> Dict:
        """Process transaction to add direction information"""
        address_lower = address.lower()
        
        enhanced_tx = tx.copy()
        
        # Check if we're the sender
        possible_from_fields = ['from', 'sender', 'from_address', 'source', 'payer']
        for field in possible_from_fields:
            if field in tx:
                field_value = tx.get(field, '')
                if isinstance(field_value, str) and field_value.lower() == address_lower:
                    enhanced_tx['direction'] = 'outgoing'
                    enhanced_tx['from'] = field_value
                    # Get amount and fee
                    amount = float(tx.get('amount', 0))
                    fee = float(tx.get('fee', 0))
                    enhanced_tx['effective_amount'] = -(amount + fee)
                    return enhanced_tx
        
        # Check if we're the receiver
        possible_to_fields = ['to', 'receiver', 'to_address', 'destination', 'payee']
        for field in possible_to_fields:
            if field in tx:
                field_value = tx.get(field, '')
                if isinstance(field_value, str) and field_value.lower() == address_lower:
                    enhanced_tx['direction'] = 'incoming'
                    enhanced_tx['to'] = field_value
                    enhanced_tx['effective_amount'] = float(tx.get('amount', 0))
                    return enhanced_tx
        
        # If we can't determine direction, add unknown
        enhanced_tx['direction'] = 'unknown'
        return enhanced_tx
    # Add this method to your LunaWalletApp class
    def debug_blockchain_data(self):
        """Debug method to understand blockchain transaction formats"""
        try:
            import requests
            
            if not self.wallet_core.current_wallet_address:
                print("❌ No wallet address available for debug")
                return
                
            address = self.wallet_core.current_wallet_address
            print(f"\n🔍 DEBUG: Checking blockchain data for {address}")
            
            # Try different endpoints
            endpoints = [
                f"https://bank.linglin.art/transactions/address/{address}",
                f"https://bank.linglin.art/blockchain/transactions/{address}",
                "https://bank.linglin.art/blockchain/blocks",
            ]
            
            for endpoint in endpoints:
                print(f"\n--- Testing: {endpoint} ---")
                try:
                    response = requests.get(endpoint, timeout=10)
                    print(f"Status: {response.status_code}")
                    if response.status_code == 200:
                        data = response.json()
                        print(f"Response type: {type(data)}")
                        
                        if isinstance(data, list):
                            print(f"Found {len(data)} items")
                            if len(data) > 0:
                                print("First item structure:")
                                for key, value in list(data[0].items())[:10]:  # Show first 10 keys
                                    print(f"  {key}: {value}")
                        elif isinstance(data, dict):
                            print("Dict keys:", list(data.keys()))
                            if 'transactions' in data:
                                txs = data['transactions']
                                print(f"Found {len(txs)} transactions")
                                if txs and len(txs) > 0:
                                    print("Sample transaction:")
                                    for key, value in list(txs[0].items())[:10]:
                                        print(f"  {key}: {value}")
                    else:
                        print(f"Response: {response.text[:200]}")
                except Exception as e:
                    print(f"Error: {e}")
                    
        except Exception as e:
            print(f"Debug error: {e}")
    def _patch_blockchain_scanner(self):
        """Patch the blockchain manager's scanner to properly detect outgoing transactions"""
        # Store original method
        original_scan = self.blockchain_manager.scan_transactions_for_address
        
        def enhanced_scan(address: str, start_height: int = 0, end_height: int = None) -> List[Dict]:
            """Enhanced scanner that properly finds BOTH incoming AND outgoing transactions"""
            try:
                print(f"\n🎯 ENHANCED SCAN for address: {address}")
                print("=" * 60)
                
                # Get original results first
                original_txs = original_scan(address, start_height, end_height)
                print(f"Original scan found: {len(original_txs)} transactions")
                
                # Get all blocks and scan manually
                if end_height is None:
                    end_height = self.blockchain_manager.get_blockchain_height()
                
                print(f"Scanning from block {start_height} to {end_height}")
                
                all_transactions = []
                address_lower = address.lower()
                
                # Use batch block fetching for better performance
                batch_size = 50  # Fetch blocks in batches of 50
                
                for batch_start in range(start_height, end_height + 1, batch_size):
                    batch_end = min(batch_start + batch_size - 1, end_height)
                    
                    try:
                        # Fetch blocks in batch
                        blocks = self.blockchain_manager.get_blocks_range(batch_start, batch_end)
                        print(f"DEBUG: Enhanced scan fetched batch of {len(blocks)} blocks ({batch_start}-{batch_end})")
                        
                        for block in blocks:
                            height = block.get('index', 0)
                            block_txs = block.get('transactions', [])
                            
                            # Check each transaction in the block
                            for tx in block_txs:
                                # Get addresses from transaction
                                from_addr = tx.get('from', '').lower()
                                to_addr = tx.get('to', '').lower()
                                
                                # Check if this transaction involves our address
                                is_our_tx = False
                                direction = None
                                
                                # OUTGOING: Our address is the sender
                                if from_addr == address_lower:
                                    is_our_tx = True
                                    direction = 'outgoing'
                                    print(f"[OK] FOUND OUTGOING TX in block {height}:")
                                    print(f"   From: {from_addr} (OURS)")
                                    print(f"   To: {to_addr}")
                                    print(f"   Amount: {tx.get('amount')}")
                                    print(f"   Hash: {tx.get('hash', '')[:16]}...")
                                
                                # INCOMING: Our address is the receiver
                                elif to_addr == address_lower:
                                    is_our_tx = True
                                    direction = 'incoming'
                                    print(f"[OK] FOUND INCOMING TX in block {height}:")
                                    print(f"   From: {from_addr}")
                                    print(f"   To: {to_addr} (OURS)")
                                    print(f"   Amount: {tx.get('amount')}")
                                    print(f"   Hash: {tx.get('hash', '')[:16]}...")
                                
                                if is_our_tx:
                                    # Create enhanced transaction with direction info
                                    enhanced_tx = tx.copy()
                                    enhanced_tx['block_height'] = height
                                    enhanced_tx['status'] = 'confirmed'
                                    enhanced_tx['direction'] = direction
                                    
                                    # Calculate effective amount
                                    amount = float(tx.get('amount', 0))
                                    fee = float(tx.get('fee', 0))
                                    
                                    if direction == 'outgoing':
                                        # Outgoing: negative amount (amount + fee)
                                        enhanced_tx['effective_amount'] = -(amount + fee)
                                        print(f"   Effective amount: -{amount + fee} ({amount} + {fee} fee)")
                                    else:
                                        # Incoming: positive amount
                                        enhanced_tx['effective_amount'] = amount
                                        print(f"   Effective amount: +{amount}")
                                    
                                    all_transactions.append(enhanced_tx)
                    
                    except Exception as e:
                        print(f"DEBUG: Error scanning batch {batch_start}-{batch_end}: {e}")
                        continue
                
                print(f"\n📊 ENHANCED SCAN RESULTS:")
                print(f"   Total transactions found: {len(all_transactions)}")
                
                incoming_count = len([t for t in all_transactions if t.get('direction') == 'incoming'])
                outgoing_count = len([t for t in all_transactions if t.get('direction') == 'outgoing'])
                
                print(f"   Incoming: {incoming_count}")
                print(f"   Outgoing: {outgoing_count}")
                
                # Show outgoing transaction details
                if outgoing_count > 0:
                    print(f"\n🔍 OUTGOING TRANSACTIONS DETAILS:")
                    for tx in all_transactions:
                        if tx.get('direction') == 'outgoing':
                            print(f"  - Block: {tx.get('block_height')}")
                            print(f"    From: {tx.get('from')}")
                            print(f"    To: {tx.get('to')}")
                            print(f"    Amount: {tx.get('amount')}")
                            print(f"    Fee: {tx.get('fee', 0)}")
                            print(f"    Total: {float(tx.get('amount', 0)) + float(tx.get('fee', 0))}")
                            print(f"    Hash: {tx.get('hash', '')[:16]}...")
                
                return all_transactions
                
            except Exception as e:
                print(f"❌ Enhanced scan error: {e}")
                import traceback
                traceback.print_exc()
                return original_scan(address, start_height, end_height)
        
        # Apply the patch
        self.blockchain_manager.scan_transactions_for_address = enhanced_scan
        print("[OK] Blockchain scanner patched with proper outgoing detection")
    def start_blockchain_sync(self):
        """Start blockchain synchronization - FIXED BALANCE CALCULATION"""
        def sync_thread():
            try:
                print("\n" + "="*60)
                print("[START] STARTING BLOCKCHAIN SYNC")
                print("="*60)
                
                if not self.wallet_core.current_wallet_address:
                    self.page.run_thread(lambda: self.show_snackbar("No wallet selected", "error"))
                    return
                
                address = self.wallet_core.current_wallet_address
                print(f"[SYNC] Syncing address: {address}")
                
                # Use the patched scanner
                transactions = self.blockchain_manager.scan_transactions_for_address(address)
                
                print(f"\n[SUMMARY] TRANSACTION SUMMARY:")
                print(f"   Found: {len(transactions)} total transactions")
                
                if not transactions:
                    print("[WARN] No transactions found")
                    self.page.run_thread(lambda: self.show_snackbar("No transactions found", "warning"))
                    return
                
                # Initialize counters
                total_incoming = 0.0
                total_outgoing = 0.0
                incoming_txs = []
                outgoing_txs = []
                
                # Process each transaction
                for tx in transactions:
                    direction = tx.get('direction', 'unknown')
                    amount = float(tx.get('amount', 0))
                    fee = float(tx.get('fee', 0))
                    
                    if direction == 'incoming':
                        total_incoming += amount
                        incoming_txs.append(tx)
                        print(f"   + Incoming: {amount} LKC (from {tx.get('from', 'unknown')})")
                    elif direction == 'outgoing':
                        # For outgoing, include both amount AND fee
                        total_outgoing += (amount + fee)
                        outgoing_txs.append(tx)
                        print(f"   - Outgoing: {amount} LKC + {fee} fee = {amount + fee} LKC (to {tx.get('to', 'unknown')})")
                
                # Calculate CORRECT balance
                balance = total_incoming - total_outgoing
                
                print(f"\n[BALANCE] BALANCE CALCULATION:")
                print(f"   Total Incoming: {total_incoming:.6f} LKC")
                print(f"   Total Outgoing: {total_outgoing:.6f} LKC")
                print(f"   Current Balance: {balance:.6f} LKC")
                
                print(f"\n[COUNT] TRANSACTION COUNT:")
                print(f"   Incoming: {len(incoming_txs)} transactions")
                print(f"   Outgoing: {len(outgoing_txs)} transactions")
                
                # Show all outgoing transactions for debugging
                if outgoing_txs:
                    print(f"\n[DEBUG] ALL OUTGOING TRANSACTIONS:")
                    for i, tx in enumerate(outgoing_txs, 1):
                        print(f"   {i}. Block: {tx.get('block_height')}")
                        print(f"      Hash: {tx.get('hash', 'unknown')}")
                        print(f"      To: {tx.get('to', 'unknown')}")
                        print(f"      Amount: {tx.get('amount')} + Fee: {tx.get('fee', 0)} = Total: {float(tx.get('amount', 0)) + float(tx.get('fee', 0))}")
                
                # Update wallet core with correct balance
                self.wallet_core.update_balance(balance)
                
                # Update database
                for tx in transactions:
                    self.database.save_transaction(tx, address)
                
                def update_ui():
                    self.update_wallet_data()
                    self.update_balance_display()
                    self.update_transaction_history()
                    
                    message = f"Sync: {len(incoming_txs)} in, {len(outgoing_txs)} out, Balance: {balance:.6f} LKC"
                    self.show_snackbar(message, "success")
                    
                    # Save wallet after sync
                    self.save_wallet_data(force_save=True)
                    self.create_backup()
                    
                self.page.run_thread(update_ui)
                
            except Exception as e:
                print(f"[ERROR] Sync error: {e}")
                import traceback
                traceback.print_exc()
                
                def show_error():
                    self.show_snackbar(f"Sync error: {str(e)[:50]}...", "error")
                
                self.page.run_thread(show_error)
        
        threading.Thread(target=sync_thread, daemon=True).start()
    def _fallback_sync(self):
        """Fallback sync method using direct blockchain scanning"""
        try:
            print("DEBUG: Starting fallback sync...")
            if self.wallet_core.current_wallet_address:
                # Use the direct scan method as backup
                transactions = self.blockchain_manager.scan_transactions_for_address(
                    self.wallet_core.current_wallet_address
                )
                
                # Update wallet with transactions
                for tx in transactions:
                    self.database.save_transaction(tx, self.wallet_core.current_wallet_address)
                
                # Calculate balance from transactions
                total_received = sum(
                    tx.get('amount', 0) for tx in transactions 
                    if tx.get('to', '').lower() == self.wallet_core.current_wallet_address.lower()
                )
                total_sent = sum(
                    tx.get('amount', 0) for tx in transactions 
                    if tx.get('from', '').lower() == self.wallet_core.current_wallet_address.lower()
                )
                current_balance = total_received - total_sent
                
                self.wallet_core.update_balance(current_balance)
                
                def update_ui_fallback():
                    self.update_balance_display()
                    self.update_transaction_history()
                    self.show_snackbar(f"Fallback sync: {len(transactions)} transactions", "info")
                    
                self.page.run_thread(update_ui_fallback)
                
        except Exception as e:
            print(f"DEBUG: Fallback sync error: {e}")
            self.page.run_thread(lambda: self.show_snackbar("Fallback sync failed", "error"))

    def update_balance_display(self):
        """Update balance display in UI with available and pending balances"""
        try:
            # Get current wallet info
            wallet_info = None
            current_address = None
            if hasattr(self, 'wallet_core') and self.wallet_core:
                if hasattr(self.wallet_core, 'current_wallet_address'):
                    current_address = self.wallet_core.current_wallet_address
                    if current_address and hasattr(self.wallet_core, 'wallets'):
                        if isinstance(self.wallet_core.wallets, dict) and current_address in self.wallet_core.wallets:
                            wallet_info = self.wallet_core.wallets[current_address]

            print(f"DEBUG update_balance_display: current_address={current_address[:12] if current_address else 'None'}")
            print(f"DEBUG update_balance_display: wallet_info keys={list(wallet_info.keys()) if wallet_info else 'None'}")
            
            if wallet_info:
                # Get available and pending balances - use cached values or placeholder
                confirmed_balance = wallet_info.get('confirmed_balance')
                available_balance = wallet_info.get('available_balance')
                pending_balance = wallet_info.get('pending_balance')
                total_balance = wallet_info.get('balance')
                
                # If balances are not set (None), show placeholder text instead of 0
                if confirmed_balance is None:
                    print(f"  confirmed_balance=None (not calculated yet)")
                else:
                    print(f"  confirmed_balance={confirmed_balance}")
                if pending_balance is None:
                    print(f"  pending_balance=None (not calculated yet)")
                else:
                    print(f"  pending_balance={pending_balance}")
                if total_balance is None:
                    print(f"  total_balance=None (not calculated yet)")
                else:
                    print(f"  total_balance={total_balance}")

                # Update main balance display (total balance)
                if total_balance is not None:
                    formatted_balance = format_balance(total_balance)
                else:
                    formatted_balance = "--.--"  # Placeholder
                
                if hasattr(self, 'balance_text'):
                    self.balance_text.value = f"{formatted_balance} LUNAR"
                    self.balance_text.update()

                if hasattr(self, 'balance_amount'):
                    self.balance_amount.value = formatted_balance
                    self.balance_amount.update()

                # Update balance card display via wallet page
                if hasattr(self, 'wallet_page') and self.wallet_page:
                    # Use available_balance if it exists and > 0, otherwise confirmed_balance, otherwise placeholder
                    if available_balance is not None and available_balance > 0:
                        display_balance = available_balance
                    elif confirmed_balance is not None:
                        display_balance = confirmed_balance
                    else:
                        display_balance = None  # Will show placeholder
                    
                    if hasattr(self.wallet_page, 'balance_text'):
                        if display_balance is not None:
                            self.wallet_page.balance_text.value = f"{display_balance:.6f} LKC"
                            print(f"  Updated wallet_page.balance_text to {display_balance:.6f}")
                        else:
                            self.wallet_page.balance_text.value = "--.-- LKC"
                            print(f"  Updated wallet_page.balance_text to placeholder")
                        self.wallet_page.balance_text.update()

                    if hasattr(self.wallet_page, 'pending_balance_text'):
                        if pending_balance is not None:
                            self.wallet_page.pending_balance_text.value = f"{pending_balance:.6f} LKC"
                            print(f"  Updated wallet_page.pending_balance_text to {pending_balance:.6f}")
                        else:
                            self.wallet_page.pending_balance_text.value = "--.-- LKC"
                            print(f"  Updated wallet_page.pending_balance_text to placeholder")
                        self.wallet_page.pending_balance_text.update()
            else:
                print(f"DEBUG update_balance_display: No wallet_info found, cannot update balances")

        except Exception as e:
            print(f"DEBUG: Balance display update error: {e}")
            import traceback
            traceback.print_exc()

    def update_transaction_history(self):
        """Update transaction history using lunalib transactions"""
        try:
            # Clear existing transactions
            if hasattr(self, 'transactions_list'):
                self.transactions_list.controls.clear()
            else:
                # Initialize transactions list if it doesn't exist
                self.transactions_list = ft.ListView(spacing=8, height=200, expand=True)
            
            if hasattr(self, 'wallet_core') and self.wallet_core:
                # Check if wallet is unlocked
                is_unlocked = (
                    getattr(self.wallet_core, 'is_unlocked', False) or
                    getattr(self.wallet_core, 'is_locked', True) == False or
                    getattr(self, 'is_locked', True) == False
                )
                
                if is_unlocked:
                    # Use lunalib transactions to get transaction history
                    from lunalib.transactions.transactions import TransactionManager
                    tx_manager = TransactionManager()
                    
                    # Get current wallet address
                    current_address = getattr(self.wallet_core, 'current_wallet_address', '')
                    if not current_address:
                        self._show_no_wallet_message()
                        return
                    
                    # Get transactions using lunalib
                    transactions = []
                    
                    # Method 1: Try database first - PRIORITIZE get_all_transactions (no 100-tx limit)
                    if hasattr(self, 'database'):
                        # Try common database methods - get_all_transactions FIRST to avoid 100 tx limit
                        db_methods = ['get_all_transactions', 'get_transactions', 'get_wallet_transactions', 'load_transactions']
                        for method in db_methods:
                            if hasattr(self.database, method):
                                try:
                                    if method == 'get_all_transactions':
                                        all_txs = getattr(self.database, method)()
                                        # Filter for current wallet
                                        transactions = [tx for tx in all_txs if 
                                                    tx.get('from') == current_address or 
                                                    tx.get('to') == current_address]
                                    else:
                                        transactions = getattr(self.database, method)(current_address)
                                    break
                                except:
                                    continue
                    
                    # Method 2: If no transactions from database, create sample or use blockchain
                    if not transactions:
                        transactions = self._get_transactions_from_blockchain(current_address)
                    
                    if not transactions:
                        self._show_no_transactions_message()
                        return
                    
                    # Sort by timestamp (newest first) and limit to 10
                    transactions.sort(key=lambda x: x.get('timestamp', 0), reverse=True)
                    transactions = transactions[:10]
                    
                    # Create transaction cards
                    for tx in transactions:
                        tx_card = self._create_transaction_card(tx, current_address)
                        self.transactions_list.controls.append(tx_card)
                        
                else:
                    self._show_wallet_locked_message()
            else:
                self._show_wallet_not_available_message()
                
        except Exception as e:
            print(f"DEBUG: Transaction history error: {e}")
            self._show_error_message(str(e))

    def _get_transactions_from_blockchain(self, address: str):
        """Get transactions from blockchain manager"""
        transactions = []
        try:
            if hasattr(self, 'blockchain_manager'):
                transactions = self.blockchain_manager.scan_transactions_for_address(address)
        except Exception as e:
            print(f"DEBUG: Blockchain scan error: {e}")
        
        return transactions

    def _create_transaction_card(self, tx: dict, current_address: str):
        """Create a transaction card UI element"""
        from lunalib.transactions.transactions import TransactionSecurity
        
        security = TransactionSecurity()
        
        # Get transaction details
        tx_type = tx.get('type', 'transfer')
        amount = tx.get('amount', 0)
        from_addr = tx.get('from', '')
        to_addr = tx.get('to', '')
        status = tx.get('status', 'confirmed')
        timestamp = tx.get('timestamp', 0)
        tx_hash = tx.get('hash', '')
        memo = tx.get('memo', '')
        fee = tx.get('fee', 0)
        
        # Determine direction and styling - FIXED LOGIC
        is_incoming = to_addr and to_addr.lower() == current_address.lower()
        is_outgoing = from_addr and from_addr.lower() == current_address.lower()
        
        # Special handling for different transaction types
        if tx_type == 'reward':
            is_incoming = True
            is_outgoing = False
        elif tx_type in ['stake', 'delegate']:
            is_outgoing = True
            is_incoming = False
        
        # Use lunalib to get color and risk assessment
        risk_level, risk_reason = security.assess_risk(tx)
        
        # Set colors and icons based on transaction type and direction
        if is_incoming:
            color = "#00ff00"  # Green for incoming
            icon = "📥"
            direction = "Received"
            amount_display = f"+{amount:.6f} LKC"
            # For incoming transactions, show who sent it
            display_address = from_addr if from_addr else "Unknown Sender"
        elif is_outgoing:
            color = "#ff4444"  # Red for outgoing
            icon = "📤"
            direction = "Sent"
            # Include fee in outgoing amount display
            total_amount = amount + fee
            amount_display = f"-{total_amount:.6f} LKC"
            # For outgoing transactions, show who received it
            display_address = to_addr if to_addr else "Unknown Recipient"
        else:
            # For other cases (like failed transactions)
            color = "#ffa500"  # Orange
            icon = "❓"
            direction = "Unknown"
            amount_display = f"{amount:.6f} LKC"
            display_address = "Unknown"
        
        # Format address for display
        if display_address:
            truncated_addr = f"{display_address[:8]}...{display_address[-6:]}" if len(display_address) > 14 else display_address
        else:
            truncated_addr = "Unknown"
        
        # Format date
        from datetime import datetime
        date_str = datetime.fromtimestamp(timestamp).strftime("%m/%d %H:%M") if timestamp else "Unknown"
        
        # Add fee display for outgoing transactions
        fee_display = ""
        if is_outgoing and fee > 0:
            fee_display = f" (Fee: {fee:.6f} LKC)"
        
        # Create transaction card
        return ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Text(
                        amount_display,
                        size=16,
                        color=color,
                        weight="bold",
                        expand=True
                    ),
                    ft.Container(
                        content=ft.Text(
                            status.upper(),
                            size=10,
                            color=color,
                            weight="bold"
                        ),
                        padding=ft.padding.symmetric(horizontal=6, vertical=2),
                        bgcolor=f"{color}20",
                        border_radius=6
                    )
                ]),
                ft.Row([
                    ft.Icon(icon, size=14, color=color),
                    ft.Text(
                        f"{direction}: {truncated_addr}{fee_display}",
                        size=12,
                        color="#f8d7da",
                        expand=True
                    ),
                    ft.Text(
                        date_str,
                        size=10,
                        color="#a8a8a8"
                    )
                ]),
                ft.Row([
                    ft.Text(
                        memo if memo else f"TX: {tx_hash[:8]}...",
                        size=10,
                        color="#a8a8a8",
                        expand=True,
                        max_lines=1,
                        overflow="ellipsis"
                    ),
                    ft.TextButton(
                        "View",
                        on_click=lambda e, tx_data=tx: self._show_transaction_details(tx_data),
                        style=ft.ButtonStyle(
                            color=color,
                            padding=ft.padding.symmetric(horizontal=8, vertical=2),
                            overlay_color=f"{color}20"
                        )
                    )
                ])
            ], spacing=6),
            padding=12,
            bgcolor="#2c1a1a",
            border_radius=10,
            border=ft.border.all(1, "#5c2e2e")
        )
    def _show_no_transactions_message(self):
        """Show no transactions message"""
        if hasattr(self, 'transactions_list'):
            self.transactions_list.controls.append(
                ft.Container(
                    content=ft.Column([
                        ft.Icon(ft.Icons.RECEIPT_LONG, size=32, color="#5c2e2e"),
                        ft.Text("No transactions yet", color="#f8d7da", size=14),
                        ft.Text("Your transactions will appear here", color="#a8a8a8", size=12),
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=5),
                    padding=20,
                    alignment=ft.Alignment(0, 0)
                )
            )

    def _show_wallet_locked_message(self):
        """Show wallet locked message"""
        if hasattr(self, 'transactions_list'):
            self.transactions_list.controls.append(
                ft.Container(
                    content=ft.Column([
                        ft.Icon(ft.Icons.LOCK, size=32, color="#5c2e2e"),
                        ft.Text("Wallet Locked", color="#f8d7da", size=14),
                        ft.Text("Unlock wallet to view transactions", color="#a8a8a8", size=12),
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=5),
                    padding=20,
                    alignment=ft.Alignment(0, 0)
                )
            )

    def _show_wallet_not_available_message(self):
        """Show wallet not available message"""
        if hasattr(self, 'transactions_list'):
            self.transactions_list.controls.append(
                ft.Container(
                    content=ft.Column([
                        ft.Icon(ft.Icons.ERROR, size=32, color="#5c2e2e"),
                        ft.Text("Wallet Not Available", color="#f8d7da", size=14),
                        ft.Text("Wallet core not initialized", color="#a8a8a8", size=12),
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=5),
                    padding=20,
                    alignment=ft.Alignment(0, 0)
                )
            )

    def _show_no_wallet_message(self):
        """Show no wallet selected message"""
        if hasattr(self, 'transactions_list'):
            self.transactions_list.controls.append(
                ft.Container(
                    content=ft.Column([
                        ft.Icon(ft.Icons.WALLET, size=32, color="#5c2e2e"),
                        ft.Text("No Wallet Selected", color="#f8d7da", size=14),
                        ft.Text("Select a wallet to view transactions", color="#a8a8a8", size=12),
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=5),
                    padding=20,
                    alignment=ft.Alignment(0, 0)
                )
            )

    def _show_error_message(self, error: str):
        """Show error message"""
        if hasattr(self, 'transactions_list'):
            self.transactions_list.controls.append(
                ft.Container(
                    content=ft.Column([
                        ft.Icon(ft.Icons.ERROR, size=32, color="#5c2e2e"),
                        ft.Text("Error Loading", color="#f8d7da", size=14),
                        ft.Text(f"Failed to load transactions", color="#a8a8a8", size=12),
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=5),
                    padding=20,
                    alignment=ft.Alignment(0, 0)
                )
            )

    def _create_transaction_item(self, transaction: Dict):
        """Create a UI item for a transaction"""
        # Use your existing transaction formatting functions
        color = get_transaction_color(transaction, [self.wallet_core.current_wallet_address])
        icon = get_transaction_icon(transaction, [self.wallet_core.current_wallet_address])
        
        # Return your transaction UI component
        # This depends on your UI framework (Flet, etc.)
        pass
    def show_wallet_page(self):
        """Show main wallet page after successful unlock"""
        print("DEBUG: Showing wallet page")
        try:
            wallet_page = WalletPage(
                self,
                on_send=self.show_send_page,
                on_receive=self.show_receive_page,
                on_export_key=self.show_export_key_page,
                on_lock=self.show_lock_page,
                on_create_wallet=self.show_create_wallet,
                on_import_wallet=self.show_import_wallet,
                on_settings=self.show_settings_page
            )
            # Keep reference to WalletPage object (not the Flet Container it returns)
            self.wallet_page = wallet_page
            self.current_page = wallet_page.create()
            
            # Clear and add the wallet page
            self.page.controls.clear()
            self.page.add(self.current_page)
            self.page.update()
            
            # Populate sidebar and main UI immediately with cached data
            try:
                if hasattr(self.wallet_page, '_refresh_sidebar_wallets'):
                    self.wallet_page._refresh_sidebar_wallets()
                if hasattr(self.wallet_page, '_update_wallet_data_ui_only'):
                    self.wallet_page._update_wallet_data_ui_only()
                if hasattr(self.page, 'update'):
                    self.page.update()
            except Exception as e:
                print(f"DEBUG: Error populating UI with cached data: {e}")
            
            # Start continuous blockchain scanning for all wallets
            self.start_continuous_blockchain_scan()
            
            # Defer wallet data update to background to not block UI
            def load_wallet_data():
                try:
                    self.update_wallet_data()
                except Exception as e:
                    print(f"DEBUG: Error loading wallet data in background: {e}")
            
            threading.Thread(target=load_wallet_data, daemon=True).start()
            
        except Exception as e:
            print(f"DEBUG: Error showing wallet page: {e}")
            import traceback
            traceback.print_exc()
            self.show_snackbar("Error loading wallet interface", "error")

    def show_create_wallet(self):
        create_page = CreateWalletPage(
            self,
            on_back=self.show_previous_page,
            on_wallet_created=self.on_wallet_created
        )
        self.current_page = create_page.create()
        
        # Clear the page and add the new content properly centered
        self.page.controls.clear()
        
        # Create a container that ensures proper centering
        centered_content = ft.Container(
            content=self.current_page,
            expand=True,
            alignment=ft.Alignment(0, 0),
            padding=20
        )
        
        self.page.add(centered_content)
        self.page.update()

    def show_import_wallet(self):
        import_page = ImportWalletPage(
            self,
            on_back=self.show_previous_page,
            on_wallet_imported=self.on_wallet_imported
        )
        self.current_page = import_page.create()
        self.show_current_page()

    def show_send_page(self):
        """Show send page for current wallet with enhanced error handling"""
        try:
            print("DEBUG: Entering show_send_page")
            
            # Check if wallet is properly unlocked
            if self.is_locked:
                print("DEBUG: Wallet is locked, cannot send")
                self.show_snackbar("Wallet is locked. Please unlock first.", "error")
                return
                
            current_address = None
            if hasattr(self.wallet_core, 'current_wallet_address'):
                current_address = self.wallet_core.current_wallet_address
                print(f"DEBUG: Current wallet address: {current_address}")
            else:
                print("DEBUG: No current wallet address found")
                self.show_snackbar("No wallet selected", "error")
                return
                
            # Check if we have the private key for signing
            if not hasattr(self.wallet_core, 'private_key') or not self.wallet_core.private_key:
                print("DEBUG: No private key available - wallet may be locked")
                self.show_snackbar("Wallet is locked or private key not available", "error")
                return
                
            print("DEBUG: Creating SendPage instance")
            send_page = SendPage(
                self,
                on_back=self.show_previous_page,
                on_send_complete=self.on_send_complete,
                from_address=current_address
            )
            
            self.current_page = send_page.create()
            self.show_current_page()
            print("DEBUG: Send page displayed successfully")
            
        except Exception as e:
            print(f"DEBUG: Error in show_send_page: {e}")
            import traceback
            traceback.print_exc()
            self.show_snackbar(f"Error opening send page: {str(e)}", "error")

    def show_receive_page(self):
        """Show receive page for current wallet"""
        current_address = None
        if hasattr(self.wallet_core, 'current_wallet_address'):
            current_address = self.wallet_core.current_wallet_address
        
        receive_page = ReceivePage(
            self, 
            on_back=self.show_previous_page,
            wallet_address=current_address  # Pass the current wallet address
        )
        self.current_page = receive_page.create()
        self.show_current_page()

    def show_export_key_page(self):
        """Show export key page for current wallet"""
        current_address = None
        if hasattr(self.wallet_core, 'current_wallet_address'):
            current_address = self.wallet_core.current_wallet_address
        
        export_page = ExportKeyPage(
            self, 
            on_back=self.show_previous_page,
            wallet_address=current_address  # Pass the current wallet address
        )
        self.current_page = export_page.create()
        self.show_current_page()

    def show_settings_page(self):
        """Show settings page for wallet configuration"""
        settings_page = SettingsPage(
            self,
            on_back=self.show_previous_page
        )
        self.current_page = settings_page.create()
        self.show_current_page()

    def show_previous_page(self):
        if self.is_locked:
            wallet_exists = self.wallet_count > 0
            self.show_lock_page(
                wallet_exists=wallet_exists,
                show_create=not wallet_exists
            )
        else:
            self.show_wallet_page()

    def on_send_complete(self):
        """Handle successful transaction send"""
        try:
            print("DEBUG: on_send_complete called - transaction sent successfully")
            
            # Go back to wallet page
            self.show_previous_page()
            
            # Refresh wallet data and UI
            if hasattr(self, 'wallet_page') and self.wallet_page:
                self.wallet_page._refresh_sidebar_wallets()
                self.wallet_page._update_wallet_data_ui_only()
            
            if hasattr(self, 'page'):
                self.page.update()
                
        except Exception as e:
            print(f"DEBUG: Error in on_send_complete: {e}")
            import traceback
            traceback.print_exc()

    def on_wallet_created(self):
        """Handle wallet creation success"""
        try:
            print("DEBUG: on_wallet_created called - transitioning to wallet page")
            self.is_locked = False
            self.last_activity_time = time.time()
            
            # CRITICAL: Save wallet immediately after creation
            print("DEBUG: Saving wallet data after creation...")
            save_success = self.save_wallet_data(force_save=True)
            if save_success:
                print("DEBUG: Wallet data saved successfully after creation")
                # Create backup for important operation
                backup_success = self.create_backup()
                print(f"DEBUG: Backup creation: {backup_success}")
            else:
                print("DEBUG: WARNING: Failed to save wallet after creation")
            
            # Wallet creation complete - balances will be calculated during blockchain sync
            # Do not reset balances here - placeholder will show until scan completes
            
            # Show success message
            self.show_snackbar("Wallet created successfully!", "success")
            
            # Force immediate transition
            print("DEBUG: Immediately showing wallet page")
            self.show_wallet_page()
            
            # Sync all wallets to populate balances asynchronously
            def sync_after_creation():
                try:
                    self.scan_all_wallets_for_changes(force_full_scan=True)
                    print("DEBUG: Background sync completed after wallet creation")
                except Exception as e:
                    print(f"DEBUG: Background sync error after creation: {e}")
            
            threading.Thread(target=sync_after_creation, daemon=True).start()
            
        except Exception as e:
            print(f"DEBUG: Error in on_wallet_created: {e}")
            import traceback
            traceback.print_exc()
            self.show_snackbar("Wallet created but transition failed", "error")
            # Force transition anyway
            self.show_wallet_page()

    def on_wallet_imported(self):
        """Handle wallet import success"""
        self.is_locked = False
        self.last_activity_time = time.time()
        
        # Save wallet immediately after import
        print("DEBUG: Saving wallet data after import...")
        save_success = self.save_wallet_data(force_save=True)
        if save_success:
            print("DEBUG: Wallet data saved after import")
            # Create backup for important operation
            self.create_backup()
        
        # Update wallet metadata for future sessions
        # Update wallet metadata for future sessions
        self._load_wallet_metadata()
        
        # Wallet import complete - balances will be calculated during blockchain sync
        # Do not reset balances here - placeholder will show until scan completes
        
        self.show_snackbar("Wallet imported successfully!", "success")
        self.show_wallet_page()
        
        # Sync all wallets to populate balances asynchronously
        def sync_after_import():
            try:
                self.scan_all_wallets_for_changes(force_full_scan=True)
                print("DEBUG: Background sync completed after wallet import")
            except Exception as e:
                print(f"DEBUG: Background sync error after import: {e}")
        
        threading.Thread(target=sync_after_import, daemon=True).start()
    
    def debug_transaction_parameters(self, to_address, amount, fee=None, memo=None):
        """Debug transaction parameters before sending"""
        print("=" * 50)
        print("DEBUG: Transaction Parameters")
        print("=" * 50)
        print(f"From Address: {getattr(self.wallet_core, 'current_wallet_address', 'None')}")
        print(f"To Address: {to_address}")
        print(f"Amount: {amount}")
        print(f"Fee: {fee}")
        print(f"Memo: {memo}")
        
        # Check wallet state
        print(f"Wallet Locked: {self.is_locked}")
        print(f"Wallet Core Locked: {getattr(self.wallet_core, 'is_locked', 'Unknown')}")
        print(f"Private Key Available: {bool(getattr(self.wallet_core, 'private_key', None))}")
        print(f"Balance: {getattr(self.wallet_core, 'balance', 'Unknown')}")
        
        # Check blockchain manager
        if hasattr(self, 'blockchain_manager'):
            print(f"Blockchain Endpoint: {getattr(self.blockchain_manager, 'endpoint_url', 'Unknown')}")
            print(f"Network Connected: {self.blockchain_manager.check_network_connection()}")
        else:
            print("Blockchain Manager: Not available")
        
        print("=" * 50)

    def lock_wallet(self, wtfisthis):
        """Lock wallet and save state"""
        print(wtfisthis)
        # Stop continuous scan when locking
        self.continuous_scan_active = False
        
        # Save wallet before locking
        self.save_wallet_data(force_save=True)
        
        self.is_locked = True
        if hasattr(self.wallet_core, 'lock_wallet'):
            self.wallet_core.lock_wallet()
        self.show_lock_page(
            title="Wallet Locked", 
            subtitle="Please unlock your wallet to continue",
            wallet_exists=True
        )
        self.show_snackbar("Wallet locked", "info")

    def update_wallet_data(self):
        if hasattr(self, 'wallet_page') and self.wallet_page and hasattr(self.wallet_page, 'update_wallet_data'):
            self.wallet_page.update_wallet_data()

    def show_snackbar(self, message, message_type="info"):
        color = {
            "error": "#dc3545",
            "success": "#28a745", 
            "warning": "#ffc107",
            "info": "#17a2b8"
        }.get(message_type, "#f8d7da")
        
        snack_bar = ft.SnackBar(
            content=ft.Text(message, color="#ffffff"),
            bgcolor=color
        )
        self.page.overlay.append(snack_bar)
        snack_bar.open = True
        self.page.update()
        
        def remove_snack():
            time.sleep(3)
            if snack_bar in self.page.overlay:
                self.page.overlay.remove(snack_bar)
                self.page.update()
                
        threading.Thread(target=remove_snack, daemon=True).start()

    def update_refs(self):
        if hasattr(self, 'page'):
            self.page.update()


    def get_current_time(self):
        """Helper method to get current time"""
        import time
        return time.time()

def main(page: ft.Page):
    app = LunaWalletApp()
    app.create_main_ui(page)

if __name__ == "__main__":
    ft.app(target=main)
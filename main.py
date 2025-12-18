import flet as ft
import threading
import time
import os
import json
import shutil
from datetime import datetime
import base64
from typing import Dict
import sqlite3
from pathlib import Path

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
        self.transaction_manager = TransactionManager()
        self.encryption_manager = EncryptionManager()
        self.database = WalletDatabase()
        
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
                    alignment=ft.alignment.center,
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
        self.current_page = lock_page.create()
        
        # Clear and add with proper centering
        self.page.controls.clear()
        centered_content = ft.Container(
            content=self.current_page,
            expand=True,
            alignment=ft.alignment.center,
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
        """Unlock existing wallet with password using only LunaWallet methods"""
        def unlock_thread():
            try:
                print("DEBUG: Starting unlock process...")
                print(f"DEBUG: Password length: {len(password)}")
                
                success = False
                
                # FIRST: Load the wallet data from persistence
                print("DEBUG: Loading wallet data from file...")
                load_success = self.load_wallet_data()
                print(f"DEBUG: Wallet data load result: {load_success}")
                
                if not load_success:
                    print("DEBUG: Failed to load wallet data")
                    def show_load_error():
                        self.show_snackbar("Failed to load wallet data", "error")
                    self.page.run_thread(show_load_error)
                    return

                # Method 1: Use LunaWallet's unlock_wallet method
                print("DEBUG: Using LunaWallet.unlock_wallet method")
                
                if hasattr(self.wallet_core, 'wallets') and self.wallet_core.wallets:
                    print(f"DEBUG: Found {len(self.wallet_core.wallets)} wallets")
                    
                    # Try to unlock each wallet in the collection
                    for wallet_address in self.wallet_core.wallets.keys():
                        try:
                            print(f"DEBUG: Attempting to unlock wallet: {wallet_address}")
                            
                            # Use LunaWallet's unlock_wallet method with correct signature
                            success = self.wallet_core.unlock_wallet(wallet_address, password)
                            
                            if success:
                                print(f"DEBUG: SUCCESS! Unlocked wallet: {wallet_address}")
                                
                                # Set this as the current wallet
                                self.wallet_core.current_wallet_address = wallet_address
                                current_wallet = self.wallet_core.wallets[wallet_address]
                                self.wallet_core._set_current_wallet(current_wallet)
                                
                                break
                            else:
                                print(f"DEBUG: Failed to unlock wallet: {wallet_address}")
                                
                        except Exception as wallet_error:
                            print(f"DEBUG: Unlock error for {wallet_address}: {wallet_error}")
                            continue
                
                # Method 2: If we have wallets but unlock_wallet didn't work, try switch_wallet with password
                if not success and hasattr(self.wallet_core, 'switch_wallet'):
                    print("DEBUG: Trying switch_wallet with password...")
                    
                    if self.wallet_core.wallets:
                        first_wallet_address = list(self.wallet_core.wallets.keys())[0]
                        try:
                            print(f"DEBUG: Switching to wallet: {first_wallet_address}")
                            success = self.wallet_core.switch_wallet(first_wallet_address, password)
                            print(f"DEBUG: switch_wallet result: {success}")
                        except Exception as switch_error:
                            print(f"DEBUG: switch_wallet failed: {switch_error}")
                
                # Method 3: Try load_from_file if we have a file path
                if not success and hasattr(self.wallet_core, 'load_from_file'):
                    print("DEBUG: Trying load_from_file with password...")
                    try:
                        # Try to load from the main wallet file
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
                        
                        # Verify the wallet is actually unlocked
                        if hasattr(self.wallet_core, 'is_unlocked'):
                            print(f"DEBUG: Wallet unlocked status: {self.wallet_core.is_unlocked}")
                        if hasattr(self.wallet_core, 'private_key') and self.wallet_core.private_key:
                            print("DEBUG: Private key is available")
                        
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
                        # Keep the lock screen visible for retry
                    
                self.page.run_thread(update_ui)
                
            except Exception as e:
                print(f"DEBUG: Unlock error: {e}")
                import traceback
                traceback.print_exc()
                def show_error():
                    self.show_snackbar(f"Unlock error: {str(e)}", "error")
                self.page.run_thread(show_error)
        
        threading.Thread(target=unlock_thread, daemon=True).start()
    def start_blockchain_sync(self):
        """Start blockchain synchronization using existing BlockchainManager"""
        def sync_thread():
            try:
                print("DEBUG: Starting blockchain sync...")
                
                # Check network connection first
                if not self.blockchain_manager.check_network_connection():
                    self.page.run_thread(lambda: self.show_snackbar("Network not connected", "error"))
                    return
                
                if self.wallet_core.current_wallet_address:
                    # Use the existing scan method that we know works
                    transactions = self.blockchain_manager.scan_transactions_for_address(
                        self.wallet_core.current_wallet_address
                    )
                    
                    print(f"DEBUG: Found {len(transactions)} transactions")
                    
                    # Update database with new transactions
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
                    
                    def update_ui():
                        # This is the key fix: Update wallet data which triggers sidebar update
                        self.update_wallet_data()
                        self.update_balance_display()
                        self.update_transaction_history()
                        self.show_snackbar(f"Sync completed: {len(transactions)} transactions", "success")
                        
                        # Save wallet after sync completion
                        self.save_wallet_data(force_save=True)
                        self.create_backup()
                        
                    self.page.run_thread(update_ui)
                else:
                    print("DEBUG: No wallet address available for sync")
                    self.page.run_thread(lambda: self.show_snackbar("No wallet address available", "warning"))
                    
            except Exception as e:
                print(f"DEBUG: Sync error: {e}")
                import traceback
                traceback.print_exc()
                
                def show_error():
                    self.show_snackbar(f"Sync error: {str(e)}", "error")
                
                self.page.run_thread(show_error)
        
        # Start sync in background thread
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
        """Update balance display in UI"""
        try:
            balance = self.wallet_core.get_balance()
            formatted_balance = format_balance(balance)
            
            # Update your balance display components
            if hasattr(self, 'balance_text'):
                self.balance_text.value = f"{formatted_balance} LUNAR"
                self.balance_text.update()
                
            if hasattr(self, 'balance_amount'):
                self.balance_amount.value = formatted_balance
                self.balance_amount.update()
                
        except Exception as e:
            print(f"DEBUG: Balance display update error: {e}")

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
                    
                    # Method 1: Try database first
                    if hasattr(self, 'database'):
                        # Try common database methods
                        db_methods = ['get_transactions', 'get_wallet_transactions', 'load_transactions', 'get_all_transactions']
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
            amount_display = f"+{amount:.6f} LUN"
            # For incoming transactions, show who sent it
            display_address = from_addr if from_addr else "Unknown Sender"
        elif is_outgoing:
            color = "#ff4444"  # Red for outgoing
            icon = "📤"
            direction = "Sent"
            # Include fee in outgoing amount display
            total_amount = amount + fee
            amount_display = f"-{total_amount:.6f} LUN"
            # For outgoing transactions, show who received it
            display_address = to_addr if to_addr else "Unknown Recipient"
        else:
            # For other cases (like failed transactions)
            color = "#ffa500"  # Orange
            icon = "❓"
            direction = "Unknown"
            amount_display = f"{amount:.6f} LUN"
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
            fee_display = f" (Fee: {fee:.6f} LUN)"
        
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
                    alignment=ft.alignment.center
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
                    alignment=ft.alignment.center
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
                    alignment=ft.alignment.center
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
                    alignment=ft.alignment.center
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
                    alignment=ft.alignment.center
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
                on_create_wallet=self.show_create_wallet,
                on_import_wallet=self.show_import_wallet
            )
            self.current_page = wallet_page.create()
            
            # Clear and add the wallet page
            self.page.controls.clear()
            self.page.add(self.current_page)
            self.page.update()
            
            self.update_wallet_data()
            
        except Exception as e:
            print(f"DEBUG: Error showing wallet page: {e}")
            self.show_snackbar("Error loading wallet interface", "error")
            # Fallback to lock screen
            self.show_lock_page()

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
            alignment=ft.alignment.center,
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

    def show_previous_page(self):
        if self.is_locked:
            self.show_lock_page()
        else:
            self.show_wallet_page()

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
            
            # Update wallet metadata for future sessions
            self._load_wallet_metadata()
            
            # Show success message
            self.show_snackbar("Wallet created successfully!", "success")
            
            # Force immediate transition
            print("DEBUG: Immediately showing wallet page")
            self.show_wallet_page()
            
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
        self._load_wallet_metadata()
        
        self.show_snackbar("Wallet imported successfully!", "success")
        self.show_wallet_page()
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
    def calculate_available_balance(self) -> float:
        """Calculate available balance (total balance minus pending outgoing transactions)"""
        try:
            from lunalib.core.mempool import MempoolManager
            from lunalib.core.blockchain import BlockchainManager
            
            # Get total balance from blockchain
            total_balance = self._get_total_balance_from_blockchain()
            
            # Get pending outgoing transactions from mempool
            mempool = MempoolManager()
            pending_txs = mempool.get_pending_transactions(self.address)
            
            # Sum pending outgoing amounts
            pending_outgoing = 0.0
            for tx in pending_txs:
                if tx.get('from') == self.address:
                    pending_outgoing += float(tx.get('amount', 0)) + float(tx.get('fee', 0))
            
            available_balance = max(0.0, total_balance - pending_outgoing)
            
            # Update both current wallet and wallets collection
            self.available_balance = available_balance
            if self.current_wallet_address in self.wallets:
                self.wallets[self.current_wallet_address]['available_balance'] = available_balance
            
            print(f"DEBUG: Available balance calculated - Total: {total_balance}, Pending Out: {pending_outgoing}, Available: {available_balance}")
            return available_balance
            
        except Exception as e:
            print(f"DEBUG: Error calculating available balance: {e}")
            return self.balance  # Fallback to total balance

    def _get_total_balance_from_blockchain(self) -> float:
        """Get total balance by scanning blockchain for confirmed transactions"""
        try:
            from lunalib.core.blockchain import BlockchainManager
            
            blockchain = BlockchainManager()
            transactions = blockchain.scan_transactions_for_address(self.address)
            
            total_balance = 0.0
            for tx in transactions:
                tx_type = tx.get('type', '')
                
                # Handle incoming transactions
                if tx.get('to') == self.address:
                    if tx_type in ['transfer', 'reward', 'fee_distribution', 'gtx_genesis']:
                        total_balance += float(tx.get('amount', 0))
                
                # Handle outgoing transactions  
                elif tx.get('from') == self.address:
                    if tx_type in ['transfer', 'stake', 'delegate']:
                        total_balance -= float(tx.get('amount', 0))
                        total_balance -= float(tx.get('fee', 0))
            
            return max(0.0, total_balance)
            
        except Exception as e:
            print(f"DEBUG: Error getting blockchain balance: {e}")
            return self.balance

    def refresh_balance(self) -> bool:
        """Refresh both total and available balance from blockchain and mempool"""
        try:
            total_balance = self._get_total_balance_from_blockchain()
            available_balance = self.calculate_available_balance()
            
            # Update wallet state
            self.balance = total_balance
            self.available_balance = available_balance
            
            # Update in wallets collection
            if self.current_wallet_address in self.wallets:
                self.wallets[self.current_wallet_address]['balance'] = total_balance
                self.wallets[self.current_wallet_address]['available_balance'] = available_balance
            
            print(f"DEBUG: Balance refreshed - Total: {total_balance}, Available: {available_balance}")
            return True
            
        except Exception as e:
            print(f"DEBUG: Error refreshing balance: {e}")
            return False

    def get_available_balance(self) -> float:
        """Get current wallet available balance"""
        return self.available_balance

    def get_transaction_history(self) -> dict:
        """Get complete transaction history (both pending and confirmed)"""
        try:
            from lunalib.core.blockchain import BlockchainManager
            from lunalib.core.mempool import MempoolManager
            
            blockchain = BlockchainManager()
            mempool = MempoolManager()
            
            # Get confirmed transactions from blockchain
            confirmed_txs = blockchain.scan_transactions_for_address(self.address)
            
            # Get pending transactions from mempool
            pending_txs = mempool.get_pending_transactions(self.address)
            
            return {
                'confirmed': confirmed_txs,
                'pending': pending_txs,
                'total_confirmed': len(confirmed_txs),
                'total_pending': len(pending_txs)
            }
        except Exception as e:
            print(f"DEBUG: Error getting transaction history: {e}")
            return {'confirmed': [], 'pending': [], 'total_confirmed': 0, 'total_pending': 0}
    def send_transaction(self, to_address: str, amount: float, memo: str = "", password: str = None) -> bool:
        """Send transaction using lunalib transactions with proper mempool submission"""
        try:
            print(f"DEBUG: send_transaction called - to: {to_address}, amount: {amount}, memo: {memo}")
            
            # Refresh balances first to get latest state
            self.refresh_balance()
            
            # Check available balance before proceeding
            if amount > self.available_balance:
                print(f"DEBUG: Insufficient available balance: {self.available_balance} < {amount}")
                return False
            
            # Check if wallet is unlocked
            if self.is_locked or not self.private_key:
                print("DEBUG: Wallet is locked or no private key available")
                return False
            
            # Import transaction manager
            from lunalib.transactions.transactions import TransactionManager
            
            # Create transaction manager
            tx_manager = TransactionManager()
            
            # Create and sign transaction
            transaction = tx_manager.create_transaction(
                from_address=self.address,
                to_address=to_address,
                amount=amount,
                private_key=self.private_key,
                memo=memo,
                transaction_type="transfer"
            )
            
            print(f"DEBUG: Transaction created: {transaction.get('hash')}")
            
            # Validate transaction
            is_valid, message = tx_manager.validate_transaction(transaction)
            if not is_valid:
                print(f"DEBUG: Transaction validation failed: {message}")
                return False
            
            # Send to mempool for broadcasting
            success, message = tx_manager.send_transaction(transaction)
            if success:
                print(f"DEBUG: Transaction sent to mempool: {message}")
                
                # Update available balance immediately (deduct pending transaction)
                fee = transaction.get('fee', 0)
                self.available_balance -= (amount + fee)
                if self.current_wallet_address in self.wallets:
                    self.wallets[self.current_wallet_address]['available_balance'] = self.available_balance
                
                print(f"DEBUG: Available balance updated - new available: {self.available_balance}")
                return True
            else:
                print(f"DEBUG: Failed to send transaction to mempool: {message}")
                return False
                
        except Exception as e:
            print(f"DEBUG: Error in send_transaction: {e}")
            import traceback
            traceback.print_exc()
            return False
    def on_send_complete(self, success=True, error_message=None, tx_hash=None):
        """Handle send transaction completion"""
        try:
            if success:
                # Play send sound
                self._play_sound("send")
                
                # Refresh data
                self.update_balance_display()
                self.update_transaction_history()
                
                # Show success message
                if tx_hash:
                    self.show_snackbar(f"Transaction sent! TX: {tx_hash[:16]}...", "success")
                else:
                    self.show_snackbar("Transaction sent successfully!", "success")
            else:
                # Show error
                if error_message:
                    self.show_snackbar(f"Send failed: {error_message}", "error")
                else:
                    self.show_snackbar("Transaction failed", "error")
                    
        except Exception as e:
            print(f"DEBUG: Error in on_send_complete: {e}")
            self.show_snackbar("Error processing send completion", "error")

    def lock_wallet(self, wtfisthis):
        """Lock wallet and save state"""
        print(wtfisthis)
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
        if hasattr(self, 'current_page') and hasattr(self.current_page, 'update_wallet_data'):
            self.current_page.update_wallet_data()

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
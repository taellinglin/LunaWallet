# app/core.py

import flet as ft
import gui.page_create_wallet
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
import requests  # Ensure requests is imported at the top of the file

# Import unified balance utilities
from utils import (
    calculate_wallet_balances,
    update_all_wallet_balances,
    format_balance_display,
    get_balance_summary
)

# Import services
from app.wallet import WalletService
from app.blockchain import BlockchainService
from app.mempool import MempoolService

# Now import lunalib components after cache is set up
from gui.page_create_wallet import CreateWalletPage
from gui.page_export_key import ExportKeyPage
from gui.page_import_wallet import ImportWalletPage
from gui.page_lock import LockPage
from gui.page_receive import ReceivePage
from gui.page_send import SendPage
from gui.page_wallet import WalletPage
from gui.page_settings import SettingsPage
from gui.tab_menu import TabMenu
from gui.tab_transactions import TabTransactions
from gui.tab_wallets import TabWallets

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

# Global trace logger for builds
def _global_trace(msg: str, category: str = "INFO"):
    """Global file logger for all build diagnostics"""
    try:
        home = os.path.expanduser('~')
        log_dir = os.path.join(home, 'LunaWallet_Logs')
        os.makedirs(log_dir, exist_ok=True)
        log_path = os.path.join(log_dir, 'unlock_trace.log')
        with open(log_path, 'a', encoding='utf-8') as f:
            timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
            # Sanitize message to avoid encoding errors
            try:
                safe_msg = msg.encode('utf-8', errors='replace').decode('utf-8')
            except Exception:
                safe_msg = str(msg)
            f.write(f"[{timestamp}] [{category}] {safe_msg}\n")
    except Exception as log_err:
        # Silently fail - don't let logging crash the app
        try:
            print(f"[LOG_ERROR] Failed to write trace log: {log_err}")
        except Exception:
            pass

# Safe print wrapper to avoid encoding errors on Windows
def _safe_print(*args, **kwargs):
    """Print wrapper that sanitizes output to avoid encoding errors"""
    try:
        # Try normal print first
        print(*args, **kwargs)
    except UnicodeEncodeError:
        # If encoding fails, sanitize and try again
        try:
            sanitized = []
            for arg in args:
                if isinstance(arg, str):
                    sanitized.append(arg.encode('utf-8', errors='replace').decode('utf-8'))
                else:
                    sanitized.append(str(arg))
            print(*sanitized, **kwargs)
        except Exception:
            # Last resort: just skip the print
            pass

# Network diagnostics for troubleshooting build/dev environment issues
def diagnose_network():
    """Log network configuration and SSL settings for debugging"""
    try:
        import sys
        import urllib.parse
        
        timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
        home = os.path.expanduser('~')
        log_dir = os.path.join(home, 'LunaWallet_Logs')
        os.makedirs(log_dir, exist_ok=True)
        log_path = os.path.join(log_dir, 'unlock_trace.log')
        
        # Get environment info
        is_frozen = getattr(sys, 'frozen', False)
        env_type = "BUILD (frozen)" if is_frozen else "DEV (not frozen)"
        
        with open(log_path, 'a', encoding='utf-8') as f:
            f.write(f"[{timestamp}] [NETWORK_DIAG] Environment: {env_type}\n")
            f.write(f"[{timestamp}] [NETWORK_DIAG] Python: {sys.version}\n")
            f.write(f"[{timestamp}] [NETWORK_DIAG] Platform: {sys.platform}\n")
            
            # Check SSL verification
            try:
                import ssl
                f.write(f"[{timestamp}] [NETWORK_DIAG] SSL Protocol: {ssl.OPENSSL_VERSION}\n")
            except Exception as e:
                f.write(f"[{timestamp}] [NETWORK_DIAG] SSL Error: {e}\n")
            
            # Check requests session
            try:
                session = requests.Session()
                f.write(f"[{timestamp}] [NETWORK_DIAG] Requests version: {requests.__version__}\n")
                f.write(f"[{timestamp}] [NETWORK_DIAG] Requests verify SSL: True (default)\n")
            except Exception as e:
                f.write(f"[{timestamp}] [NETWORK_DIAG] Requests Error: {e}\n")
    except Exception as diag_err:
        # Silently fail
        pass

# FIX: Ensure cache directory exists with proper permissions
def setup_cache_directory():
    """Create cache directory for lunalib with proper permissions"""
    try:
        # Try multiple possible cache locations
        cache_locations = []
        flet_storage = os.getenv("FLET_APP_STORAGE")
        if flet_storage:
            cache_locations.append(Path(flet_storage) / "lunalib" / "cache")

        home_dir = Path(os.path.expanduser("~"))
        if str(home_dir) not in ("", "/"):
            cache_locations.extend([
                home_dir / ".lunalib" / "cache",
                home_dir / "lunalib" / "cache",
            ])

        cache_locations.extend([
            Path("./.lunalib_cache"),
            Path("/tmp/lunalib_cache"),  # For Unix-like systems
        ])
        
        for cache_dir in cache_locations:
            try:
                cache_dir.mkdir(parents=True, exist_ok=True)
                
                # Test if we can create a file in this directory
                test_file = cache_dir / "test_write.tmp"
                with open(test_file, 'w', encoding='utf-8') as f:
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
cache_dir = Path(CACHE_DIR)

class LunaWalletApp:
    """Luna Wallet Application with Red Theme - Responsive Mobile Support"""

    def __init__(self):
        # Run network diagnostics on startup
        diagnose_network()
        
        # Initialize debug logger first
        try:
            from app.debug_logger import debug_log, get_logger
            self.debug_logger = get_logger()
            debug_log("=" * 60)
            debug_log("LunaWallet Application Starting")
            debug_log("=" * 60)
        except Exception as e:
            print(f"DEBUG: Failed to initialize debug logger: {e}")
            self.debug_logger = None
        
        self._patch_lunalib_cache()
        # Use services instead of direct lunalib
        self.wallet_service = WalletService()
        self.blockchain_service = BlockchainService()
        self.mempool_service = MempoolService()

        # Keep references for backward compatibility
        self.wallet_core = self.wallet_service.core
        self.blockchain_manager = self.blockchain_service.manager
        self.mempool_manager = self.mempool_service.manager
        
        # Initialize sound manager
        try:
            from app.sound_manager import SoundManager
            self.sound_manager = SoundManager()
        except Exception as e:
            print(f"DEBUG: Failed to initialize SoundManager: {e}")
            self.sound_manager = None

        # Initialize database
        try:
            from lunalib.storage.database import WalletDatabase
            # Use the same data directory as the wallet
            data_dir = self._get_data_directory()
            db_path = os.path.join(data_dir, "wallet.db")
            self.database = WalletDatabase(db_path=db_path)
            print(f"DEBUG: WalletDatabase initialized successfully at {db_path}")
        except Exception as e:
            print(f"DEBUG: Error initializing WalletDatabase: {e}")
            self.database = None

        self.minimized_to_tray = False
        self.current_tab_index = 0
        self.snack_bar = None
        self.selected_wallet_index = 0
        self.last_activity_time = time.time()
        self.auto_lock_minutes = 15
        self.is_locked = True
        self.is_mobile = False
        self.is_landscape = False
        self.current_layout = "desktop"
        self.sidebar_collapsed = False
        self.sidebar_width = 240
        self.sidebar_collapsed_width = 60
        
        # Initial screen state for when UI hasn't been initialized yet
        self.initial_screen_state = None

        # Refs for UI elements
        self.refs = {}

        # Initialize page references
        self.current_page = None
        self.current_lock_page = None
        self.pages = {}

        # Notification container for custom snackbar overlay
        self.notification_container = None

        # Track last scan time per wallet to avoid redundant scans (5 minute threshold)
        self.wallet_last_scan_times = {}  # {address: timestamp}
        self.scan_cooldown_minutes = 5

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
        self.initial_scan_complete = False
        self.last_scanned_block = 0
        self.wallet_balances_cache = {}  # Cache of wallet balances to detect changes
        self.scan_interval = 30  # Scan every 30 seconds
        self._inactivity_monitor_started = False

    def _register_activity(self, *_args, **_kwargs):
        """Update last activity time for inactivity auto-lock."""
        self.last_activity_time = time.time()

    def _start_inactivity_monitor(self):
        """Start background monitor to auto-lock after inactivity."""
        if self._inactivity_monitor_started:
            return
        self._inactivity_monitor_started = True

        def _monitor():
            while True:
                try:
                    time.sleep(15)
                    if self.is_locked:
                        continue
                    idle_seconds = time.time() - self.last_activity_time
                    if idle_seconds >= self.auto_lock_minutes * 60:
                        def _do_lock():
                            try:
                                self.show_snackbar("Wallet locked due to inactivity", "info")
                                self.lock_wallet()
                            except Exception as e:
                                print(f"DEBUG: Auto-lock error: {e}")
                        if hasattr(self, 'page') and self.page and hasattr(self.page, 'run_thread'):
                            self.page.run_thread(_do_lock)
                        else:
                            _do_lock()
                        self.last_activity_time = time.time()
                except Exception as e:
                    print(f"DEBUG: Inactivity monitor error: {e}")

        threading.Thread(target=_monitor, daemon=True).start()

    def show_snackbar(self, message: str, message_type: str = "info"):
        """Display a slim notification panel docked at the bottom of the window.

        Args:
            message: The message to display
            message_type: Type of message - "success" (green), "error" (red), "info" (blue)
        """
        try:
            print(f"[SNACKBAR] show_snackbar() called - message_type: {message_type}, message: {message}")
        except Exception:
            # Silently handle encoding errors in print
            print(f"[SNACKBAR] show_snackbar() called - message_type: {message_type}")

        if not hasattr(self, 'page') or not self.page:
            print(f"[SNACKBAR] No page available - printing to console")
            try:
                print(f"Snackbar: {message_type.upper()}: {message}")
            except Exception:
                print(f"Snackbar: {message_type.upper()}")
            return

        # Color mapping for different message types
        color_map = {
            "success": "#4CAF50",  # Green
            "error": "#f44336",    # Red
            "info": "#2196F3"      # Blue
        }

        bg_color = color_map.get(message_type, "#2196F3")

        try:
            print(f"[SNACKBAR] Creating slim bottom panel notification")

            # Create the notification content
            notification_content = ft.Row([
                ft.Text(
                    message,
                    color="#ffffff",
                    weight="bold",
                    size=13,
                    expand=True
                ),
                ft.IconButton(
                    ft.Icons.CLOSE,
                    icon_color="#ffffff",
                    icon_size=16,
                    on_click=lambda e: self._close_notification(notification_wrapper)
                )
            ], spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER)

            # Create the actual panel
            notification_panel = ft.Container(
                content=notification_content,
                bgcolor=bg_color,
                padding=ft.padding.symmetric(horizontal=15, vertical=8),
                height=45,
                width=float('inf')
            )

            # Wrap in a positioned container at the bottom
            notification_wrapper = ft.Container(
                content=notification_panel,
                alignment=ft.Alignment(0, 1),  # Center horizontally, bottom vertically
                bottom=0,
                left=0,
                right=0,
                animate_opacity=300
            )

            print(f"[SNACKBAR] Notification panel created")

            # Add to page overlay at bottom
            if hasattr(self.page, 'overlay'):
                print(f"[SNACKBAR] Adding to page.overlay")
                self.page.overlay.append(notification_wrapper)
                self.page.update()
                print(f"[SNACKBAR] Notification panel displayed successfully at bottom")

                # Auto-remove after 3.5 seconds if not closed manually
                def auto_close():
                    time.sleep(3.5)
                    try:
                        if notification_wrapper in self.page.overlay:
                            print(f"[SNACKBAR] Auto-closing notification")
                            self.page.overlay.remove(notification_wrapper)
                            self.page.update()
                    except Exception as e:
                        print(f"[SNACKBAR] Error in auto-close: {e}")

                threading.Thread(target=auto_close, daemon=True).start()
            else:
                print(f"[SNACKBAR] page.overlay not available")

        except Exception as e:
            print(f"[SNACKBAR] Error showing notification: {e}")
            import traceback
            traceback.print_exc()
            try:
                print(f"[SNACKBAR] Fallback: {message_type.upper()}: {message}")
            except Exception:
                print(f"[SNACKBAR] Fallback: {message_type.upper()}")

    def _close_notification(self, notification):
        """Close a notification container"""
        try:
            print(f"[SNACKBAR] Closing notification manually")
            if hasattr(self.page, 'overlay') and notification in self.page.overlay:
                self.page.overlay.remove(notification)
                self.page.update()
        except Exception as e:
            print(f"[SNACKBAR] Error closing notification: {e}")

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
            base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
            sounds_dir = os.path.join(base_dir, "assets", "sounds")
            fallback_map = {
                "transfer": "transaction",
                "reward": "transaction",
                "lock": "transaction",
                "unlock": "transaction",
            }
            sound_name = sound_type
            sound_path = os.path.join(sounds_dir, f"{sound_name}.wav")

            if not os.path.exists(sound_path) and sound_name in fallback_map:
                sound_name = fallback_map[sound_name]
                sound_path = os.path.join(sounds_dir, f"{sound_name}.wav")

            if not os.path.exists(sound_path):
                print(f"Sound file missing: {sound_path}")
                return

            # Prefer SoundManager if available (Windows winsound / platform-specific)
            if hasattr(self, 'sound_manager') and self.sound_manager:
                try:
                    if self.sound_manager.play_sound(sound_name):
                        return
                except Exception as sm_err:
                    print(f"SoundManager error: {sm_err}")

            # Fallback to Flet audio
            if not hasattr(self, 'page') or not self.page:
                return

            audio = ft.Audio(
                src=os.path.join("assets", "sounds", f"{sound_name}.wav"),
                autoplay=True,
            )
            self.page.overlay.append(audio)
            self.page.update()
        except Exception as e:
            print(f"Sound error: {e}")

    def _load_wallet_metadata(self):
        """Load basic wallet metadata from database without requiring password"""
        try:
            if not self.database:
                print("DEBUG: No database available")
                self.wallet_count = 0
                self.existing_wallet_address = None
                return

            # Get all wallet addresses from database
            wallet_addresses = self._get_all_wallet_addresses_from_db()
            self.wallet_count = len(wallet_addresses)
            
            if self.wallet_count > 0:
                self.existing_wallet_address = wallet_addresses[0]  # Use first wallet address
                print(f"DEBUG: Found {self.wallet_count} wallets in database, first address: {self.existing_wallet_address}")
            else:
                self.existing_wallet_address = None
                print("DEBUG: No wallets found in database")
                
        except Exception as e:
            print(f"DEBUG: Error loading wallet metadata from database: {e}")
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
            # Default data directories to check (don't depend on self.database being initialized)
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
            # Fallback to user home directory
            fallback_dir = os.path.join(os.path.expanduser("~"), ".luna_wallet")
            try:
                os.makedirs(fallback_dir, exist_ok=True)
                return fallback_dir
            except Exception as fallback_e:
                print(f"DEBUG: Fallback directory creation failed: {fallback_e}")
                # Last resort - use temp directory
                import tempfile
                return tempfile.mkdtemp(prefix="luna_wallet_")

    def save_wallet_data(self, force_save=False, is_backup=False):
        """Save wallet data using WalletDatabase"""
        try:
            current_time = time.time()

            # Rate limiting for normal saves
            if not force_save and not is_backup:
                if current_time - self.last_save_time < self.save_cooldown:
                    return True

            if self.is_locked and not force_save:
                print("DEBUG: Wallet is locked, skipping save (use force_save=True to override)")
                return False

            if not self.database:
                print("DEBUG: No database available, skipping save")
                return False

            # Save each wallet to database
            saved_count = 0
            if hasattr(self.wallet_core, 'wallets') and self.wallet_core.wallets:
                for address, wallet_info in self.wallet_core.wallets.items():
                    try:
                        # WalletDatabase expects the wallet data as-is
                        result = self.database.save_wallet(wallet_info)
                        if result:
                            saved_count += 1
                            print(f"DEBUG: Saved wallet {address[:12]}...")
                        else:
                            print(f"DEBUG: Failed to save wallet {address[:12]}...")
                    except Exception as e:
                        print(f"DEBUG: Error saving wallet {address[:12]}...: {e}")

            self.last_save_time = current_time
            print(f"DEBUG: Saved {saved_count} wallets to database")
            return True

        except Exception as e:
            print(f"DEBUG: Error saving wallet data: {e}")
            return False

    def _get_all_wallet_addresses_from_db(self):
        """Get all wallet addresses from the database"""
        if not self.database:
            return []
        
        try:
            import sqlite3
            conn = sqlite3.connect(self.database.db_path)
            cursor = conn.cursor()
            cursor.execute('SELECT address FROM wallets')
            addresses = [row[0] for row in cursor.fetchall()]
            conn.close()
            return addresses
        except Exception as e:
            print(f"DEBUG: Error getting wallet addresses from DB: {e}")
            return []

    def load_wallet_data(self):
        """Load wallet data from WalletDatabase"""
        try:
            if not self.database:
                print("DEBUG: No database available")
                return False

            print(f"DEBUG: Loading wallet data from database: {self.database.db_path}")

            # Get all wallet addresses from database
            wallet_addresses = self._get_all_wallet_addresses_from_db()
            if not wallet_addresses:
                print("DEBUG: No wallets found in database")
                return False

            print(f"DEBUG: Found {len(wallet_addresses)} wallets in database")

            # Load each wallet and restore to LunaWallet
            loaded_count = 0
            if hasattr(self.wallet_core, 'wallets'):
                # Clear existing wallets
                self.wallet_core.wallets = {}

                for address in wallet_addresses:
                    try:
                        wallet_data = self.database.load_wallet(address)
                        if wallet_data:
                            # Initialize balance fields if they don't exist
                            if 'confirmed_balance' not in wallet_data:
                                wallet_data['confirmed_balance'] = 0.0
                            if 'pending_balance' not in wallet_data:
                                wallet_data['pending_balance'] = 0.0
                            if 'available_balance' not in wallet_data:
                                wallet_data['available_balance'] = 0.0
                            if 'balance' not in wallet_data:
                                wallet_data['balance'] = 0.0
                            
                            # Restore to LunaWallet format
                            self.wallet_core.wallets[address] = wallet_data
                            loaded_count += 1
                            print(f"DEBUG: Loaded wallet {address[:12]}...")
                        else:
                            print(f"DEBUG: Failed to load wallet {address[:12]}...")
                    except Exception as e:
                        print(f"DEBUG: Error loading wallet {address[:12]}...: {e}")

            print(f"DEBUG: Successfully loaded {loaded_count} wallets")
            return loaded_count > 0

        except Exception as e:
            print(f"DEBUG: Error loading wallet data: {e}")
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

    def on_balance_changed(self):
        """Handle balance changes with auto-save"""
        if hasattr(self, 'wallet_page') and self.wallet_page:
            if hasattr(self.wallet_page, '_update_wallet_data_ui_only'):
                self.wallet_page._update_wallet_data_ui_only()
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
        if hasattr(self, 'wallet_page') and self.wallet_page:
            if hasattr(self.wallet_page, 'refresh_transaction_history'):
                try:
                    self.wallet_page.refresh_transaction_history()
                except Exception as e:
                    print(f"DEBUG: Error refreshing transaction history: {e}")
        self.show_snackbar("New transaction received", "success")

        # Play transaction sound
        self._play_sound("transaction")
        print("Played Transaction Sound")

        self.save_wallet_data(force_save=True)
        self.create_backup()

    def on_sync_complete(self):
        """Handle sync completion with auto-save"""
        if hasattr(self, 'wallet_page') and self.wallet_page:
            if hasattr(self.wallet_page, '_update_wallet_data_ui_only'):
                self.wallet_page._update_wallet_data_ui_only()
            if hasattr(self.wallet_page, 'refresh_transaction_history'):
                try:
                    self.wallet_page.refresh_transaction_history()
                except Exception as e:
                    print(f"DEBUG: Error refreshing transaction history: {e}")
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

        # Set icon for taskbar (use .ico on Windows for best compatibility)
        try:
            import os
            icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "wallet_icon.ico")
            if os.path.exists(icon_path):
                print(f"DEBUG: Setting icon from: {icon_path}")
                page.window.icon = icon_path
            else:
                # Try PNG as fallback
                png_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "wallet_icon.png")
                if os.path.exists(png_path):
                    print(f"DEBUG: Setting icon from: {png_path}")
                    page.window.icon = png_path
                else:
                    print(f"DEBUG: No icon file found at {icon_path} or {png_path}")
        except Exception as e:
            print(f"DEBUG: Error setting icon: {e}")
            import traceback
            traceback.print_exc()

        page.on_resize = self.on_page_resize

        # Track user activity for auto-lock
        try:
            if hasattr(page, "on_keyboard_event"):
                page.on_keyboard_event = self._register_activity
            if hasattr(page, "on_pointer_event"):
                page.on_pointer_event = self._register_activity
        except Exception as e:
            print(f"DEBUG: Failed to attach activity handlers: {e}")

        self._start_inactivity_monitor()

        # Check for existing wallets and show appropriate screen
        self.initialize_wallet_state()

        # If initialize_wallet_state stored state instead of showing UI, display it now
        if self.initial_screen_state:
            state = self.initial_screen_state
            if state['has_existing_wallets']:
                print("DEBUG: Showing stored unlock screen")
                self.show_lock_page(
                    title="Welcome Back",
                    subtitle=f"Unlock your existing wallet\n{state['existing_wallet_address']}",
                    wallet_exists=True,
                    show_create=False
                )
            else:
                print("DEBUG: Showing stored create screen")
                self.show_lock_page(
                    title="Welcome to Luna Wallet",
                    subtitle="Create your first wallet to get started",
                    show_create=True,
                    wallet_exists=False
                )

    def initialize_wallet_state(self):
        """Initialize wallet state and show appropriate screen"""
        try:
            print("=" * 50)
            print("DEBUG: Initializing wallet state...")

            # Check for existing wallets using robust detection
            has_existing_wallets = self.check_existing_wallets()

            print(f"DEBUG: Wallet detection result: {has_existing_wallets}")
            print(f"DEBUG: Existing wallet address: {self.existing_wallet_address}")

            # Store initial screen state for later use
            self.initial_screen_state = {
                'has_existing_wallets': has_existing_wallets,
                'existing_wallet_address': self.existing_wallet_address
            }

            # Only show UI if page has been initialized
            if hasattr(self, 'page') and self.page:
                if has_existing_wallets:
                    print("DEBUG: Wallets found - showing unlock screen")
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
            else:
                print("DEBUG: No UI page available - storing state for later display")
                
            print("=" * 50)

        except Exception as e:
            print(f"DEBUG: Error in initialize_wallet_state: {e}")
            import traceback
            traceback.print_exc()
            # Fallback to create wallet screen
            self.initial_screen_state = {
                'has_existing_wallets': False,
                'existing_wallet_address': None
            }
            if hasattr(self, 'page') and self.page:
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

    def show_wallet_page(self):
        """Display the main wallet page with all wallets and transactions"""
        try:
            print("[WALLET_PAGE] showing wallet page...")

            # Create the wallet page with all necessary callbacks
            wallet_page = WalletPage(
                app=self,
                on_send=self.on_send_transaction,
                on_receive=self.on_receive,
                on_export_key=self.on_export_key,
                on_lock=self.on_lock,
                on_create_wallet=self.on_create_wallet,
                on_import_wallet=self.on_import_wallet,
                on_settings=self.on_settings
            )

            # Store reference for later updates
            self.wallet_page = wallet_page

            # Set as current page
            try:
                self.current_page = wallet_page.create()
                self.show_snackbar("Wallet loaded", "success")
            except Exception as create_err:
                print(f"[WALLET_PAGE] create FAILED: {create_err}")
                import traceback
                traceback.print_exc()
                self.show_snackbar(f"Error loading wallet: {create_err}", "error")
                return

            # Clear page controls and display
            if hasattr(self, 'page') and self.page:
                # Clear both controls and overlay
                try:
                    self.page.clean()
                except Exception:
                    self.page.controls.clear()
                if hasattr(self.page, 'overlay'):
                    self.page.overlay.clear()
            
            if hasattr(self, 'page') and self.page:
                self.page.add(self.current_page)
                # Force UI refresh
                self.page.update()
                try:
                    self.page.update()
                except Exception:
                    pass
            
            print("[WALLET_PAGE] wallet page displayed")
            
        except Exception as e:
            print(f"[WALLET_PAGE] ERROR: {e}")
            import traceback
            traceback.print_exc()
            raise

    def lock_wallet(self):
        """Lock the wallet and return to lock screen"""
        print("DEBUG: lock_wallet called")
        self.is_locked = True
        self.continuous_scan_active = False  # Stop continuous scanning
        self._play_sound("lock")
        self.show_lock_page(
            title="Wallet Locked",
            subtitle="Enter password to unlock",
            wallet_exists=True,
            show_create=False
        )

    def on_send_transaction(self):
        """Handle send transaction action"""
        print("DEBUG: on_send_transaction called")
        send_page = SendPage(
            self,
            on_back=self.show_wallet_page,
            on_send_complete=self.on_transaction_sent
        )
        self.current_page = send_page.create()
        self.page.controls.clear()
        self.page.add(self.current_page)
        self.page.update()
        print("DEBUG: Send page displayed")

    def on_receive(self):
        """Handle receive action"""
        print("DEBUG: on_receive called")
        receive_page = ReceivePage(
            self,
            on_back=self.show_wallet_page
        )
        self.current_page = receive_page.create()
        self.page.controls.clear()
        self.page.add(self.current_page)
        self.page.update()
        print("DEBUG: Receive page displayed")

    def on_export_key(self):
        """Handle export key action"""
        print("DEBUG: on_export_key called")
        export_key_page = ExportKeyPage(
            self,
            on_back=self.show_wallet_page
        )
        self.current_page = export_key_page.create()
        self.page.controls.clear()
        self.page.add(self.current_page)
        self.page.update()
        print("DEBUG: Export key page displayed")

    def on_transaction_sent(self):
        """Handle transaction sent confirmation"""
        print("DEBUG: on_transaction_sent called")
        self.show_snackbar("Transaction sent successfully!", "success")
        self._play_sound("send")
        # Return to wallet page
        self.show_wallet_page()

    def on_lock(self):
        """Handle lock action - lock the wallet"""
        print("DEBUG: on_lock called")
        self.is_locked = True
        self._play_sound("lock")
        self.show_lock_page(
            title="Wallet Locked",
            subtitle="Enter password to unlock",
            wallet_exists=True,
            show_create=False
        )

    def on_create_wallet(self):
        """Handle create wallet action"""
        print("DEBUG: on_create_wallet called")
        self.show_create_wallet()

    def on_import_wallet(self):
        """Handle import wallet action"""
        print("DEBUG: on_import_wallet called")
        from gui.page_import_wallet import ImportWalletPage
        import_page = ImportWalletPage(
            self,
            on_back=self.show_wallet_page,
            on_wallet_imported=self.refresh_wallet_list
        )
        self.current_page = import_page.create()
        self.page.controls.clear()
        self.page.add(self.current_page)
        self.page.update()

    def show_import_wallet(self):
        """Show import wallet page from lock screen"""
        print("DEBUG: show_import_wallet called")
        from gui.page_import_wallet import ImportWalletPage
        import_page = ImportWalletPage(
            self,
            on_back=self.initialize_wallet_state,  # Go back to lock/create screen
            on_wallet_imported=self.initialize_wallet_state  # Re-check wallet state after import
        )
        self.current_page = import_page.create()
        self.page.controls.clear()
        self.page.add(self.current_page)
        self.page.update()

    def refresh_wallet_list(self):
        """Refresh the wallet list after a new wallet is created."""
        print("DEBUG: refresh_wallet_list called")
        try:
            # Return to wallet page and refresh the sidebar
            if hasattr(self, 'wallet_page') and self.wallet_page:
                # Refresh sidebar wallets
                if hasattr(self.wallet_page, '_refresh_sidebar_wallets'):
                    self.wallet_page._refresh_sidebar_wallets()
                    print("DEBUG: Sidebar wallets refreshed")
            
            # Show the wallet page
            self.show_wallet_page()
        except Exception as e:
            print(f"DEBUG: Error refreshing wallet list: {e}")
            import traceback
            traceback.print_exc()

    def on_settings(self):
        """Handle settings action"""
        print("DEBUG: on_settings called")
        self.show_snackbar("Settings feature", "info")

    def unlock_wallet(self, password):
        """Unlock existing wallet with password using LunaWallet core methods"""
        try:
            print("[UNLOCK] Starting unlock process...")

            def _trace(msg: str):
                try:
                    home = os.path.expanduser('~')
                    log_dir = os.path.join(home, 'LunaWallet_Logs')
                    os.makedirs(log_dir, exist_ok=True)
                    log_path = os.path.join(log_dir, 'unlock_trace.log')
                    with open(log_path, 'a', encoding='utf-8') as f:
                        f.write(msg + "\n")
                except Exception:
                    pass
            
            # Show loading immediately
            if hasattr(self, 'current_lock_page') and self.current_lock_page:
                self.current_lock_page.show_loading()
            
            # Do the actual unlock work
            print("[UNLOCK] Loading wallet data from database...")
            load_success = self.load_wallet_data()
            
            if not load_success:
                print("[UNLOCK] Failed to load wallet data")
                self.show_snackbar("Failed to load wallet data", "error")
                if hasattr(self, 'current_lock_page') and self.current_lock_page:
                    self.current_lock_page.hide_loading()
                return
            
            print("[UNLOCK] Attempting to unlock with core method...")
            success = False
            
            # Try to unlock each wallet
            if hasattr(self.wallet_core, 'wallets') and self.wallet_core.wallets:
                for wallet_address in self.wallet_core.wallets.keys():
                    unlock_success = self.wallet_core.unlock_wallet(wallet_address, password)
                    if unlock_success:
                                    # Ensure balance fields exist
                        wallet_obj = self.wallet_core.wallets.get(wallet_address)
                        if wallet_obj:
                            for field in ['available_balance', 'confirmed_balance', 'pending_balance', 'balance']:
                                if field not in wallet_obj:
                                    wallet_obj[field] = 0.0
                        
                        # Switch to wallet
                        self.wallet_core.switch_wallet(wallet_address)
                        success = True
                        break
            
            # Hide loading
            if hasattr(self, 'current_lock_page') and self.current_lock_page:
                self.current_lock_page.hide_loading()
            
            if success:
                print("[UNLOCK] Wallet unlocked successfully")
                _global_trace("Wallet unlocked successfully", "UNLOCK")
                self.is_locked = False
                self._play_sound("unlock")
                
                # Save wallet state
                self.save_wallet_data(force_save=True)
                _global_trace("Wallet state saved", "UNLOCK")
                
                # Show success message
                self.show_snackbar("Wallet unlocked successfully", "success")
                
                # Clear lock page reference
                self.current_lock_page = None
                
                # Transition to wallet page
                try:
                    self.show_wallet_page()
                    _global_trace("Wallet page displayed", "UNLOCK")
                except Exception as page_error:
                    print(f"[UNLOCK] show_wallet_page() failed: {page_error}")
                    _global_trace(f"Wallet page failed: {page_error}", "UNLOCK_ERROR")
                    import traceback
                    traceback.print_exc()
                    raise

                # START INITIAL SCAN after wallet page is shown
                self.start_initial_blockchain_scan()

                # Update page
                if hasattr(self, 'page') and self.page:
                    try:
                        self.page.update()
                    except Exception as upd_err:
                        print(f"[UNLOCK] page.update failed: {upd_err}")
            else:
                print("[UNLOCK] Unlock failed - wrong password")
                self.show_snackbar("Failed to unlock wallet - wrong password", "error")
        
        except Exception as e:
            print(f"[UNLOCK] ERROR: {e}")
            import traceback
            traceback.print_exc()
            self.show_snackbar(f"Unlock error: {str(e)}", "error")
            if hasattr(self, 'current_lock_page') and self.current_lock_page:
                self.current_lock_page.hide_loading()

    def start_initial_blockchain_scan(self):
        """
        Performs the initial, one-time, full blockchain scan.
        This should only run once after the wallet is unlocked.
        """
        if self.initial_scan_complete:
            print("DEBUG: Initial scan already completed. Skipping.")
            return

        print("DEBUG: Starting initial blockchain scan...")

        def initial_scan_thread():
            try:
                # Show loading indicator on the wallet page
                if hasattr(self, 'wallet_page') and self.wallet_page:
                    if hasattr(self.wallet_page, 'show_loading'):
                        self.page.run_thread(self.wallet_page.show_loading, "Syncing Blockchain...")

                # Perform the full scan
                wallet_addresses = list(self.wallet_core.wallets.keys())
                if wallet_addresses:
                    self._update_scan_loading("Connecting to node...")
                    latest_block = self.blockchain_manager.get_latest_block()
                    latest_height = latest_block.get('index', 0) if latest_block else 0
                    self._update_scan_loading(f"Scanning Transactions (0-{latest_height})...")
                    self._perform_full_blockchain_scan(wallet_addresses, latest_height)
                    self.last_scanned_block = latest_height
                    self._update_scan_loading("Processing results...")
                
                self.initial_scan_complete = True
                print("DEBUG: Initial blockchain scan COMPLETED.")

                # Hide loading indicator
                if hasattr(self, 'wallet_page') and self.wallet_page:
                    if hasattr(self.wallet_page, 'hide_loading'):
                        self.page.run_thread(self.wallet_page.hide_loading)

                # Now, start the continuous background scan for new blocks
                self.start_continuous_blockchain_scan()

            except Exception as e:
                print(f"DEBUG: Error during initial blockchain scan: {e}")
                import traceback
                traceback.print_exc()
                # Ensure loading indicator is hidden on error
                if hasattr(self, 'wallet_page') and self.wallet_page:
                    if hasattr(self.wallet_page, 'hide_loading'):
                        self.page.run_thread(self.wallet_page.hide_loading)

        threading.Thread(target=initial_scan_thread, daemon=True).start()

    def _update_scan_loading(self, text):
        """Update scan overlay text without toggling visibility."""
        try:
            if hasattr(self, 'wallet_page') and self.wallet_page:
                if hasattr(self.wallet_page, 'show_loading'):
                    if hasattr(self, 'page') and self.page and hasattr(self.page, 'run_thread'):
                        self.page.run_thread(self.wallet_page.show_loading, text)
                    else:
                        self.wallet_page.show_loading(text)
        except Exception as e:
            print(f"DEBUG: Error updating scan loading text: {e}")

    def show_create_wallet(self):
        """Display the wallet creation page or dialog."""
        print("DEBUG: show_create_wallet called")
        # Example implementation: Navigate to the wallet creation page
        from gui.page_create_wallet import CreateWalletPage
        create_wallet_page = CreateWalletPage(
            self,
            on_back=self.show_wallet_page,
            on_wallet_created=self.refresh_wallet_list
        )
        self.current_page = create_wallet_page.create()

        # Clear and add the new page to the UI
        self.page.controls.clear()
        self.page.controls.append(self.current_page)
        self.page.update()

    def update_refs(self):
            """Update all UI references"""
            if hasattr(self, 'page') and self.page:
                self.page.update()

    def scan_all_wallets_for_changes(self, force_full_scan=False):
        """
        Scan wallets for transactions.
        - If force_full_scan=True: Do complete blockchain scan from start, cache results, then update all balances
        - Otherwise: Only check for NEW transactions since last scan, update balances when new found
        """
        show_ready = threading.Event()

        def _show_scan_loading():
            try:
                if hasattr(self, 'wallet_page') and self.wallet_page:
                    def _do_show():
                        try:
                            self.wallet_page.show_loading("Scanning Transactions...")
                        finally:
                            show_ready.set()

                    if hasattr(self, 'page') and self.page and hasattr(self.page, 'run_thread'):
                        self.page.run_thread(_do_show)
                    else:
                        _do_show()
                else:
                    show_ready.set()
            except Exception as e:
                print(f"DEBUG: Error showing scan loading: {e}")
                show_ready.set()

        def _hide_scan_loading():
            try:
                if hasattr(self, 'wallet_page') and self.wallet_page:
                    self.wallet_page.hide_loading()
            except Exception as e:
                print(f"DEBUG: Error hiding scan loading: {e}")

        start_time = time.time()
        try:
            _show_scan_loading()
            try:
                show_ready.wait(timeout=0.3)
            except Exception:
                pass
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
        finally:
            try:
                elapsed = time.time() - start_time
                min_visible = 0.5
                if elapsed < min_visible:
                    time.sleep(min_visible - elapsed)
            except Exception:
                pass
            _hide_scan_loading()

    def _perform_full_blockchain_scan(self, wallet_addresses, latest_height):
        """Perform complete blockchain scan from genesis using batch API"""
        try:
            print(f"DEBUG: Starting full blockchain scan using batch API (0 to {latest_height})")
            self._update_scan_loading(f"Scanning Transactions (multi-scan 0-{latest_height})...")
            
            # Use new batch method: scan_transactions_for_addresses(addresses: List[str])
            # Returns Dict[str, List[Dict]] where keys are addresses
            print(f"[OK] Using batch scan_transactions_for_addresses() for {len(wallet_addresses)} wallets")
            all_transactions = self.blockchain_manager.scan_transactions_for_addresses(wallet_addresses)
            self._update_scan_loading("Processing scanned transactions...")
            
            # ALSO get sent transactions for each wallet, as scan_transactions_for_addresses might only get incoming
            for wallet_addr in wallet_addresses:
                try:
                    sent_txs = self.blockchain_manager.get_sent_transactions(wallet_addr)
                    if sent_txs:
                        print(f"DEBUG: Found {len(sent_txs)} sent transactions for {wallet_addr[:12]}")
                        # Add these to the all_transactions dict if not already present
                        wallet_addr_lower = wallet_addr.lower()
                        if wallet_addr_lower not in all_transactions:
                            all_transactions[wallet_addr_lower] = []
                        
                        existing_tx_ids = {tx.get('transaction_id') for tx in all_transactions[wallet_addr_lower]}
                        for tx in sent_txs:
                            if tx.get('transaction_id') not in existing_tx_ids:
                                all_transactions[wallet_addr_lower].append(tx)
                except Exception as e:
                    print(f"DEBUG: Error getting sent transactions for {wallet_addr[:12]}: {e}")

            # Process transactions for each wallet
            wallet_txs_count = {addr: {'reward': 0, 'transfer': 0, 'other': 0} for addr in wallet_addresses}
                
            for wallet_addr in wallet_addresses:
                wallet_addr_lower = wallet_addr.lower()
                wallet_txs = all_transactions.get(wallet_addr_lower, []) or all_transactions.get(wallet_addr, [])
                    
                print(f"\n📨 Processing {len(wallet_txs)} transactions for {wallet_addr[:12]}...")
                    
                for tx in wallet_txs:
                    # Normalize sender/receiver fields so outgoing is counted correctly
                    if not tx.get('from'):
                        tx['from'] = tx.get('from_address') or tx.get('sender') or tx.get('sender_address') or ''
                    if not tx.get('to'):
                        tx['to'] = tx.get('to_address') or tx.get('receiver') or tx.get('recipient') or ''
                    if not tx.get('hash'):
                        tx['hash'] = tx.get('transaction_id') or ''

                    tx_type = tx.get('type', 'transfer').lower()
                    block_height = tx.get('block_height', 0)
                        
                    # Save transaction with proper status (per-wallet unique hash)
                    tx['status'] = 'confirmed'
                    if hasattr(self, 'database'):
                        tx_copy = dict(tx)
                        base_hash = tx_copy.get('hash') or tx_copy.get('transaction_id') or ''
                        tx_copy['hash'] = f"{base_hash}_{wallet_addr}" if base_hash else wallet_addr
                        self.database.save_transaction(tx_copy, wallet_addr)
                        
                        # **IMPORTANT**: For incoming transfers, also save for the RECEIVER
                        if tx_type == 'transfer':
                            tx_to = (tx.get('to') or tx.get('to_address') or '').lower()
                            wallet_addr_lower = wallet_addr.lower()
                            # If this wallet is the sender, also save it for the receiver
                            if tx_to and tx_to != wallet_addr_lower:
                                # Find if the receiver wallet is in our wallet list
                                for check_wallet in wallet_addresses:
                                    if check_wallet.lower() == tx_to:
                                        tx_copy_receiver = dict(tx)
                                        base_hash = tx_copy_receiver.get('hash') or tx_copy_receiver.get('transaction_id') or ''
                                        tx_copy_receiver['hash'] = f"{base_hash}_{check_wallet}" if base_hash else check_wallet
                                        self.database.save_transaction(tx_copy_receiver, check_wallet)
                                        print(f"  → Saved outgoing transaction for receiver: {check_wallet[:12]}...")
                                        break
                        
                    # Update balance incrementally
                    self._update_wallet_balance_incremental(wallet_addr, tx)
                        
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
            
            # Check mempool for ALL pending transactions at once
            self._check_mempool_for_pending(wallet_addresses)
            
            # Detect new incoming transactions and play sound
            self._detect_new_incoming_transactions(wallet_addresses)
            
            # Refresh UI after full scan complete
            self._refresh_ui_after_scan(force_update=True)
            
        except Exception as e:
            print(f"DEBUG: Error in _perform_full_blockchain_scan: {e}")
            import traceback
            traceback.print_exc()

    def _perform_incremental_scan(self, wallet_addresses, start_height, latest_height):
        """Perform incremental scan for only NEW transactions since last scan using batch API"""
        try:
            print(f"DEBUG: Incremental scan from block {start_height} to {latest_height}")
            new_transactions_found = False
            
            wallet_txs_count = {addr: {'reward': 0, 'transfer': 0, 'other': 0} for addr in wallet_addresses}
            
            # Use new batch method to scan all wallets at once
            print(f"✓ Using batch scan_transactions_for_addresses() for new blocks {start_height}-{latest_height}")
            all_transactions = self.blockchain_manager.scan_transactions_for_addresses(
                wallet_addresses,
                start_height=start_height,
                end_height=latest_height
            )

            # ALSO fetch sent transactions for each wallet in this height range
            for wallet_addr in wallet_addresses:
                try:
                    sent_txs = self.blockchain_manager.get_sent_transactions(
                        wallet_addr,
                        start_height=start_height,
                        end_height=latest_height
                    )
                    if sent_txs:
                        wallet_addr_lower = wallet_addr.lower()
                        if wallet_addr_lower not in all_transactions:
                            all_transactions[wallet_addr_lower] = []

                        existing_tx_ids = {
                            tx.get('transaction_id') or tx.get('hash')
                            for tx in all_transactions[wallet_addr_lower]
                        }
                        for tx in sent_txs:
                            tx_id = tx.get('transaction_id') or tx.get('hash')
                            if tx_id and tx_id not in existing_tx_ids:
                                all_transactions[wallet_addr_lower].append(tx)
                except Exception as e:
                    print(f"DEBUG: Error getting sent transactions for {wallet_addr[:12]}: {e}")
                
            for wallet_addr in wallet_addresses:
                wallet_addr_lower = wallet_addr.lower()
                wallet_txs = all_transactions.get(wallet_addr_lower, []) or all_transactions.get(wallet_addr, [])
                    
                if wallet_txs:
                    new_transactions_found = True
                    print(f"\n📨 Processing {len(wallet_txs)} transactions for {wallet_addr[:12]}...")
                        
                    for tx in wallet_txs:
                        # Normalize sender/receiver fields so outgoing is counted correctly
                        if not tx.get('from'):
                            tx['from'] = tx.get('from_address') or tx.get('sender') or tx.get('sender_address') or ''
                        if not tx.get('to'):
                            tx['to'] = tx.get('to_address') or tx.get('receiver') or tx.get('recipient') or ''
                        if not tx.get('hash'):
                            tx['hash'] = tx.get('transaction_id') or ''

                        tx_type = tx.get('type', 'transfer').lower()
                        block_height = tx.get('block_height', 0)

                        # Save transaction with proper status (per-wallet unique hash)
                        tx['status'] = 'confirmed'
                        if hasattr(self, 'database'):
                            tx_copy = dict(tx)
                            base_hash = tx_copy.get('hash') or tx_copy.get('transaction_id') or ''
                            tx_copy['hash'] = f"{base_hash}_{wallet_addr}" if base_hash else wallet_addr
                            self.database.save_transaction(tx_copy, wallet_addr)

                            # For transfers, also save for the receiver if we own it
                            if tx_type == 'transfer':
                                tx_to = (tx.get('to') or tx.get('to_address') or '').lower()
                                wallet_addr_lower = wallet_addr.lower()
                                if tx_to and tx_to != wallet_addr_lower:
                                    for check_wallet in wallet_addresses:
                                        if check_wallet.lower() == tx_to:
                                            tx_copy_receiver = dict(tx)
                                            base_hash = tx_copy_receiver.get('hash') or tx_copy_receiver.get('transaction_id') or ''
                                            tx_copy_receiver['hash'] = f"{base_hash}_{check_wallet}" if base_hash else check_wallet
                                            self.database.save_transaction(tx_copy_receiver, check_wallet)
                                            print(f"  → Saved outgoing transaction for receiver: {check_wallet[:12]}...")
                                            break

                        # Update balance incrementally
                        self._update_wallet_balance_incremental(wallet_addr, tx)
                        
                        # Count by type
                        if tx_type == 'reward':
                            wallet_txs_count[wallet_addr]['reward'] += 1
                            _safe_print(f"  [REWARD] {tx.get('amount')} LKC @ block {block_height}")
                        elif tx_type == 'fee_distribution':
                            wallet_txs_count[wallet_addr]['other'] += 1
                        else:
                            wallet_txs_count[wallet_addr]['transfer'] += 1
                            _safe_print(f"  [TXN] Found transaction in block {block_height} for {wallet_addr[:12]}...")
            
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
            
            # Only update UI - balances already updated incrementally
            if new_transactions_found:
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
                        
                        # Update balance incrementally for pending transaction
                        self._update_wallet_balance_incremental(wallet_addr, tx)
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
                                
                                # Update balance incrementally for pending transaction
                                self._update_wallet_balance_incremental(wallet_addr, tx)
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
                            if tx_type == 'reward' or tx_type == 'fee_distribution':
                                self._play_sound("reward")
                            elif tx_type == 'transfer':
                                self._play_sound("transfer")
                            else:
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
            # Use Flet audio for mobile/Desktop compatibility
            self._play_sound("transaction")
        except Exception as e:
            print(f"Error playing sound: {e}")

    def _update_wallet_balance_incremental(self, wallet_addr, tx):
        """Update a wallet's balance incrementally when a new transaction is found"""
        if wallet_addr not in self.wallet_core.wallets:
            return
            
        wallet_obj = self.wallet_core.wallets[wallet_addr]
        tx_type = tx.get('type', tx.get('tx_type', 'transfer')).lower()
        amount = float(tx.get('amount', 0))
        fee = float(tx.get('fee', 0))
        tx_from = tx.get('from', tx.get('from_address', '')).lower()
        tx_to = tx.get('to', tx.get('to_address', '')).lower()
        reward_addr = tx.get('reward_address', '').lower()
        recipient_addr = tx.get('recipient', '').lower()
        wallet_addr_lower = wallet_addr.lower()
        tx_status = tx.get('status', 'confirmed').lower()
        
        # Initialize balance keys if they don't exist
        if 'confirmed_balance' not in wallet_obj:
            wallet_obj['confirmed_balance'] = 0.0
        if 'pending_balance' not in wallet_obj:
            wallet_obj['pending_balance'] = 0.0
        if 'available_balance' not in wallet_obj:
            wallet_obj['available_balance'] = 0.0
        
        # Handle confirmed vs pending transactions differently
        if tx_status == 'confirmed':
            # Update confirmed balance based on transaction type
            if tx_type == 'reward':
                if (tx_to == wallet_addr_lower or reward_addr == wallet_addr_lower):
                    wallet_obj['confirmed_balance'] += amount
                    print(f"  ✓ Incremental: +{amount} reward")
            elif tx_type == 'fee_distribution':
                if (tx_to == wallet_addr_lower or reward_addr == wallet_addr_lower or recipient_addr == wallet_addr_lower):
                    wallet_obj['confirmed_balance'] += amount
                    print(f"  ✓ Incremental: +{amount} fee distribution")
            elif tx_to == wallet_addr_lower:
                wallet_obj['confirmed_balance'] += amount
                print(f"  ✓ Incremental: +{amount} transfer in")
            elif tx_from == wallet_addr_lower:
                wallet_obj['confirmed_balance'] -= (amount + fee)
                print(f"  ✓ Incremental: -{amount} -{fee} transfer out")
        elif tx_status == 'pending':
            # Update pending balance for unconfirmed transactions
            if tx_to == wallet_addr_lower:
                wallet_obj['pending_balance'] += amount
                print(f"  ⏳ Incremental: +{amount} pending in")
            elif tx_from == wallet_addr_lower:
                wallet_obj['pending_balance'] -= (amount + fee)
                print(f"  ⏳ Incremental: -{amount} -{fee} pending out")
        
        # Update total balance
        wallet_obj['available_balance'] = max(0.0, wallet_obj['confirmed_balance'])
        wallet_obj['balance'] = max(0.0, wallet_obj['confirmed_balance']) + wallet_obj['pending_balance']

    def _refresh_ui_after_scan(self, force_update=False):
        """Refresh UI after scan - must be called from scanning thread, schedules on main thread"""
        if not hasattr(self, 'page') or not self.page:
            return
        
        print(f"\n=== SCHEDULING UI REFRESH (from scan) ===")
        
        def update_ui():
            try:
                print(f">>> UI REFRESH STARTING (on main thread)")
                
                if hasattr(self, 'wallet_page') and self.wallet_page:
                    # FIRST: Refresh sidebar structure (rebuild list)
                    print(f">>> [1] Refreshing sidebar wallets structure...")
                    if hasattr(self.wallet_page, '_refresh_sidebar_wallets'):
                        self.wallet_page._refresh_sidebar_wallets()

                    # SECOND: Update all sidebar wallet balances (after structure refresh)
                    print(f">>> [2] Updating all sidebar wallet balances...")
                    if hasattr(self.wallet_page, 'update_all_sidebar_wallets_after_scan'):
                        self.wallet_page.update_all_sidebar_wallets_after_scan()

                    # THIRD: Update active wallet's balance card
                    print(f">>> [3] Recalculating balance from all transactions...")
                    if hasattr(self.wallet_page, 'recalculate_wallet_balances'):
                        if hasattr(self.wallet_core, 'current_wallet_address'):
                            self.wallet_page.recalculate_wallet_balances(self.wallet_core.current_wallet_address)
                    
                    print(f">>> [4] Updating balance card...")
                    if hasattr(self.wallet_page, '_update_wallet_data_ui_only'):
                        self.wallet_page._update_wallet_data_ui_only()
                
                print(f">>> [5] Updating transaction history...")
                if hasattr(self.wallet_page, 'refresh_transaction_history'):
                    try:
                        self.wallet_page.refresh_transaction_history()
                    except Exception as e:
                        print(f"DEBUG: Error refreshing transaction history: {e}")
                
                print(f">>> [6] Calling page.update()...")
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
            # Wait a bit before starting the loop to let the initial scan finish
            time.sleep(self.scan_interval)
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

if __name__ == "__main__":
    ft.app(target=LunaWalletApp().create_main_ui)

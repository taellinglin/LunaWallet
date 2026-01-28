# app/core.py

import flet as ft
import gui.page_create_wallet
import threading
import time
import os
import json
import shutil
import re
from datetime import datetime
import base64
from typing import Dict, List, Optional
import sys
from pathlib import Path

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
from gui.icon_utils import feather_icon

# Import utils
from utils import format_address, format_balance, format_timestamp, get_transaction_color, get_transaction_icon


def _prefer_venv_site_packages():
    """Ensure .venv site-packages take precedence over repo root for imports."""
    try:
        repo_root = str(Path(__file__).resolve().parents[1])
        venv_site = str(Path(repo_root) / ".venv" / "Lib" / "site-packages")
        if os.path.isdir(venv_site):
            sys.path = [p for p in sys.path if p not in (venv_site, repo_root)]
            sys.path.insert(0, venv_site)
            sys.path.insert(1, repo_root)
    except Exception:
        pass


def _strip_emoji_prefix(message: str) -> str:
    try:
        msg = (message or "").lstrip()
        msg = re.sub(
            r"^[\u2190-\u21FF\u2600-\u26FF\u2700-\u27BF\U0001F300-\U0001FAFF]+\s*",
            "",
            msg,
        )
        return msg
    except Exception:
        return message


def _bootstrap_ca_bundle():
    """Ensure CA bundle env vars are set to a string at import time."""
    try:
        ca_path = None
        try:
            from certifi import where

            ca_path = where()
        except Exception:
            ca_path = None

        if not ca_path:
            try:
                import ssl

                ca_path = ssl.get_default_verify_paths().cafile
            except Exception:
                ca_path = None

        if not ca_path:
            try:
                base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
                local_bundle = os.path.join(base_dir, "certifi", "cacert.pem")
                if os.path.exists(local_bundle) and os.path.getsize(local_bundle) > 0:
                    ca_path = local_bundle
            except Exception:
                ca_path = None

        if ca_path and os.path.exists(ca_path):
            os.environ["REQUESTS_CA_BUNDLE"] = ca_path
            os.environ["SSL_CERT_FILE"] = ca_path
        else:
            os.environ.pop("REQUESTS_CA_BUNDLE", None)
            os.environ.pop("SSL_CERT_FILE", None)
    except Exception:
        os.environ.pop("REQUESTS_CA_BUNDLE", None)
        os.environ.pop("SSL_CERT_FILE", None)


_prefer_venv_site_packages()
_bootstrap_ca_bundle()

# Import lunalib components
from lunalib.core.wallet import LunaWallet
from lunalib.core.blockchain import BlockchainManager
from lunalib.transactions.transactions import TransactionManager
from lunalib.storage.encryption import EncryptionManager
from app.storage import Storage, is_web

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
            
            # Requests診断は削除（lunalibのみ使用）
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
            from app.debug_logger import debug_log, get_logger, install_exception_hooks
            self.debug_logger = get_logger()
            install_exception_hooks()
            debug_log("=" * 60)
            debug_log("LunaWallet Application Starting")
            debug_log("=" * 60)
        except Exception as e:
            print(f"DEBUG: Failed to initialize debug logger: {e}")
            self.debug_logger = None
        
        self._log_runtime_crypto_info()
        self.wallet_state_manager = self._ensure_wallet_state_manager()
        self._wallet_manager_sync_started = False
        # Defer service initialization to avoid startup hangs
        self.wallet_service = None
        self.blockchain_service = None
        self.mempool_service = None
        self.wallet_core = None
        self.blockchain_manager = None
        self.mempool_manager = None
        self._services_ready = False
        self._inactivity_monitor_started = False
        self._is_closing = False
        # Initialize sound manager
        self.sound_enabled = True  # サウンドを明示的に有効化
        print(f"[SOUND] sound_enabled = {self.sound_enabled}")
        try:
            from app.sound_manager import SoundManager
            self.sound_manager = SoundManager()
        except Exception as e:
            print(f"DEBUG: Failed to initialize SoundManager: {e}")
            self.sound_manager = None

        # Initialize storage (web: browser storage, desktop: sqlite3)
        try:
            if is_web():
                self.storage = Storage()
                print("DEBUG: BrowserStorage initialized for web")
            else:
                data_dir = self._get_data_directory()
                db_path = os.path.join(data_dir, "wallet.db")
                self.storage = Storage()
                print(f"DEBUG: SQLiteStorage initialized at {db_path}")
        except Exception as e:
            print(f"DEBUG: Error initializing Storage: {e}")
            self.storage = None

        # Apply runtime settings stored in Storage (e.g., decimals, sync URL)
        try:
            self._apply_runtime_settings_from_storage()
        except Exception as e:
            print(f"DEBUG: Failed to apply runtime settings: {e}")

        try:
            from app.debug_logger import debug_log
            storage_type = "BrowserStorage" if is_web() else "SQLiteStorage"
            flet_storage = os.getenv("FLET_APP_STORAGE")
            debug_log(f"[STORAGE] type={storage_type} data_dir={self._get_data_directory()} flet_storage={flet_storage}")
            try:
                import lunalib
                pkg_version = None
                try:
                    from importlib.metadata import version as _pkg_version
                    pkg_version = _pkg_version("lunalib")
                except Exception:
                    pkg_version = None
                debug_log(f"[LUNALIB] __version__={getattr(lunalib, '__version__', 'unknown')} installed={pkg_version or 'unknown'}")
                ver = pkg_version or getattr(lunalib, '__version__', '0')
                def _parse_ver(v):
                    parts = []
                    for p in str(v).split('.'):
                        try:
                            parts.append(int(''.join(ch for ch in p if ch.isdigit()) or 0))
                        except Exception:
                            parts.append(0)
                    return tuple(parts)
                if pkg_version and getattr(lunalib, '__version__', None) and pkg_version != getattr(lunalib, '__version__'):
                    debug_log(f"[LUNALIB][WARN] version mismatch: __version__={getattr(lunalib, '__version__')} installed={pkg_version}")
                if _parse_ver(ver) < (1, 9, 3):
                    debug_log("[LUNALIB][WARN] version < 1.9.3 detected; build may miss pending/scan behavior")
            except Exception:
                pass
        except Exception:
            pass

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
        self.ui_scan_interval_seconds = 300  # 5 minutes between UI-triggered scans
        self.last_ui_scan_time = 0
        self.integrity_base_url = os.getenv("INTEGRITY_BASE_URL", "https://linglin.art/blockchain")
        self.integrity_check_interval_seconds = 300  # 5 minutes
        self.last_integrity_check_time = 0
        self._inactivity_monitor_started = False
        self.start_blockchain_monitor()
    def start_blockchain_monitor(self, interval=10):
        """Start a background thread to monitor blockchain changes every `interval` seconds.
        改良版: キャッシュが遅れている場合もすべてのブロックを順次処理する。"""
        import threading, time
        def monitor():
            last_height = None
            while True:
                try:
                    if hasattr(self, 'blockchain_manager') and self.blockchain_manager:
                        latest_block = self.blockchain_manager.get_latest_block()
                        latest_height = latest_block.get('index', 0) if latest_block else 0
                        if last_height is None:
                            # 初回は最新ブロックで初期化（catch-upはしない）
                            last_height = latest_height
                        elif latest_height > last_height:
                            print(f"[MONITOR] Blockchain changed: {last_height} -> {latest_height}")
                            # すべての未処理ブロックを順次処理
                            for h in range(last_height + 1, latest_height + 1):
                                try:
                                    self.handle_blockchain_update(h - 1, h)
                                except Exception as e:
                                    print(f"[MONITOR] Error processing block {h}: {e}")
                            last_height = latest_height
                except Exception as e:
                    print(f"[MONITOR] Error: {e}")
                time.sleep(interval)
        threading.Thread(target=monitor, daemon=True).start()

    def handle_blockchain_update(self, old_height, new_height):
        """Download/process new blocks or transactions. Customize as needed."""
        print(f"[MONITOR] Handling blockchain update from {old_height} to {new_height}")
        # Add your download/processing logic here
    def _register_activity(self, *_args, **_kwargs):
        """Update last activity time for inactivity auto-lock."""
        self.last_activity_time = time.time()

    def _ensure_ca_bundle(self):
        """Ensure requests has a valid CA bundle path."""
        try:
            ca_path = None
            try:
                from certifi import where

                ca_path = where()
            except Exception:
                ca_path = None

            if not ca_path:
                try:
                    import ssl

                    ca_path = ssl.get_default_verify_paths().cafile
                except Exception:
                    ca_path = None

            if not ca_path:
                try:
                    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
                    local_bundle = os.path.join(base_dir, "certifi", "cacert.pem")
                    if os.path.exists(local_bundle) and os.path.getsize(local_bundle) > 0:
                        ca_path = local_bundle
                except Exception:
                    ca_path = None

            if ca_path and os.path.exists(ca_path):
                os.environ["REQUESTS_CA_BUNDLE"] = ca_path
                os.environ["SSL_CERT_FILE"] = ca_path
            else:
                # Avoid NoneType path usage in downstream libs
                os.environ.pop("REQUESTS_CA_BUNDLE", None)
                os.environ.pop("SSL_CERT_FILE", None)
        except Exception as e:
            print(f"DEBUG: Failed to set CA bundle: {e}")

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
            "info": "#2196F3",     # Blue
            "warning": "#ff9800",  # Amber
        }

        icon_map = {
            "success": "check-circle",
            "error": "x-circle",
            "info": "info",
            "warning": "alert-triangle",
        }

        bg_color = color_map.get(message_type, "#2196F3")
        icon_name = icon_map.get(message_type, "info")
        display_message = _strip_emoji_prefix(message)

        try:
            print(f"[SNACKBAR] Creating slim bottom panel notification")

            # Create the notification content
            notification_content = ft.Row([
                feather_icon(icon_name, size=16, color="#ffffff"),
                ft.Text(
                    display_message,
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
                padding=ft.Padding.symmetric(horizontal=15, vertical=8),
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


    def _log_runtime_crypto_info(self):
        """Log crypto and lunalib runtime info for built unlock diagnostics."""
        try:
            from app.debug_logger import debug_log
            import sys

            debug_log(f"[CRYPTO] sys.path[0:5]={sys.path[:5]}")

            try:
                import lunalib
                debug_log(f"[CRYPTO] lunalib.__file__={getattr(lunalib, '__file__', 'unknown')}")
                debug_log(f"[CRYPTO] lunalib.__version__={getattr(lunalib, '__version__', 'unknown')}")
            except Exception as e:
                debug_log(f"[CRYPTO] lunalib import failed: {e}")

            try:
                from lunalib.core import wallet as luna_wallet
                debug_log(f"[CRYPTO] lunalib.core.wallet.__file__={getattr(luna_wallet, '__file__', 'unknown')}")
                debug_log(f"[CRYPTO] lunalib.core.wallet._decrypt_with_password={getattr(luna_wallet, '_decrypt_with_password', None)}")
            except Exception as e:
                debug_log(f"[CRYPTO] lunalib.core.wallet import failed: {e}")

            try:
                import cryptography
                debug_log(f"[CRYPTO] cryptography.__file__={getattr(cryptography, '__file__', 'unknown')}")
                debug_log(f"[CRYPTO] cryptography.__version__={getattr(cryptography, '__version__', 'unknown')}")
                try:
                    from cryptography.fernet import Fernet  # noqa: F401
                    debug_log("[CRYPTO] cryptography.fernet import OK")
                except Exception as e:
                    debug_log(f"[CRYPTO] cryptography.fernet import failed: {e}")
            except Exception as e:
                debug_log(f"[CRYPTO] cryptography import failed: {e}")
        except Exception:
            pass

    def _play_sound(self, sound_type):
        """Play sound using Flet's audio capabilities (mobile compatible)"""
        if not getattr(self, 'sound_enabled', True):
            print(f"[SOUND] sound_enabled is False, skipping sound: {sound_type}")
            return

        try:
            base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
            sounds_dir = os.path.join(base_dir, "assets", "sounds")
            fallback_map = {
                "transfer": "transaction",
                "reward": "transaction",
            }
            sound_name = sound_type
            sound_path = os.path.join(sounds_dir, f"{sound_name}.wav")

            if not os.path.exists(sound_path) and sound_name in fallback_map:
                print(f"[SOUND] {sound_name}.wav not found, falling back to {fallback_map[sound_name]}.wav")
                sound_name = fallback_map[sound_name]
                sound_path = os.path.join(sounds_dir, f"{sound_name}.wav")

            if not os.path.exists(sound_path):
                print(f"[SOUND] Sound file missing: {sound_path}")
                if hasattr(self, 'show_snackbar'):
                    self.show_snackbar(f"Sound file missing: {sound_path}", "error")
                return

            print(f"[SOUND] Attempting to play: {sound_path} (type: {sound_type})")

            # Prefer SoundManager if available (Windows winsound / platform-specific)
            if hasattr(self, 'sound_manager') and self.sound_manager:
                try:
                    result = self.sound_manager.play_sound(sound_name)
                    print(f"[SOUND] SoundManager.play_sound('{sound_name}') result: {result}")
                    if result:
                        return
                except Exception as sm_err:
                    print(f"[SOUND] SoundManager error: {sm_err}")

            # Fallback to Flet audio
            if not hasattr(self, 'page') or not self.page:
                print(f"[SOUND] No page context for Flet audio fallback")
                return

            try:
                if not hasattr(ft, "Audio"):
                    print(f"[SOUND] Flet Audio not available on this platform")
                    return
                audio = ft.Audio(
                    src=os.path.join("assets", "sounds", f"{sound_name}.wav"),
                    autoplay=True,
                    volume=0.5,
                )
                self.page.overlay.append(audio)
                self.page.update()
                print(f"[SOUND] Played via Flet Audio overlay")
            except Exception as flet_err:
                print(f"[SOUND] Flet audio error: {flet_err}")
                if hasattr(self, 'show_snackbar'):
                    self.show_snackbar(f"Flet audio error: {flet_err}", "error")
        except Exception as e:
            print(f"[SOUND] General sound error: {e}")
            if hasattr(self, 'show_snackbar'):
                self.show_snackbar(f"Sound error: {e}", "error")

    def _mark_incoming_sound(self, sound_type: str):
        try:
            self._last_incoming_sound_type = sound_type
            self._last_incoming_sound_time = time.time()
        except Exception:
            pass

    def _should_play_incoming_sound(self, sound_type: str, window_seconds: float = 3.0) -> bool:
        try:
            last_type = getattr(self, "_last_incoming_sound_type", None)
            last_time = float(getattr(self, "_last_incoming_sound_time", 0) or 0)
            if last_time and (time.time() - last_time) < window_seconds:
                if last_type == sound_type:
                    return False
                if last_type == "reward" and sound_type == "transaction":
                    return False
        except Exception:
            pass
        return True

    def _load_wallet_metadata(self):
        """Load basic wallet metadata from database without requiring password"""
        try:
            if not self.storage:
                print("DEBUG: No storage available")
                self.wallet_count = 0
                self.existing_wallet_address = None
                return

            # Get all wallet addresses from storage
            wallet_addresses = self._get_all_wallet_addresses_from_db()

            # Fallback: migrate from wallet_data.json if storage is empty
            if not wallet_addresses:
                try:
                    if os.path.exists(self.wallet_file_path):
                        with open(self.wallet_file_path, "r", encoding="utf-8") as f:
                            wallet_data = json.load(f)
                        wallets = wallet_data.get("wallets") if isinstance(wallet_data, dict) else None
                        if isinstance(wallets, dict) and wallets:
                            for address, data in wallets.items():
                                key = f"wallet:{address}"
                                self.storage.set(key, json.dumps(data))
                            wallet_addresses = self._get_all_wallet_addresses_from_db()
                except Exception as e:
                    print(f"DEBUG: Metadata migration from wallet file failed: {e}")

            self.wallet_count = len(wallet_addresses)

            if self.wallet_count > 0:
                self.existing_wallet_address = wallet_addresses[0]
                print(f"DEBUG: Found {self.wallet_count} wallets in storage, first address: {self.existing_wallet_address}")
            else:
                self.existing_wallet_address = None
                print("DEBUG: No wallets found in storage")
                
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

    def _encode_wallet_data(self, obj):
        """JSON serializer for wallet data (handles bytes)."""
        if isinstance(obj, (bytes, bytearray)):
            return {"__bytes__": True, "b64": base64.b64encode(obj).decode("ascii")}
        raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")

    def _decode_wallet_data(self, obj):
        """JSON hook for wallet data (handles bytes)."""
        if isinstance(obj, dict) and obj.get("__bytes__") is True and "b64" in obj:
            try:
                return base64.b64decode(obj["b64"])
            except Exception:
                return obj
        return obj

    def _store_transaction(self, wallet_addr: str, tx: dict, status: str = None):
        """Persist a transaction for a wallet in storage."""
        if not self.storage:
            return
        try:
            tx_copy = dict(tx)
            if status:
                tx_copy['status'] = status
            tx_id = self._get_tx_unique_id(tx_copy)
            key = f"tx:{wallet_addr}:{tx_id}"
            self.storage.set(key, json.dumps(tx_copy, default=self._encode_wallet_data))

            index_key = f"tx_index:{wallet_addr}"
            raw_index = self.storage.get(index_key)
            index = json.loads(raw_index) if raw_index else []
            if tx_id not in index:
                index.append(tx_id)
                self.storage.set(index_key, json.dumps(index))
        except Exception as e:
            print(f"DEBUG: Failed to store transaction for {wallet_addr[:12]}...: {e}")

    def get_wallet_transactions(self, wallet_addr: str):
        """Load transactions for a wallet from storage."""
        if not self.storage:
            return []
        try:
            index_key = f"tx_index:{wallet_addr}"
            raw_index = self.storage.get(index_key)
            if not raw_index:
                return []
            index = json.loads(raw_index)
            transactions = []
            for tx_id in index:
                raw = self.storage.get(f"tx:{wallet_addr}:{tx_id}")
                if raw:
                    transactions.append(json.loads(raw, object_hook=self._decode_wallet_data))
            transactions.sort(key=lambda t: t.get('timestamp', t.get('block_height', 0)), reverse=True)
            return transactions
        except Exception as e:
            print(f"DEBUG: Failed to load wallet transactions: {e}")
            return []

    def get_all_transactions(self):
        """Load all transactions from storage."""
        if not self.storage:
            return []
        transactions = []
        try:
            for key in self.storage.keys():
                if key.startswith("tx:"):
                    raw = self.storage.get(key)
                    if raw:
                        transactions.append(json.loads(raw, object_hook=self._decode_wallet_data))
        except Exception as e:
            print(f"DEBUG: Failed to load all transactions: {e}")
        return transactions

    def get_cached_transactions_for_addresses(self, wallet_addresses: List[str]) -> Dict[str, List[Dict]]:
        """Return cached transactions for addresses using lunalib cache only (no network)."""
        results: Dict[str, List[Dict]] = {addr: [] for addr in wallet_addresses}
        try:
            if not wallet_addresses:
                return results
            if not hasattr(self, 'blockchain_manager') or not self.blockchain_manager:
                return results

            # Prefer lunalib's built-in scan (better reward detection)
            ends_height = None
            if hasattr(self.blockchain_manager, 'get_blockchain_height'):
                try:
                    ends_height = int(self.blockchain_manager.get_blockchain_height() or 0)
                except Exception:
                    ends_height = None
            try:
                scan_results = self.blockchain_manager.scan_transactions_for_addresses(
                    wallet_addresses,
                    start_height=0,
                    end_height=ends_height,
                )
                if isinstance(scan_results, dict):
                    for addr in wallet_addresses:
                        results[addr] = list(scan_results.get(addr, []) or [])
                    if any(results.values()):
                        return results
            except Exception as scan_err:
                print(f"DEBUG: lunalib scan_transactions_for_addresses failed: {scan_err}")

            def _normalize(addr: str) -> str:
                if not addr:
                    return ''
                addr_str = str(addr).strip("'\" ").lower()
                return addr_str[4:] if addr_str.startswith('lun_') else addr_str

            normalized_map: Dict[str, str] = {}
            for addr in wallet_addresses:
                norm = _normalize(addr)
                if norm:
                    normalized_map[norm] = addr

            def _add_tx(target_addr: str, tx: Dict):
                if target_addr in results:
                    results[target_addr].append(tx)
            def _process_block(block: Dict):
                if not isinstance(block, dict):
                    return
                block_height = block.get('index') or block.get('height') or 0
                block_hash = block.get('hash') or ''
                timestamp = block.get('timestamp')

                # Block mining reward
                miner_norm = _normalize(block.get('miner') or block.get('mined_by') or block.get('miner_address') or block.get('mined_by_address') or '')
                reward_amount = self._parse_scan_amount(block.get('reward', 0) or 0)
                if miner_norm in normalized_map and reward_amount > 0:
                    target_addr = normalized_map[miner_norm]
                    _add_tx(target_addr, {
                        'type': 'reward',
                        'from': 'network',
                        'to': target_addr,
                        'reward_address': target_addr,
                        'amount': reward_amount,
                        'block_height': block_height,
                        'timestamp': timestamp,
                        'hash': f"reward_{block_height}_{block_hash[:8]}",
                        'status': 'confirmed',
                        'direction': 'incoming',
                        'effective_amount': reward_amount,
                        'fee': 0,
                    })

                # Regular transactions + rewards + GTX_Genesis
                for tx_index, tx in enumerate(block.get('transactions', []) or []):
                    if not isinstance(tx, dict):
                        continue
                    tx_type = (tx.get('type') or 'transfer').lower()
                    from_norm = _normalize(tx.get('from') or tx.get('sender') or '')
                    to_norm = _normalize(tx.get('to') or tx.get('receiver') or '')

                    if tx_type == 'reward':
                        reward_to = tx.get('to') or tx.get('receiver') or tx.get('issued_to') or tx.get('owner_address') or tx.get('to_address')
                        reward_norm = _normalize(reward_to or '')
                        if reward_norm in normalized_map:
                            target_addr = normalized_map[reward_norm]
                            amount = self._parse_scan_amount(tx.get('amount', tx.get('denomination', 0) or 0) or 0)
                            enhanced = tx.copy()
                            enhanced.update({
                                'type': 'reward',
                                'from': enhanced.get('from', 'network'),
                                'to': reward_to or target_addr,
                                'block_height': block_height,
                                'timestamp': enhanced.get('timestamp', timestamp),
                                'hash': enhanced.get('hash') or f"reward_{block_height}_{tx_index}",
                                'status': 'confirmed',
                                'tx_index': tx_index,
                                'direction': 'incoming',
                                'effective_amount': amount,
                                'amount': amount,
                                'fee': 0,
                                'reward_address': target_addr,
                            })
                            _add_tx(target_addr, enhanced)
                        continue

                    if tx_type == 'gtx_genesis':
                        reward_to = tx.get('issued_to') or tx.get('owner_address') or tx.get('to') or tx.get('receiver') or tx.get('to_address')
                        reward_norm = _normalize(reward_to or '')
                        if reward_norm in normalized_map:
                            target_addr = normalized_map[reward_norm]
                            amount = self._parse_scan_amount(tx.get('amount', tx.get('denomination', 0) or 0) or 0)
                            enhanced = tx.copy()
                            enhanced.update({
                                'type': 'reward',
                                'from': 'network',
                                'to': reward_to or target_addr,
                                'block_height': block_height,
                                'timestamp': enhanced.get('timestamp', timestamp),
                                'hash': enhanced.get('hash') or f"genesis_reward_{block_height}_{tx_index}",
                                'status': 'confirmed',
                                'tx_index': tx_index,
                                'direction': 'incoming',
                                'effective_amount': amount,
                                'amount': amount,
                                'fee': 0,
                                'reward_address': target_addr,
                                'original_type': 'gtx_genesis',
                            })
                            _add_tx(target_addr, enhanced)
                        continue

                    # Transfers
                    amount = self._parse_scan_amount(tx.get('amount', 0) or 0)
                    fee = self._parse_scan_amount(tx.get('fee', 0) or tx.get('gas', 0) or 0)
                    if to_norm in normalized_map:
                        target_addr = normalized_map[to_norm]
                        enhanced = tx.copy()
                        enhanced.update({
                            'block_height': block_height,
                            'status': 'confirmed',
                            'tx_index': tx_index,
                            'direction': 'incoming',
                            'effective_amount': amount,
                            'amount': amount,
                            'fee': fee,
                        })
                        _add_tx(target_addr, enhanced)
                    if from_norm in normalized_map:
                        target_addr = normalized_map[from_norm]
                        enhanced = tx.copy()
                        enhanced.update({
                            'block_height': block_height,
                            'status': 'confirmed',
                            'tx_index': tx_index,
                            'direction': 'outgoing',
                            'effective_amount': -(amount + fee),
                            'amount': amount,
                            'fee': fee,
                        })
                        _add_tx(target_addr, enhanced)

            cache = getattr(self.blockchain_manager, 'cache', None)
            if not cache:
                return results
            cached_height = cache.get_highest_cached_height()
            if cached_height is None or cached_height < 0:
                return results
            batch_size = 200
            for start in range(0, cached_height + 1, batch_size):
                end = min(start + batch_size - 1, cached_height)
                blocks = cache.get_block_range(start, end)
                for block in blocks:
                    _process_block(block)
            return results
        except Exception as e:
            print(f"DEBUG: get_cached_transactions_for_addresses failed: {e}")
            return results

    def get_cached_transactions_for_address(self, wallet_address: str) -> List[Dict]:
        """Return cached transactions for a single address using lunalib cache only."""
        try:
            results = self.get_cached_transactions_for_addresses([wallet_address])
            return results.get(wallet_address, []) if isinstance(results, dict) else []
        except Exception as e:
            print(f"DEBUG: get_cached_transactions_for_address failed: {e}")
            return []

    def schedule_catchup_scan_from_cache(self):
        """Scan from last cached height to latest height and refresh UI."""
        if getattr(self, '_catchup_scan_in_progress', False):
            return

        def _catchup():
            try:
                self._catchup_scan_in_progress = True
                if not hasattr(self, 'wallet_core') or not self.wallet_core:
                    return
                wallet_addresses = list(getattr(self.wallet_core, 'wallets', {}).keys())
                if not wallet_addresses:
                    return

                if not hasattr(self, 'blockchain_manager') or not self.blockchain_manager:
                    return
                cache = getattr(self.blockchain_manager, 'cache', None)
                cached_height = cache.get_highest_cached_height() if cache else -1
                latest_block = self.blockchain_manager.get_latest_block()
                latest_height = latest_block.get('index', 0) if latest_block else 0

                if cached_height >= latest_height:
                    return

                self._sync_wallets_with_lunalib()
                self.last_scanned_block = max(self.last_scanned_block, latest_height)
            except Exception as e:
                print(f"DEBUG: schedule_catchup_scan_from_cache failed: {e}")
            finally:
                self._catchup_scan_in_progress = False

        threading.Thread(target=_catchup, daemon=True).start()

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
            flet_storage = os.getenv("FLET_APP_STORAGE")
            if flet_storage:
                flet_dir = os.path.join(flet_storage, "luna_wallet")
                os.makedirs(flet_dir, exist_ok=True)
                return flet_dir
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
        """Save wallet data using Storage"""
        try:
            current_time = time.time()

            # Rate limiting for normal saves
            if not force_save and not is_backup:
                if current_time - self.last_save_time < self.save_cooldown:
                    return True

            if self.is_locked and not force_save:
                print("DEBUG: Wallet is locked, skipping save (use force_save=True to override)")
                return False

            if not self.storage:
                print("DEBUG: No storage available, skipping save")
                return False

            # Save each wallet to storage
            saved_count = 0
            if hasattr(self.wallet_core, 'wallets') and self.wallet_core.wallets:
                try:
                    print(f"DEBUG: save_wallet_data wallet_core.wallets keys: {list(self.wallet_core.wallets.keys())}")
                except Exception:
                    pass
                for address, wallet_info in self.wallet_core.wallets.items():
                    try:
                        key = f"wallet:{address}"
                        self.storage.set(key, json.dumps(wallet_info, default=self._encode_wallet_data))
                        saved_count += 1
                        print(f"DEBUG: Saved wallet {address[:12]}...")
                    except Exception as e:
                        print(f"DEBUG: Error saving wallet {address[:12]}...: {e}")

            self.last_save_time = current_time
            try:
                key_count = len(self.storage.keys()) if self.storage else 0
                print(f"DEBUG: Saved {saved_count} wallets to storage (total keys: {key_count})")
            except Exception:
                print(f"DEBUG: Saved {saved_count} wallets to storage")
            return True

        except Exception as e:
            print(f"DEBUG: Error saving wallet data: {e}")
            return False

    def _get_all_wallet_addresses_from_db(self):
        """Get all wallet addresses from the database"""
        if not self.storage:
            return []
        try:
            # For demo: assume addresses are stored as keys with prefix 'wallet:'
            return [k[7:] for k in self.storage.keys() if k.startswith('wallet:')]
        except Exception as e:
            print(f"DEBUG: Error getting wallet addresses from storage: {e}")
            return []

    def load_wallet_data(self):
        """Load wallet data from Storage"""
        try:
            if not self.storage:
                print("DEBUG: No storage available")
                return False

            print("DEBUG: Loading wallet data from storage")

            # Get all wallet addresses from storage
            wallet_addresses = self._get_all_wallet_addresses_from_db()
            if not wallet_addresses:
                # Fallback to legacy WalletDatabase on desktop
                if not is_web():
                    try:
                        from lunalib.storage.database import WalletDatabase
                        data_dir = self._get_data_directory()
                        db_path = os.path.join(data_dir, "wallet.db")
                        legacy_db = WalletDatabase(db_path=db_path)

                        # Try multiple legacy APIs to get wallet addresses
                        addr_list = []
                        if hasattr(legacy_db, "get_all_wallet_addresses"):
                            addr_list = legacy_db.get_all_wallet_addresses()
                        elif hasattr(legacy_db, "get_wallet_index"):
                            wallet_index = legacy_db.get_wallet_index()
                            if isinstance(wallet_index, list):
                                addr_list = [w.get("address") for w in wallet_index if isinstance(w, dict) and w.get("address")]
                        elif hasattr(legacy_db, "get_wallets"):
                            wallets = legacy_db.get_wallets()
                            if isinstance(wallets, dict):
                                addr_list = list(wallets.keys())
                            elif isinstance(wallets, list):
                                addr_list = [w.get("address") for w in wallets if isinstance(w, dict) and w.get("address")]

                        wallet_addresses = [a for a in addr_list if a]
                        if wallet_addresses:
                            print(f"DEBUG: Found {len(wallet_addresses)} wallets in legacy database")
                            # Load and migrate to storage
                            for address in wallet_addresses:
                                wallet_data = None
                                if hasattr(legacy_db, "load_wallet"):
                                    wallet_data = legacy_db.load_wallet(address)
                                elif hasattr(legacy_db, "get_wallet"):
                                    wallet_data = legacy_db.get_wallet(address)
                                if wallet_data:
                                    key = f"wallet:{address}"
                                    self.storage.set(key, json.dumps(wallet_data))
                            # Rebuild list from storage after migration
                            wallet_addresses = self._get_all_wallet_addresses_from_db()
                    except Exception as e:
                        print(f"DEBUG: Legacy WalletDatabase fallback failed: {e}")

                # Fallback: load from wallet_data.json and backups
                if not wallet_addresses:
                    try:
                        if os.path.exists(self.wallet_file_path):
                            with open(self.wallet_file_path, "r", encoding="utf-8") as f:
                                wallet_data = json.load(f)
                            wallets = wallet_data.get("wallets") if isinstance(wallet_data, dict) else None
                            if isinstance(wallets, dict) and wallets:
                                for address, data in wallets.items():
                                    key = f"wallet:{address}"
                                    self.storage.set(key, json.dumps(data))
                                wallet_addresses = self._get_all_wallet_addresses_from_db()
                    except Exception as e:
                        print(f"DEBUG: Wallet file fallback failed: {e}")

                if not wallet_addresses:
                    try:
                        backup_dir = os.path.join(self._get_data_directory(), "backups")
                        if os.path.isdir(backup_dir):
                            for fname in os.listdir(backup_dir):
                                if not fname.startswith("wallet_backup_") or not fname.endswith(".json"):
                                    continue
                                backup_path = os.path.join(backup_dir, fname)
                                with open(backup_path, "r", encoding="utf-8") as f:
                                    wallet_data = json.load(f)
                                wallets = wallet_data.get("wallets") if isinstance(wallet_data, dict) else None
                                if isinstance(wallets, dict) and wallets:
                                    for address, data in wallets.items():
                                        key = f"wallet:{address}"
                                        self.storage.set(key, json.dumps(data))
                                    wallet_addresses = self._get_all_wallet_addresses_from_db()
                                    if wallet_addresses:
                                        print(f"DEBUG: Restored wallets from backup: {fname}")
                                        break
                    except Exception as e:
                        print(f"DEBUG: Backup fallback failed: {e}")

                if not wallet_addresses:
                    print("DEBUG: No wallets found in storage")
                    return False

            print(f"DEBUG: Found {len(wallet_addresses)} wallets in storage")

            # Load each wallet and restore to LunaWallet
            loaded_count = 0
            if hasattr(self.wallet_core, 'wallets'):
                # Clear existing wallets
                self.wallet_core.wallets = {}

                for address in wallet_addresses:
                    try:
                        key = f"wallet:{address}"
                        raw = self.storage.get(key)
                        wallet_data = json.loads(raw, object_hook=self._decode_wallet_data) if raw else None
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
        if self._should_play_incoming_sound("transaction"):
            self._play_sound("transaction")
            self._mark_incoming_sound("transaction")
        self.create_backup()  # Create backup for important changes

    def on_sync_progress(self, progress, message):
        if not self.is_locked and hasattr(self, 'page'):
            if 'progress_sync' in self.refs and self.refs['progress_sync'].current:
                self.refs['progress_sync'].current.value = progress / 100
                self.refs['progress_sync'].current.visible = True
            if 'lbl_sync_status' in self.refs and self.refs['lbl_sync_status'].current:
                self.refs['lbl_sync_status'].current.value = f"Status: {message}"
            if hasattr(self, 'wallet_page') and self.wallet_page:
                if hasattr(self.wallet_page, 'show_sync_status'):
                    try:
                        self.wallet_page.show_sync_status(message, progress)
                    except Exception:
                        pass
            self.update_refs()

    def on_transaction_received(self):
        """Handle incoming transactions: キャッシュへ即時追加し、残高・UIを即時更新。"""
        # tx, wallet_addrは外部から渡すことを想定（既存互換のため引数なしでも動作）
        import inspect
        tx = None
        wallet_addr = None
        # 呼び出し元がtx, wallet_addrを渡している場合は取得
        frame = inspect.currentframe()
        try:
            args, _, _, values = inspect.getargvalues(frame)
            if 'tx' in values:
                tx = values['tx']
            if 'wallet_addr' in values:
                wallet_addr = values['wallet_addr']
        except Exception:
            pass
        # 1. 受信トランザクションをキャッシュへ追加
        if tx and wallet_addr:
            try:
                self._store_transaction(wallet_addr, tx)
                # 残高キャッシュも即時更新（必要に応じて）
                if hasattr(self, 'wallet_balances_cache'):
                    bal = self.wallet_balances_cache.get(wallet_addr, 0)
                    # txのvalueやtypeに応じて加算/減算（例: 入金なら加算、出金なら減算）
                    if 'amount' in tx:
                        # ここは実際の仕様に合わせて調整
                        bal += tx.get('amount', 0)
                        self.wallet_balances_cache[wallet_addr] = bal
            except Exception as e:
                print(f"DEBUG: Failed to cache new transaction: {e}")

        # 2. UIを即時リフレッシュ
        if hasattr(self, 'wallet_page') and self.wallet_page:
            if hasattr(self.wallet_page, 'refresh_transaction_history'):
                try:
                    self.wallet_page.refresh_transaction_history()
                except Exception as e:
                    print(f"DEBUG: Error refreshing transaction history: {e}")
            if hasattr(self.wallet_page, '_update_wallet_data_ui_only'):
                try:
                    self.wallet_page._update_wallet_data_ui_only()
                except Exception as e:
                    print(f"DEBUG: Error updating wallet data UI: {e}")

        self.show_snackbar("New transaction received", "success")

        # Play transaction sound (if not just played as reward)
        if self._should_play_incoming_sound("transaction"):
            self._play_sound("transaction")
            self._mark_incoming_sound("transaction")
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
            if hasattr(self.wallet_page, '_refresh_sidebar_wallets'):
                try:
                    self.wallet_page._refresh_sidebar_wallets()
                except Exception as e:
                    print(f"DEBUG: Error refreshing sidebar: {e}")
        self.save_wallet_data(force_save=True)  # Force save after sync
        self.create_backup()  # Create backup after sync
        self.show_snackbar("Blockchain sync completed", "success")

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
            base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
            icon_path = os.path.join(base_dir, "wallet_icon.ico")
            if os.path.exists(icon_path):
                print(f"DEBUG: Setting icon from: {icon_path}")
                page.window.icon = icon_path
            else:
                # Try PNG as fallback
                png_path = os.path.join(base_dir, "wallet_icon.png")
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
        if hasattr(page, "on_close"):
            page.on_close = self.on_page_close

        # Track user activity for auto-lock
        try:
            if hasattr(page, "on_keyboard_event"):
                page.on_keyboard_event = self._register_activity
            if hasattr(page, "on_pointer_event"):
                page.on_pointer_event = self._register_activity
        except Exception as e:
            print(f"DEBUG: Failed to attach activity handlers: {e}")

        self._start_inactivity_monitor()

        # Show lightweight loading UI first to avoid startup hangs
        try:
            page.controls.clear()
            page.add(
                ft.Container(
                    content=ft.Column([
                        ft.Text("Starting Luna Wallet...", size=18, weight="bold", color="#f8d7da"),
                        ft.Text("Initializing services", size=12, color="#f8d7da"),
                    ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                    alignment=ft.Alignment(0, 0),
                    expand=True,
                )
            )
            page.update()
        except Exception:
            pass

        def _init_services_and_ui():
            self._ensure_services()
            if hasattr(self, 'page') and self.page and hasattr(self.page, 'run_thread'):
                self.page.run_thread(self.initialize_wallet_state)
            else:
                self.initialize_wallet_state()

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

        threading.Thread(target=_init_services_and_ui, daemon=True).start()

    def _ensure_services(self):
        if self._services_ready:
            return
        try:
            print("DEBUG: Initializing services...")
            self._ensure_ca_bundle()
            self.wallet_service = self.wallet_service or WalletService()
            self.blockchain_service = self.blockchain_service or BlockchainService()
            self.mempool_service = self.mempool_service or MempoolService()

            # Keep references for backward compatibility
            self.wallet_core = self.wallet_service.core
            self.blockchain_manager = self.blockchain_service.manager
            self.mempool_manager = self.mempool_service.manager

            # Optional one-time cache reset
            try:
                if str(os.getenv("LUNALIB_RESET_CACHE", "")).strip() in ("1", "true", "yes"):
                    if self.blockchain_service and hasattr(self.blockchain_service, "reset_cache"):
                        if self.blockchain_service.reset_cache():
                            print("DEBUG: Blockchain cache reset (forced)")
            except Exception as e:
                print(f"DEBUG: Cache reset skipped: {e}")

            # Register as peer and refresh peer list (desktop only)
            try:
                if not is_web() and self.blockchain_service:
                    self.blockchain_service.register_as_peer()
                    self.blockchain_service.refresh_peers()
            except Exception as e:
                print(f"DEBUG: Peer registration/refresh skipped: {e}")

            self._services_ready = True
            print("DEBUG: Services initialized")
        except Exception as e:
            print(f"DEBUG: Service initialization failed: {e}")

    def _set_mobile_content(self, content, transition=None):
        if transition is None:
            transition = getattr(ft.AnimatedSwitcherTransition, "SLIDE", ft.AnimatedSwitcherTransition.FADE)
        if not hasattr(self, "_mobile_switcher") or self._mobile_switcher is None:
            self._mobile_switcher = ft.AnimatedSwitcher(
                content=content,
                transition=transition,
                duration=300,
                reverse_duration=300,
            )
            if hasattr(self, 'page') and self.page:
                try:
                    self.page.clean()
                except Exception:
                    self.page.controls.clear()
                self.page.add(self._mobile_switcher)
        else:
            self._mobile_switcher.transition = transition
            self._mobile_switcher.content = content
        if hasattr(self, 'page') and self.page:
            self.page.update()

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
        if self._is_closing:
            return
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
        if self._is_closing:
            return
        self.detect_orientation()
        self.update_layout()

    def update_layout(self):
        if self._is_closing:
            return
        if not hasattr(self, 'page') or not self.page:
            return

        self.page.controls.clear()
        self.show_current_page()
        self.page.update()

    def show_current_page(self):
        if self._is_closing:
            return
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

    def on_page_close(self, e):
        """Handle window close to avoid GTK/engine warnings during teardown."""
        self._is_closing = True
        try:
            if hasattr(self, 'page') and self.page:
                self.page.on_resize = None
                if hasattr(self.page, "on_keyboard_event"):
                    self.page.on_keyboard_event = None
                if hasattr(self.page, "on_pointer_event"):
                    self.page.on_pointer_event = None
        except Exception:
            pass

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

    def show_wallet_page(self, reuse: bool = False):
        """Display the main wallet page with all wallets and transactions"""
        try:
            print("[WALLET_PAGE] showing wallet page...")

            # Fast path: reuse existing wallet page view when available
            if reuse and hasattr(self, "wallet_page") and hasattr(self, "wallet_page_view") and self.wallet_page_view:
                self.current_page = self.wallet_page_view
                if hasattr(self, 'page') and self.page:
                    try:
                        self.page.clean()
                    except Exception:
                        self.page.controls.clear()
                    if hasattr(self.page, 'overlay'):
                        self.page.overlay.clear()
                    if self.is_mobile:
                        self._set_mobile_content(self.current_page)
                    else:
                        self.page.add(self.current_page)
                        self.page.update()
                try:
                    if hasattr(self.wallet_page, 'refresh_transaction_history'):
                        if hasattr(self.page, 'run_thread'):
                            self.page.run_thread(self.wallet_page.refresh_transaction_history)
                        else:
                            self.wallet_page.refresh_transaction_history()
                except Exception:
                    pass
                return

            # Create the wallet page with all necessary callbacks
            try:
                if hasattr(self, 'wallet_core') and self.wallet_core and hasattr(self.wallet_core, 'wallets'):
                    wallets_dict = self.wallet_core.wallets if isinstance(self.wallet_core.wallets, dict) else {}
                    if wallets_dict:
                        current_addr = getattr(self.wallet_core, 'current_wallet_address', None)
                        if not current_addr or current_addr not in wallets_dict:
                            addresses = list(wallets_dict.keys())
                            idx = getattr(self, 'selected_wallet_index', 0) if isinstance(getattr(self, 'selected_wallet_index', 0), int) else 0
                            if idx < 0 or idx >= len(addresses):
                                idx = 0
                            default_addr = addresses[idx]
                            if hasattr(self.wallet_core, 'switch_wallet'):
                                try:
                                    self.wallet_core.switch_wallet(default_addr)
                                except Exception:
                                    self.wallet_core.current_wallet_address = default_addr
                            else:
                                self.wallet_core.current_wallet_address = default_addr
            except Exception as addr_err:
                print(f"[WALLET_PAGE] default wallet selection failed: {addr_err}")

            wallet_page = WalletPage(
                app=self,
                on_send=self.on_send_transaction,
                on_receive=self.on_receive,
                on_export_key=self.on_export_key,
                on_lock=self.on_lock,
                on_create_wallet=self.on_create_wallet,
                on_import_wallet=self.on_import_wallet,
                on_settings=self.on_settings,
                show_back=self.is_mobile,
                on_back=self.show_wallet_index_page if self.is_mobile else None
            )

            # Store reference for later updates
            self.wallet_page = wallet_page

            # Set as current page
            try:
                self.current_page = wallet_page.create()
                self.wallet_page_view = self.current_page
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
            
            if self.is_mobile:
                self._set_mobile_content(
                    self.current_page,
                    transition=getattr(ft.AnimatedSwitcherTransition, "SLIDE", ft.AnimatedSwitcherTransition.FADE)
                )
            elif hasattr(self, 'page') and self.page:
                self.page.add(self.current_page)
                # Force UI refresh
                self.page.update()
                try:
                    self.page.update()
                except Exception:
                    pass

            # Ensure sidebar shows newly created wallets
            try:
                if hasattr(self, 'wallet_page') and self.wallet_page:
                    if hasattr(self.wallet_page, '_refresh_sidebar_wallets'):
                        self.wallet_page._refresh_sidebar_wallets()
                    if hasattr(self.wallet_page, '_apply_sidebar_selection_highlight'):
                        self.wallet_page._apply_sidebar_selection_highlight()
            except Exception as sidebar_err:
                print(f"[WALLET_PAGE] sidebar refresh failed: {sidebar_err}")
            
            print("[WALLET_PAGE] wallet page displayed")
            
        except Exception as e:
            print(f"[WALLET_PAGE] ERROR: {e}")
            import traceback
            traceback.print_exc()
            raise

    def show_wallet_index_page(self):
        """Display wallet index page on mobile."""
        if not self.is_mobile:
            return self.show_wallet_page()

        from gui.page_wallet_index import WalletIndexPage

        def _select_wallet(address):
            try:
                if hasattr(self.wallet_core, 'switch_wallet'):
                    self.wallet_core.switch_wallet(address)
                elif hasattr(self.wallet_core, 'current_wallet_address'):
                    self.wallet_core.current_wallet_address = address
                self.show_wallet_page()
            except Exception as e:
                print(f"DEBUG: Failed to select wallet: {e}")

        index_page = WalletIndexPage(
            app=self,
            on_select_wallet=_select_wallet,
            on_create_wallet=self.on_create_wallet,
            on_import_wallet=self.on_import_wallet,
        )

        self.current_page = index_page.create()
        self._set_mobile_content(
            self.current_page,
            transition=getattr(ft.AnimatedSwitcherTransition, "SLIDE", ft.AnimatedSwitcherTransition.FADE)
        )

    def lock_wallet(self):
        """Lock the wallet and return to lock screen"""
        print("DEBUG: lock_wallet called")
        try:
            if hasattr(self, 'storage') and self.storage and hasattr(self.storage, 'db_path'):
                print(f"[LOCK] Storage DB path: {self.storage.db_path}")
        except Exception:
            pass
        try:
            if hasattr(self, 'wallet_core') and hasattr(self.wallet_core, 'wallets'):
                wallet_count = len(self.wallet_core.wallets) if isinstance(self.wallet_core.wallets, dict) else 0
                print(f"[LOCK] wallet_core.wallets count: {wallet_count}")
        except Exception:
            pass
        try:
            self.save_wallet_data(force_save=True)
        except Exception as e:
            print(f"[LOCK] save_wallet_data failed: {e}")
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
            on_back=lambda: self.show_wallet_page(reuse=True),
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
            on_back=lambda: self.show_wallet_page(reuse=True)
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
            on_back=lambda: self.show_wallet_page(reuse=True)
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
            on_back=self.show_wallet_index_page if self.is_mobile else self.show_wallet_page,
            on_wallet_imported=self.refresh_wallet_list
        )
        self.current_page = import_page.create()
        if self.is_mobile:
            self._set_mobile_content(
                self.current_page,
                transition=getattr(ft.AnimatedSwitcherTransition, "SLIDE", ft.AnimatedSwitcherTransition.FADE)
            )
        else:
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
            on_wallet_imported=self.show_wallet_index_page if self.is_mobile else self.initialize_wallet_state
        )
        self.current_page = import_page.create()
        if self.is_mobile:
            self._set_mobile_content(
                self.current_page,
                transition=getattr(ft.AnimatedSwitcherTransition, "SLIDE", ft.AnimatedSwitcherTransition.FADE)
            )
        else:
            self.page.controls.clear()
            self.page.add(self.current_page)
            self.page.update()

    def refresh_wallet_list(self):
        """Refresh the wallet list after a new wallet is created."""
        print("DEBUG: refresh_wallet_list called")
        try:
            self._register_wallets_with_manager()
            # Return to wallet page and refresh the sidebar
            if hasattr(self, 'wallet_page') and self.wallet_page:
                # Refresh sidebar wallets
                if hasattr(self.wallet_page, '_refresh_sidebar_wallets'):
                    self.wallet_page._refresh_sidebar_wallets()
                    print("DEBUG: Sidebar wallets refreshed")
            
            # Show the wallet page (mobile uses index)
            if self.is_mobile:
                self.show_wallet_index_page()
            else:
                self.show_wallet_page()
        except Exception as e:
            print(f"DEBUG: Error refreshing wallet list: {e}")
            import traceback
            traceback.print_exc()

    def on_settings(self):
        """Handle settings action"""
        print("DEBUG: on_settings called")
        try:
            from gui.page_settings import SettingsPage

            settings_page = SettingsPage(
                self,
                on_back=lambda: self.show_wallet_page(reuse=True)
            )
            self.current_page = settings_page.create()
            self.page.controls.clear()
            self.page.add(self.current_page)
            self.page.update()
        except Exception as e:
            print(f"DEBUG: Failed to show settings page: {e}")
            self.show_snackbar("Failed to open settings", "error")

    def _apply_runtime_settings_from_storage(self):
        """Apply runtime settings stored in Storage to environment variables."""
        if not getattr(self, "storage", None):
            return
        try:
            import json
            raw = self.storage.get("settings")
            if not raw:
                return
            data = json.loads(raw)
        except Exception:
            return

        def _set_env(key: str, value):
            if value is None:
                return
            os.environ[str(key)] = str(value)

        _set_env("LUNALIB_AMOUNT_DECIMALS", data.get("luna_big_decimals"))
        _set_env("LUNALIB_AMOUNT_SMALL_DECIMALS", data.get("luna_small_decimals"))
        _set_env("LUNALIB_AMOUNT_TINY_DECIMALS", data.get("luna_tiny_decimals"))
        _set_env("LUNALIB_ENDPOINT_URL", data.get("sync_url"))
        _set_env("LUNA_NODE_URL", data.get("sync_url"))
        _set_env("LUNAWALLET_FLAT_LKC", "1" if data.get("flat_lkc_display") else "0")

    def unlock_wallet(self, password):
        """Unlock existing wallet with password using LunaWallet core methods"""
        try:
            print("[UNLOCK] Starting unlock process...")
            # Ensure SM4 wallet encryption is used (lunalib 2.4.0+)
            try:
                os.environ.setdefault("LUNALIB_WALLET_CIPHER", "sm4")
                os.environ.setdefault("LUNALIB_SM4_USE_GPU", "1")
            except Exception:
                pass
            try:
                if hasattr(self, 'storage') and self.storage and hasattr(self.storage, 'db_path'):
                    print(f"[UNLOCK] Storage DB path: {self.storage.db_path}")
            except Exception:
                pass

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
            print("[UNLOCK] Loading wallet data from storage...")
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
                    try:
                        from app.debug_logger import debug_log
                        wallet_obj = self.wallet_core.wallets.get(wallet_address, {})
                        token = wallet_obj.get('encrypted_private_key')
                        prefix = None
                        if isinstance(token, bytes):
                            prefix = token[:10]
                        elif isinstance(token, str):
                            prefix = token[:10]
                        debug_log(f"[UNLOCK] wallet={wallet_address[:12]} token_prefix={prefix}")
                    except Exception:
                        pass
                    unlock_result = self.wallet_core.unlock_wallet(wallet_address, password)
                    if isinstance(unlock_result, dict):
                        unlock_success = bool(unlock_result.get("success", False))
                    else:
                        unlock_success = bool(unlock_result)
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

                # Clear lock page reference
                self.current_lock_page = None
                
                # Transition to wallet page
                try:
                    if self.is_mobile:
                        self.show_wallet_index_page()
                    else:
                        self.show_wallet_page()
                    _global_trace("Wallet page displayed", "UNLOCK")
                except Exception as page_error:
                    print(f"[UNLOCK] show_wallet_page() failed: {page_error}")
                    _global_trace(f"Wallet page failed: {page_error}", "UNLOCK_ERROR")
                    import traceback
                    traceback.print_exc()
                    raise

                # Defer heavy post-unlock tasks to background to speed UI
                def _post_unlock_tasks():
                    try:
                        self.save_wallet_data(force_save=True)
                        _global_trace("Wallet state saved", "UNLOCK")
                    except Exception as e:
                        print(f"[UNLOCK] save_wallet_data failed: {e}")
                    try:
                        self._register_wallets_with_manager()
                        self._start_wallet_manager_sync()
                    except Exception as e:
                        print(f"[UNLOCK] wallet manager sync start failed: {e}")
                    try:
                        if str(os.getenv("LUNALIB_FORCE_RESCAN", "")).strip().lower() in ("1", "true", "yes"):
                            self.force_rescan_blockchain()
                        else:
                            self.start_initial_blockchain_scan()
                    except Exception as e:
                        print(f"[UNLOCK] start_initial_blockchain_scan failed: {e}")

                threading.Thread(target=_post_unlock_tasks, daemon=True).start()

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
                    if hasattr(self.wallet_page, 'show_sync_status'):
                        self.page.run_thread(self.wallet_page.show_sync_status, "Syncing Blockchain...")

                # Perform the initial sync using lunalib
                wallet_addresses = list(self.wallet_core.wallets.keys())
                if wallet_addresses:
                    self._update_scan_loading("Connecting to node...")
                    latest_block = self.blockchain_manager.get_latest_block()
                    latest_height = latest_block.get('index', 0) if latest_block else 0
                    cached_height = 0
                    try:
                        cached_height = int(self.blockchain_manager.cache.get_highest_cached_height() or 0)
                    except Exception:
                        cached_height = 0

                    try:
                        from app.debug_logger import debug_log
                        debug_log(f"[SCAN] startup cache detected height={cached_height} latest={latest_height}")
                    except Exception:
                        pass

                    # すでにキャッシュが最新まで到達していればスキャン不要
                    if cached_height >= latest_height:
                        self.last_scanned_block = cached_height
                        self._update_scan_loading(f"Blockchain already up to date (height={cached_height})")
                        print(f"DEBUG: Blockchain already up to date (height={cached_height})")
                    else:
                        self._update_scan_loading("Syncing Transactions (lunalib)...")
                        sync_ok = self._sync_wallets_with_lunalib()
                        if sync_ok:
                            try:
                                self._refresh_ui_after_scan(force_update=True)
                            except Exception as refresh_err:
                                print(f"DEBUG: refresh after initial lunalib sync failed: {refresh_err}")
                        self.last_scanned_block = latest_height
                    self._update_scan_loading("Processing results...")
                
                self.initial_scan_complete = True
                print("DEBUG: Initial blockchain scan COMPLETED.")

                # Hide loading indicator
                if hasattr(self, 'wallet_page') and self.wallet_page:
                    if hasattr(self.wallet_page, 'hide_sync_status'):
                        self.page.run_thread(self.wallet_page.hide_sync_status)

                # Now, start the continuous background scan for new blocks
                self.start_continuous_blockchain_scan()

            except Exception as e:
                print(f"DEBUG: Error during initial blockchain scan: {e}")
                import traceback
                traceback.print_exc()
                # Ensure loading indicator is hidden on error
                if hasattr(self, 'wallet_page') and self.wallet_page:
                    if hasattr(self.wallet_page, 'hide_sync_status'):
                        self.page.run_thread(self.wallet_page.hide_sync_status)

        threading.Thread(target=initial_scan_thread, daemon=True).start()

    def _update_scan_loading(self, text, progress: float = None):
        """Update scan overlay text/progress without toggling visibility."""
        try:
            if hasattr(self, 'wallet_page') and self.wallet_page:
                if hasattr(self.wallet_page, 'show_sync_status'):
                    if hasattr(self, 'page') and self.page and hasattr(self.page, 'run_thread'):
                        self.page.run_thread(self.wallet_page.show_sync_status, text, progress)
                    else:
                        self.wallet_page.show_sync_status(text, progress)
        except Exception as e:
            print(f"DEBUG: Error updating scan loading text: {e}")

    def show_create_wallet(self):
        """Display the wallet creation page or dialog."""
        print("DEBUG: show_create_wallet called")
        try:
            if hasattr(self, '_ensure_services'):
                self._ensure_services()
        except Exception as svc_err:
            print(f"DEBUG: Service init failed before show_create_wallet: {svc_err}")
        if not getattr(self, 'wallet_core', None):
            self.show_snackbar("Wallet service not ready. Please try again.", "error")
            return
        # Example implementation: Navigate to the wallet creation page
        from gui.page_create_wallet import CreateWalletPage
        create_wallet_page = CreateWalletPage(
            self,
            on_back=self.show_wallet_index_page if self.is_mobile else self.show_wallet_page,
            on_wallet_created=self.refresh_wallet_list
        )
        self.current_page = create_wallet_page.create()

        # Clear and add the new page to the UI
        if self.is_mobile:
            self._set_mobile_content(
                self.current_page,
                transition=getattr(ft.AnimatedSwitcherTransition, "SLIDE", ft.AnimatedSwitcherTransition.FADE)
            )
        else:
            self.page.controls.clear()
            self.page.controls.append(self.current_page)
            self.page.update()

    def update_refs(self):
            """Update all UI references"""
            if hasattr(self, 'page') and self.page:
                self.page.update()

    def _ensure_wallet_sync_helper(self):
        if hasattr(self, '_wallet_sync_helper') and self._wallet_sync_helper:
            return self._wallet_sync_helper
        try:
            try:
                from lunalib.core.wallet_sync_helper import create_wallet_sync_helper
            except Exception:
                from lunalib.core.sync_helper import create_wallet_sync_helper
            helper = create_wallet_sync_helper(self.wallet_core, self.blockchain_manager, self.mempool_manager)
            self._wallet_sync_helper = helper
            try:
                if hasattr(helper, 'register_wallets_from_lunawallet'):
                    helper.register_wallets_from_lunawallet()
                elif hasattr(helper, 'register_wallets'):
                    helper.register_wallets()
            except Exception as reg_err:
                print(f"DEBUG: wallet sync register failed: {reg_err}")
            return helper
        except Exception as e:
            print(f"DEBUG: wallet sync helper unavailable: {e}")
            self._wallet_sync_helper = None
            return None

    def _ensure_wallet_state_manager(self):
        if hasattr(self, 'wallet_state_manager') and self.wallet_state_manager:
            return self.wallet_state_manager
        try:
            from lunalib.wallet_manager import get_wallet_manager
            self.wallet_state_manager = get_wallet_manager()
            return self.wallet_state_manager
        except Exception as e:
            print(f"DEBUG: wallet_state_manager unavailable: {e}")
            self.wallet_state_manager = None
            return None

    def _register_wallets_with_manager(self):
        try:
            manager = self._ensure_wallet_state_manager()
            if not manager or not hasattr(self, 'wallet_core') or not self.wallet_core:
                return
            addresses = list(getattr(self.wallet_core, 'wallets', {}).keys())
            if addresses:
                manager.register_wallets(addresses)
        except Exception as e:
            print(f"DEBUG: register_wallets_with_manager failed: {e}")

    def _normalize_scan_address(self, addr: str) -> str:
        if not addr:
            return ''
        addr_str = str(addr).strip("'\" ").lower()
        return addr_str[4:] if addr_str.startswith('lun_') else addr_str

    def _parse_scan_amount(self, value, default: float = 0.0) -> float:
        if value is None:
            return default
        if isinstance(value, (int, float)):
            try:
                return float(value)
            except Exception:
                return default
        try:
            return float(value)
        except Exception:
            text = str(value)
            match = re.search(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", text)
            if match:
                try:
                    return float(match.group(0))
                except Exception:
                    return default
        return default

    def _scan_reward_like_transactions_for_addresses(self, addresses: List[str], start_height: int = 0, end_height: Optional[int] = None) -> Dict[str, List[Dict]]:
        """Scan blocks for reward-like txs, including GTX_Genesis payouts to our wallets."""
        results: Dict[str, List[Dict]] = {addr: [] for addr in addresses}
        if not addresses or not hasattr(self, 'blockchain_manager') or not self.blockchain_manager:
            return results

        normalized_map = {self._normalize_scan_address(a): a for a in addresses if self._normalize_scan_address(a)}
        if not normalized_map:
            return results

        if end_height is None:
            try:
                end_height = int(self.blockchain_manager.get_blockchain_height() or 0)
            except Exception:
                end_height = -1
        try:
            end_height = int(end_height)
        except Exception:
            end_height = -1
        if end_height < start_height:
            return results

        seen: Dict[str, set] = {addr: set() for addr in addresses}
        batch_size = 100
        for batch_start in range(start_height, end_height + 1, batch_size):
            batch_end = min(batch_start + batch_size - 1, end_height)
            try:
                blocks = self.blockchain_manager.get_blocks_range(batch_start, batch_end)
            except Exception:
                blocks = []
            for block in blocks:
                if not isinstance(block, dict):
                    continue
                block_height = block.get('index') or block.get('height') or 0
                block_hash = block.get('hash') or ''
                timestamp = block.get('timestamp')

                # Block mining reward from metadata
                miner_raw = block.get('miner') or block.get('mined_by') or block.get('miner_address') or block.get('mined_by_address')
                miner_norm = self._normalize_scan_address(miner_raw or '')
                reward_amount = self._parse_scan_amount(block.get('reward', 0) or 0)
                if miner_norm in normalized_map and reward_amount > 0:
                    target_addr = normalized_map[miner_norm]
                    reward_hash = f"reward_{block_height}_{block_hash[:8]}"
                    if reward_hash not in seen[target_addr]:
                        seen[target_addr].add(reward_hash)
                        results[target_addr].append({
                            'type': 'reward',
                            'from': 'network',
                            'to': target_addr,
                            'reward_address': target_addr,
                            'amount': reward_amount,
                            'block_height': block_height,
                            'timestamp': timestamp,
                            'hash': reward_hash,
                            'status': 'confirmed',
                            'direction': 'incoming',
                            'effective_amount': reward_amount,
                            'fee': 0,
                        })

                for tx_index, tx in enumerate(block.get('transactions', []) or []):
                    if not isinstance(tx, dict):
                        continue
                    tx_type = (tx.get('type') or 'transfer').lower()

                    if tx_type == 'reward':
                        reward_to = tx.get('to') or tx.get('receiver') or tx.get('issued_to') or tx.get('owner_address') or tx.get('to_address')
                        reward_norm = self._normalize_scan_address(reward_to or '')
                        if reward_norm in normalized_map:
                            target_addr = normalized_map[reward_norm]
                            amount = self._parse_scan_amount(tx.get('amount', tx.get('denomination', 0) or 0) or 0)
                            reward_hash = tx.get('hash') or f"reward_{block_height}_{tx_index}"
                            if reward_hash not in seen[target_addr]:
                                seen[target_addr].add(reward_hash)
                                enhanced = tx.copy()
                                enhanced.update({
                                    'type': 'reward',
                                    'from': enhanced.get('from', 'network'),
                                    'to': reward_to or target_addr,
                                    'block_height': block_height,
                                    'timestamp': enhanced.get('timestamp', timestamp),
                                    'hash': reward_hash,
                                    'status': 'confirmed',
                                    'tx_index': tx_index,
                                    'direction': 'incoming',
                                    'effective_amount': amount,
                                    'amount': amount,
                                    'fee': 0,
                                    'reward_address': target_addr,
                                })
                                results[target_addr].append(enhanced)
                        continue

                    if tx_type == 'gtx_genesis':
                        reward_to = tx.get('issued_to') or tx.get('owner_address') or tx.get('to') or tx.get('receiver') or tx.get('to_address')
                        reward_norm = self._normalize_scan_address(reward_to or '')
                        if reward_norm in normalized_map:
                            target_addr = normalized_map[reward_norm]
                            amount = self._parse_scan_amount(tx.get('amount', tx.get('denomination', 0) or 0) or 0)
                            reward_hash = tx.get('hash') or f"genesis_reward_{block_height}_{tx_index}"
                            if reward_hash not in seen[target_addr]:
                                seen[target_addr].add(reward_hash)
                                enhanced = tx.copy()
                                enhanced.update({
                                    'type': 'reward',
                                    'from': 'network',
                                    'to': reward_to or target_addr,
                                    'block_height': block_height,
                                    'timestamp': enhanced.get('timestamp', timestamp),
                                    'hash': reward_hash,
                                    'status': 'confirmed',
                                    'tx_index': tx_index,
                                    'direction': 'incoming',
                                    'effective_amount': amount,
                                    'amount': amount,
                                    'fee': 0,
                                    'reward_address': target_addr,
                                    'original_type': 'gtx_genesis',
                                })
                                results[target_addr].append(enhanced)

        return results

    def _get_blockchain_txs_with_fallback(self, addresses: List[str], end_height: Optional[int] = None) -> Dict[str, List[Dict]]:
        results = self.blockchain_manager.scan_transactions_for_addresses(
            addresses,
            start_height=0,
            end_height=end_height,
        )
        if isinstance(results, dict):
            for addr in addresses:
                if results.get(addr):
                    continue
                try:
                    per_addr = self.blockchain_manager.scan_transactions_for_address(
                        addr,
                        start_height=0,
                        end_height=end_height,
                    )
                    if per_addr:
                        results[addr] = per_addr
                except Exception:
                    pass
        else:
            results = {addr: [] for addr in addresses}

        # If no rewards detected, do a one-time reward-like scan (GTX_Genesis -> reward)
        if not getattr(self, '_reward_like_scan_attempted', False):
            has_rewards = False
            for txs in results.values():
                if any((tx.get('type') or '').lower() == 'reward' for tx in (txs or [])):
                    has_rewards = True
                    break
            if not has_rewards:
                self._reward_like_scan_attempted = True
                try:
                    reward_results = self._scan_reward_like_transactions_for_addresses(addresses, start_height=0, end_height=None)
                    if isinstance(reward_results, dict):
                        for addr, txs in reward_results.items():
                            if txs:
                                results.setdefault(addr, []).extend(txs)
                except Exception as scan_err:
                    print(f"DEBUG: reward-like scan failed: {scan_err}")

        return results

    def _start_wallet_manager_sync(self):
        if getattr(self, '_wallet_manager_sync_started', False):
            return
        manager = self._ensure_wallet_state_manager()
        if not manager:
            return

        def _get_blockchain_data(addresses):
            try:
                end_height = None
                cache = getattr(self.blockchain_manager, 'cache', None)
                if cache:
                    cached_height = cache.get_highest_cached_height()
                    if isinstance(cached_height, int) and cached_height > 0:
                        end_height = cached_height
                results = self._get_blockchain_txs_with_fallback(addresses, end_height=end_height)
                if isinstance(results, dict) and not any(results.values()):
                    return self.get_cached_transactions_for_addresses(addresses)
                return results
            except Exception as e:
                print(f"DEBUG: wallet manager blockchain fetch failed: {e}")
                return {addr: [] for addr in addresses}

        def _get_mempool_data(addresses):
            try:
                if self.mempool_manager and hasattr(self.mempool_manager, 'get_pending_transactions_for_addresses'):
                    return self.mempool_manager.get_pending_transactions_for_addresses(addresses, fetch_remote=True)
            except Exception as e:
                print(f"DEBUG: wallet manager mempool fetch failed: {e}")
            return {addr: [] for addr in addresses}

        manager.sync_wallets_background(_get_blockchain_data, _get_mempool_data, poll_interval=30)
        self._wallet_manager_sync_started = True

    def get_wallet_manager_transactions(self, address: str, force_sync: bool = False) -> List[Dict]:
        manager = self._ensure_wallet_state_manager()
        if not manager:
            return []
        if force_sync:
            try:
                addresses = list(getattr(self.wallet_core, 'wallets', {}).keys()) or [address]
                end_height = None
                cache = getattr(self.blockchain_manager, 'cache', None)
                if cache:
                    cached_height = cache.get_highest_cached_height()
                    if isinstance(cached_height, int) and cached_height > 0:
                        end_height = cached_height
                blockchain_txs = self._get_blockchain_txs_with_fallback(addresses, end_height=end_height)
                if isinstance(blockchain_txs, dict) and not any(blockchain_txs.values()):
                    blockchain_txs = self.get_cached_transactions_for_addresses(addresses)
                mempool_txs = {}
                if self.mempool_manager and hasattr(self.mempool_manager, 'get_pending_transactions_for_addresses'):
                    mempool_txs = self.mempool_manager.get_pending_transactions_for_addresses(addresses, fetch_remote=True)
                manager.sync_wallets_from_sources(blockchain_txs, mempool_txs)
            except Exception as e:
                print(f"DEBUG: wallet manager force sync failed: {e}")
        try:
            # Use wallet_manager categories to omit GTX_Genesis from history
            transfers = manager.get_transactions(address, 'transfers')
            rewards = manager.get_transactions(address, 'rewards')
            combined = []
            seen = set()
            for tx in (transfers or []):
                tx_hash = tx.get('hash')
                if tx_hash and tx_hash in seen:
                    continue
                if tx_hash:
                    seen.add(tx_hash)
                combined.append(tx)
            for tx in (rewards or []):
                tx_hash = tx.get('hash')
                if tx_hash and tx_hash in seen:
                    continue
                if tx_hash:
                    seen.add(tx_hash)
                combined.append(tx)
            combined.sort(key=lambda x: x.get('timestamp', 0), reverse=True)
            return combined
        except Exception:
            return []

    def get_wallet_manager_balance(self, address: str, force_sync: bool = False) -> Optional[Dict]:
        manager = self._ensure_wallet_state_manager()
        if not manager:
            return None
        if force_sync:
            _ = self.get_wallet_manager_transactions(address, force_sync=True)
        try:
            return manager.get_balance(address)
        except Exception:
            return None

    def force_rescan_blockchain(self):
        """Force a full blockchain rescan for all wallets."""
        try:
            if hasattr(self, 'blockchain_service') and self.blockchain_service:
                if hasattr(self.blockchain_service, 'reset_cache'):
                    self.blockchain_service.reset_cache()
            manager = self._ensure_wallet_state_manager()
            if manager and hasattr(manager, 'clear_all_caches'):
                manager.clear_all_caches()

            if not hasattr(self, 'wallet_core') or not self.wallet_core:
                return
            addresses = list(getattr(self.wallet_core, 'wallets', {}).keys())
            if not addresses or not hasattr(self, 'blockchain_manager') or not self.blockchain_manager:
                return

            latest_block = self.blockchain_manager.get_latest_block()
            end_height = latest_block.get('index', 0) if latest_block else None
            if end_height is None:
                end_height = self.blockchain_manager.get_blockchain_height()

            blockchain_txs = self._get_blockchain_txs_with_fallback(addresses, end_height=end_height)
            mempool_txs = {}
            if self.mempool_manager and hasattr(self.mempool_manager, 'get_pending_transactions_for_addresses'):
                mempool_txs = self.mempool_manager.get_pending_transactions_for_addresses(addresses, fetch_remote=True)
            if manager:
                manager.sync_wallets_from_sources(blockchain_txs, mempool_txs)

            self.last_scanned_block = end_height or 0
            self.initial_scan_complete = True
            try:
                self._refresh_ui_after_scan(force_update=True)
            except Exception:
                pass
        except Exception as e:
            print(f"DEBUG: force_rescan_blockchain failed: {e}")

    def _sync_wallets_with_lunalib(self) -> bool:
        try:
            # Prefer wallet's built-in sync if available
            if hasattr(self.wallet_core, 'sync_with_state_manager'):
                self.wallet_core.sync_with_state_manager(
                    blockchain=self.blockchain_manager,
                    mempool=self.mempool_manager
                )
                return True
        except Exception as e:
            print(f"DEBUG: wallet_core sync_with_state_manager failed: {e}")

        helper = self._ensure_wallet_sync_helper()
        if not helper:
            return False
        try:
            # Refresh registered wallets each sync
            if hasattr(helper, 'register_wallets_from_lunawallet'):
                helper.register_wallets_from_lunawallet()
            elif hasattr(helper, 'register_wallets'):
                helper.register_wallets()

            if hasattr(helper, 'sync_wallets_now'):
                helper.sync_wallets_now()
            elif hasattr(helper, 'sync_wallets'):
                helper.sync_wallets()
            elif hasattr(helper, 'sync'):
                helper.sync()
            return True
        except Exception as e:
            print(f"DEBUG: wallet sync helper failed: {e}")
            return False

    def scan_all_wallets_for_changes(self, force_full_scan=False):
        """
        Scan wallets for transactions using lunalib built-in sync.
        """
        show_ready = threading.Event()

        def _show_scan_loading():
            try:
                if hasattr(self, 'wallet_page') and self.wallet_page:
                    def _do_show():
                        try:
                            self.wallet_page.show_sync_status("Scanning Transactions...")
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
                    self.wallet_page.hide_sync_status()
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
            
            # Use lunalib wallet sync helper
            if not self._sync_wallets_with_lunalib():
                print("DEBUG: lunalib wallet sync not available")
                return

            # Refresh UI after lunalib sync completes
            try:
                self._refresh_ui_after_scan(force_update=True)
            except Exception as refresh_err:
                print(f"DEBUG: refresh after lunalib sync failed: {refresh_err}")
            
        except Exception as e:
            print(f"DEBUG: Error in scan_all_wallets_for_changes: {e}")
            import traceback
            traceback.print_exc()
            try:
                from app.debug_logger import debug_log
                debug_log(f"[SCAN][ERROR] scan_all_wallets_for_changes: {e}")
            except Exception:
                pass
        finally:
            try:
                elapsed = time.time() - start_time
                min_visible = 0.5
                if elapsed < min_visible:
                    time.sleep(min_visible - elapsed)
            except Exception:
                pass
            _hide_scan_loading()

    def _integrity_check_base_url(self, peer_latest_block: dict):
        """Check local node's latest block vs peer's latest block using lunalib only."""
        import time
        try:
            if is_web():
                return
            now = time.time()
            if (now - self.last_integrity_check_time) < self.integrity_check_interval_seconds:
                return

            # Get peer's latest block info
            peer_height = None
            peer_hash = None
            if isinstance(peer_latest_block, list) and peer_latest_block:
                peer_latest_block = peer_latest_block[-1]
            if isinstance(peer_latest_block, dict):
                peer_height = peer_latest_block.get("index") or peer_latest_block.get("height")
                peer_hash = peer_latest_block.get("hash") or peer_latest_block.get("block_hash")

            # Get local node's latest block using lunalib
            if not hasattr(self, "blockchain_manager") or not self.blockchain_manager:
                print("[INTEGRITY] No blockchain_manager available for integrity check.")
                return
            local_block = self.blockchain_manager.get_latest_block()
            if not local_block:
                print("[INTEGRITY] Could not get local latest block from lunalib.")
                return
            local_height = local_block.get("index") or local_block.get("height")
            local_hash = local_block.get("hash") or local_block.get("block_hash")

            # Compare
            if peer_height is not None and local_height is not None:
                ui_refresh_needed = False
                if int(peer_height) != int(local_height):
                    print(f"[INTEGRITY] Height mismatch: peer={peer_height}, local={local_height}")
                    self.show_snackbar("Integrity check: height mismatch", "warning")
                    ui_refresh_needed = True
                elif peer_hash and local_hash and str(peer_hash) != str(local_hash):
                    print(f"[INTEGRITY] Hash mismatch at height {peer_height}")
                    self.show_snackbar("Integrity check: hash mismatch", "warning")
                    ui_refresh_needed = True
                else:
                    print("[INTEGRITY] Local node matches peer latest block")
                if ui_refresh_needed:
                    # サイドバー・カード・履歴を即時リフレッシュ
                    self.refresh_wallet_list()
                    if hasattr(self, 'wallet_page') and self.wallet_page:
                        if hasattr(self.wallet_page, 'refresh_transaction_history'):
                            self.wallet_page.refresh_transaction_history()
                        if hasattr(self.wallet_page, '_update_wallet_data_ui_only'):
                            self.wallet_page._update_wallet_data_ui_only()
            self.last_integrity_check_time = now
        except Exception as e:
            print(f"[INTEGRITY] Error in lunalib-only integrity check: {e}")
    def _check_mempool_for_pending(self, wallet_addresses):
        """Check mempool for pending transactions using batch API"""
        try:
            from lunalib.core.mempool import MempoolManager
            mempool_manager = MempoolManager()
            
            _safe_print(f"\n=== CHECKING MEMPOOL FOR {len(wallet_addresses)} WALLETS ===")
            
            # Use new batch method: get_pending_transactions_for_addresses(addresses: List[str])
            # Returns Dict[str, List[Dict]] where keys are addresses
            _safe_print(f"[OK] Using batch get_pending_transactions_for_addresses()")
            all_pending = mempool_manager.get_pending_transactions_for_addresses(wallet_addresses, fetch_remote=True)
                
            for wallet_addr in wallet_addresses:
                wallet_addr_lower = wallet_addr.lower()
                pending_txs = all_pending.get(wallet_addr_lower, []) or all_pending.get(wallet_addr, [])
                
                if pending_txs:
                    _safe_print(f"[OK] Found {len(pending_txs)} pending transactions for {wallet_addr[:12]}...")
                    for i, tx in enumerate(pending_txs):
                        tx_hash = tx.get('hash', 'unknown')
                        tx_from = tx.get('from', 'unknown')
                        tx_to = tx.get('to', 'unknown')
                        tx_amount = tx.get('amount', 0)
                        _safe_print(f"  [{i+1}] hash={tx_hash[:8] if isinstance(tx_hash, str) else tx_hash}...")
                        _safe_print(f"      from={tx_from[:8] if isinstance(tx_from, str) else tx_from}... -> to={tx_to[:8] if isinstance(tx_to, str) else tx_to}...")
                        _safe_print(f"      amount={tx_amount}")
                        
                        # Mark as pending and save to storage
                        tx['status'] = 'pending'
                        self._store_transaction(wallet_addr, tx, status='pending')
                        _safe_print(f"      Saved to storage")
                        
                        # Update balance incrementally for pending transaction
                        self._update_wallet_balance_incremental(wallet_addr, tx)
                else:
                    _safe_print(f"[OK] No pending transactions for {wallet_addr[:12]}...")
            else:
                # Fallback to single-address method
                _safe_print(f"[WARN] Batch mempool not available, falling back to single-address method")
                for wallet_addr in wallet_addresses:
                    try:
                        pending_txs = mempool_manager.get_pending_transactions(wallet_addr)
                        
                        if pending_txs:
                            _safe_print(f"[OK] Found {len(pending_txs)} pending transactions for {wallet_addr[:12]}...")
                            for i, tx in enumerate(pending_txs):
                                tx_hash = tx.get('hash', 'unknown')
                                tx_from = tx.get('from', 'unknown')
                                tx_to = tx.get('to', 'unknown')
                                tx_amount = tx.get('amount', 0)
                                _safe_print(f"  [{i+1}] hash={tx_hash[:8] if isinstance(tx_hash, str) else tx_hash}...")
                                _safe_print(f"      from={tx_from[:8] if isinstance(tx_from, str) else tx_from}... -> to={tx_to[:8] if isinstance(tx_to, str) else tx_to}...")
                                _safe_print(f"      amount={tx_amount}")
                                
                                # Mark as pending and save to storage
                                tx['status'] = 'pending'
                                self._store_transaction(wallet_addr, tx, status='pending')
                                _safe_print(f"      Saved to storage")
                                
                                # Update balance incrementally for pending transaction
                                self._update_wallet_balance_incremental(wallet_addr, tx)
                        else:
                            _safe_print(f"[OK] No pending transactions for {wallet_addr[:12]}...")
                            
                    except Exception as e:
                        _safe_print(f"[ERROR] Mempool check error for {wallet_addr[:12]}...: {e}")
                        import traceback
                        traceback.print_exc()
            
            _safe_print(f"=== MEMPOOL CHECK COMPLETE ===\n")
                    
        except Exception as e:
            _safe_print(f"[ERROR] Mempool check failed: {e}")
            import traceback
            traceback.print_exc()

    def _detect_new_incoming_transactions(self, wallet_addresses):
        """
        Detect NEW incoming transactions that haven't been seen before.
        Mark existing transactions as 'old' so we don't replay sound on rescan.
        Play sound for new incoming transactions.
        """
        try:
            _safe_print(f"\n=== DETECTING NEW TRANSACTIONS ===")
            
            # Get all transactions from storage
            all_txs = []
            if hasattr(self, 'get_all_transactions'):
                all_txs = self.get_all_transactions()
            
            if not all_txs:
                print("No transactions in database")
                return
            
            # Process each wallet
            for wallet_addr in wallet_addresses:
                wallet_addr_lower = wallet_addr.lower()
                
                # Find transactions for this wallet
                wallet_txs = [tx for tx in all_txs if 
                             (str(tx.get('to', '')).lower() == wallet_addr_lower or 
                              str(tx.get('reward_address', '')).lower() == wallet_addr_lower or
                              str(tx.get('recipient', '')).lower() == wallet_addr_lower)]
                
                _safe_print(f"\n  Checking {len(wallet_txs)} transactions for {wallet_addr[:12]}...")
                
                wallet_obj = self.wallet_core.wallets.get(wallet_addr, {}) if hasattr(self, 'wallet_core') else {}
                seen_ids = wallet_obj.get('seen_tx_ids', []) if isinstance(wallet_obj, dict) else []
                if not isinstance(seen_ids, list):
                    seen_ids = []

                for tx in wallet_txs:
                    tx_id = self._get_tx_unique_id(tx)
                    if tx_id in seen_ids:
                        continue

                    seen_ids.append(tx_id)

                    is_incoming = (str(tx.get('to', '')).lower() == wallet_addr_lower or
                                  str(tx.get('reward_address', '')).lower() == wallet_addr_lower or
                                  str(tx.get('recipient', '')).lower() == wallet_addr_lower)

                    tx_type = str(tx.get('type', 'transfer')).lower()
                    amount = tx.get('amount', 0)

                    if is_incoming:
                        _safe_print(f"    NEW incoming {tx_type}: {amount} LKC")
                        # Play reward.wav for reward/fee_distribution, else transaction.wav
                        if tx_type in ("reward", "fee_distribution"):
                            if self._should_play_incoming_sound("reward"):
                                self._play_sound("reward")
                                self._mark_incoming_sound("reward")
                        else:
                            if self._should_play_incoming_sound("transaction"):
                                self._play_sound("transaction")
                                self._mark_incoming_sound("transaction")

                if isinstance(wallet_obj, dict):
                    wallet_obj['seen_tx_ids'] = seen_ids
                    try:
                        self.save_wallet_data(force_save=True)
                    except Exception:
                        pass
            
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
                    _safe_print(f"  [INC] +{amount} reward")
            elif tx_type == 'fee_distribution':
                if (tx_to == wallet_addr_lower or reward_addr == wallet_addr_lower or recipient_addr == wallet_addr_lower):
                    wallet_obj['confirmed_balance'] += amount
                    _safe_print(f"  [INC] +{amount} fee distribution")
            elif tx_to == wallet_addr_lower:
                wallet_obj['confirmed_balance'] += amount
                _safe_print(f"  [INC] +{amount} transfer in")
            elif tx_from == wallet_addr_lower:
                wallet_obj['confirmed_balance'] -= (amount + fee)
                _safe_print(f"  [INC] -{amount} -{fee} transfer out")
        elif tx_status == 'pending':
            # Update pending balance for unconfirmed transactions
            if tx_type in ('reward', 'fee_distribution'):
                if tx_to == wallet_addr_lower or reward_addr == wallet_addr_lower or recipient_addr == wallet_addr_lower:
                    wallet_obj['pending_balance'] += amount
                    _safe_print(f"  [INC] +{amount} pending reward")
            elif tx_to == wallet_addr_lower:
                wallet_obj['pending_balance'] += amount
                _safe_print(f"  [INC] +{amount} pending in")
            elif tx_from == wallet_addr_lower:
                wallet_obj['pending_balance'] -= (amount + fee)
                _safe_print(f"  [INC] -{amount} -{fee} pending out")
        
        # Update total balance
        wallet_obj['available_balance'] = max(0.0, wallet_obj['confirmed_balance'])
        wallet_obj['balance'] = max(0.0, wallet_obj['confirmed_balance']) + wallet_obj['pending_balance']

    def _get_tx_unique_id(self, tx: dict) -> str:
        base_hash = tx.get('hash') or tx.get('transaction_id')
        if base_hash:
            return str(base_hash)
        return f"{tx.get('type','tx')}_{tx.get('block_height','')}_{tx.get('timestamp','')}"

    def _is_reward_for_wallet(self, tx: dict, wallet_addr_lower: str) -> bool:
        tx_type = str(tx.get('type', '')).lower()
        if tx_type not in ('reward', 'fee_distribution'):
            return False
        tx_to = str(tx.get('to', '')).lower()
        reward_addr = str(tx.get('reward_address', '')).lower()
        recipient_addr = str(tx.get('recipient', '')).lower()
        return tx_to == wallet_addr_lower or reward_addr == wallet_addr_lower or recipient_addr == wallet_addr_lower

    def _handle_reward_detected(self, wallet_addr: str, tx: dict, notify: bool = True):
        if wallet_addr not in self.wallet_core.wallets:
            return
        wallet_obj = self.wallet_core.wallets[wallet_addr]
        tx_id = self._get_tx_unique_id(tx)
        seen = wallet_obj.get('seen_reward_ids', [])
        if not isinstance(seen, list):
            seen = []

        if tx_id not in seen:
            seen.append(tx_id)
            wallet_obj['seen_reward_ids'] = seen
            if notify:
                amount = tx.get('amount', 0)
                print(f"[REWARD] New reward detected: {amount} LKC for {wallet_addr[:12]}...")
                if self._should_play_incoming_sound("reward"):
                    self._play_sound("reward")
                    self._mark_incoming_sound("reward")
                self.show_snackbar(f"Reward received: {amount} LKC", "success")
            # Persist updated wallet data
            try:
                self.save_wallet_data(force_save=True)
            except Exception as e:
                print(f"[REWARD] save_wallet_data failed: {e}")

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
                        self.wallet_page.refresh_transaction_history(force_scan=True)
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
        
        helper = self._ensure_wallet_sync_helper()
        if helper and hasattr(helper, 'start_continuous_sync'):
            self.continuous_scan_active = True
            print(f"DEBUG: Starting lunalib continuous sync (every {self.scan_interval}s)")
            try:
                helper.start_continuous_sync(poll_interval=int(self.scan_interval))
                return
            except Exception as e:
                print(f"DEBUG: lunalib continuous sync failed: {e}")

        # Fallback to periodic sync loop if helper isn't available
        self.continuous_scan_active = True
        print("DEBUG: Starting continuous sync loop (every 30 seconds)")

        def continuous_scan_loop():
            time.sleep(self.scan_interval)
            while self.continuous_scan_active and not self.is_locked:
                try:
                    self.scan_all_wallets_for_changes()
                    time.sleep(self.scan_interval)
                except Exception as e:
                    print(f"DEBUG: Continuous scan error: {e}")
                    time.sleep(self.scan_interval)

        threading.Thread(target=continuous_scan_loop, daemon=True).start()

if __name__ == "__main__":
    ft.app(target=LunaWalletApp().create_main_ui)

import os
import sys
import threading
import shutil
import platform
# Ensure local packages (./cryptography, ./certifi) shadow site-packages
sys.path.insert(0, os.path.dirname(__file__))

# Prevent leaking paths from other projects (e.g., via PYTHONPATH)
os.environ.pop("PYTHONPATH", None)

# Enable tiny-decimal amounts in lunalib (must be set before lunalib imports)
os.environ.setdefault("LUNALIB_AMOUNT_TINY_DECIMALS", "1")


def _prune_foreign_venv_paths():
    """Remove unrelated/old venv paths from sys.path (e.g., other projects)."""
    try:
        current_venv = os.environ.get("VIRTUAL_ENV")
        keep_prefixes = []
        if current_venv:
            keep_prefixes.append(os.path.normpath(current_venv))
        # Always keep current interpreter prefixes
        keep_prefixes.extend([os.path.normpath(sys.prefix), os.path.normpath(sys.base_prefix)])

        cleaned = []
        for p in sys.path:
            if not p:
                cleaned.append(p)
                continue
            norm = os.path.normpath(p)

            # Drop anything under /Programs/ that isn't this project
            if "/Programs/" in norm.replace("\\", "/") and "LunaWallet" not in norm:
                continue

            # Drop obvious foreign/old venvs
            if ".venv.old" in norm or "Gambler" in norm:
                continue

            # If it looks like a venv site-packages and it's not current, drop it
            if ("site-packages" in norm or "dist-packages" in norm) and keep_prefixes:
                if not any(norm.startswith(k) for k in keep_prefixes):
                    continue

            cleaned.append(p)

        sys.path[:] = cleaned
    except Exception:
        pass


def _ensure_flet_storage_dir():
    """Set FLET_APP_STORAGE to a writable path on Linux if missing."""
    if os.getenv("FLET_APP_STORAGE"):
        return
    try:
        if sys.platform.startswith("linux"):
            # Ensure Flet home exists to avoid MissingPlatformDirectoryException
            flet_home = os.getenv("FLET_HOME")
            if not flet_home:
                flet_home = os.path.join(os.path.expanduser("~"), ".flet")
                os.environ["FLET_HOME"] = flet_home
            os.makedirs(flet_home, exist_ok=True)

            # WSL hint (harmless on non-WSL, but helps if running under WSL)
            if "microsoft" in " ".join(platform.uname()).lower():
                os.environ["FLET_WSL"] = "true"

            base_dir = os.getenv("XDG_DATA_HOME")
            if not base_dir:
                base_dir = os.path.join(os.path.expanduser("~"), ".local", "share")
            storage_dir = os.path.join(base_dir, "LunaWallet")
            os.makedirs(storage_dir, exist_ok=True)
            os.environ["FLET_APP_STORAGE"] = storage_dir
    except Exception:
        pass


def _ensure_xdg_user_dirs():
    """Ensure XDG user dirs exist on Linux to avoid MissingPlatformDirectoryException."""
    try:
        if not sys.platform.startswith("linux"):
            return
        home_dir = os.path.expanduser("~")
        if not home_dir:
            return
        config_dir = os.path.join(home_dir, ".config")
        user_dirs_file = os.path.join(config_dir, "user-dirs.dirs")
        documents_dir = os.path.join(home_dir, "Documents")

        if not os.path.isdir(documents_dir):
            os.makedirs(documents_dir, exist_ok=True)

        if not os.path.isfile(user_dirs_file):
            os.makedirs(config_dir, exist_ok=True)
            with open(user_dirs_file, "w", encoding="utf-8") as f:
                f.write('XDG_DOCUMENTS_DIR="$HOME/Documents"\n')

        # Also set env for current process/session
        os.environ.setdefault("XDG_DOCUMENTS_DIR", documents_dir)
    except Exception:
        pass


_prune_foreign_venv_paths()
_ensure_xdg_user_dirs()
_ensure_flet_storage_dir()


def _ensure_lunalib_on_path():
    """Ensure lunalib is discoverable on Android APK runtime."""
    try:
        import lunalib  # noqa: F401
        return
    except Exception:
        pass

    base_dir = os.path.dirname(__file__)
    flet_root = os.path.abspath(os.path.join(base_dir, ".."))

    # Likely package roots in Flet APK layout
    candidates = [
        os.path.join(flet_root, "site-packages"),
        os.path.join(flet_root, "packages"),
        os.path.join(flet_root, "python", "site-packages"),
    ]

    for candidate in candidates:
        if os.path.isdir(candidate) and candidate not in sys.path:
            sys.path.insert(0, candidate)

    # Fallback: search for a folder that contains lunalib
    max_depth = 4
    base_depth = flet_root.count(os.sep)
    for root, dirs, _files in os.walk(flet_root):
        if root.count(os.sep) - base_depth > max_depth:
            dirs[:] = []
            continue
        if "lunalib" in dirs:
            if root not in sys.path:
                sys.path.insert(0, root)
            break


_ensure_lunalib_on_path()

from app.core import LunaWalletApp
from gui.page_wallet_index import WalletIndexPage
from typing import List, Dict
if __name__ == "__main__":
    import flet as ft
    ft.app(target=LunaWalletApp().create_main_ui)
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
            # Use Flet audio for mobile compatibility (if available)
            if not hasattr(ft, "Audio"):
                print("Sound error: Flet Audio not available on this platform")
                return
            if sound_type == "transaction":
                audio = ft.Audio(
                    src="transaction.wav",
                    autoplay=True,
                )
                self.page.overlay.append(audio)
                print("play transaction sound")
                self.page.update()
            elif sound_type == "reward":
                audio = ft.Audio(
                    src="reward.wav",
                    autoplay=True,
                )
                self.page.overlay.append(audio)
                print("play reward sound")
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
        """Load wallet metadata using lunalib's SQLite backend (no password required)"""
        print("DEBUG: _load_wallet_metadata called")
        try:
            if hasattr(self.wallet_core, "get_wallet_index"):
                wallet_index = self.wallet_core.get_wallet_index()
                count = len(wallet_index) if wallet_index else 0
                print(f"DEBUG: _load_wallet_metadata found {count} wallets")
                return bool(wallet_index)
        except Exception as e:
            print(f"DEBUG: _load_wallet_metadata error: {e}")
        return False

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
            if hasattr(self, 'database') and hasattr(self.database, 'data_dir') and self.database.data_dir:
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

        try:
            # Try to load from database instead of JSON file
            if hasattr(self, 'database') and self.database:
                wallet_addresses = self.database.get_all_wallet_addresses()
                if wallet_addresses:
                    self.wallet_count = len(wallet_addresses)
                    self.existing_wallet_address = wallet_addresses[0]
                    print(f"DEBUG: Found {self.wallet_count} wallets in database, first address: {self.existing_wallet_address}")
                    return True
            
            self.wallet_count = 0
            self.existing_wallet_address = None
            print("DEBUG: No wallets found in database")
            return False
        except Exception as e:
            print(f"DEBUG: Error loading wallet metadata (lunalib): {e}")
            import traceback
            traceback.print_exc()
            self.wallet_count = 0
            self.existing_wallet_address = None
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
            self.update_refs()

    def on_transaction_received(self):
        """Handle incoming transactions with auto-save"""
        try:
            # Use Flet audio for mobile/Desktop compatibility
            if self._should_play_incoming_sound("transaction"):
                self._play_sound("transaction")
                self._mark_incoming_sound("transaction")
        except Exception as e:
            print(f"Error playing sound: {e}")

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

        # --- UI描画はここで初めて呼ぶ ---
        self.initialize_wallet_state()  # Shows unlock or create screen as appropriate
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

    def show_wallet_page(self, reuse: bool = False):
        """Display the main wallet page or wallet index for mobile."""
        try:
            print("DEBUG: show_wallet_page called")

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

            # Fast path: reuse existing wallet page view when available
            if reuse and hasattr(self, "wallet_page_view") and self.wallet_page_view:
                self.current_page = self.wallet_page_view
                if hasattr(self, 'page') and self.page:
                    try:
                        self.page.clean()
                    except Exception:
                        self.page.controls.clear()
                    self.page.add(self.current_page)
                    self.page.update()
                return

            self.show_snackbar("Loading wallet page...", "info")
            _trace("[WALLET_PAGE] begin create")

            if getattr(self, 'is_mobile', False):
                # モバイル：ウォレットインデックスページを表示
                def on_select_wallet(address):
                    self.show_mobile_wallet_page(address)
                def on_create_wallet():
                    self.show_create_wallet()
                def on_import_wallet():
                    self.on_import_wallet()
                wallet_index_page = WalletIndexPage(
                    app=self,
                    on_select_wallet=on_select_wallet,
                    on_create_wallet=on_create_wallet,
                    on_import_wallet=on_import_wallet
                )
                self.current_page = wallet_index_page.create()
                self.page.controls.clear()
                self.page.add(self.current_page)
                self.page.update()
                _trace("[WALLET_INDEX_PAGE] displayed (mobile)")
                print("DEBUG: Wallet index page displayed (mobile)")
                return

            # デスクトップ：従来通りWalletPage
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
            self.wallet_page = wallet_page
            try:
                self.current_page = wallet_page.create()
                self.wallet_page_view = self.current_page
                _trace("[WALLET_PAGE] create succeeded")
                self.show_snackbar("Wallet page created", "success")
            except Exception as create_err:
                _trace(f"[WALLET_PAGE] create failed: {create_err}")
                self.show_snackbar(f"Wallet page error: {create_err}", "error")
                raise
            if hasattr(self, 'page') and self.page:
                try:
                    self.page.clean()
                except Exception:
                    self.page.controls.clear()
                self.page.add(self.current_page)
                self.page.update()
            print("DEBUG: Wallet page displayed successfully")
            _trace("[WALLET_PAGE] displayed")
        except Exception as e:
            print(f"DEBUG: Error showing wallet page: {e}")
            import traceback
            traceback.print_exc()

    def show_mobile_wallet_page(self, address):
        """モバイル用：ウォレット選択後に詳細ページを表示"""
        from gui.page_wallet import WalletPage
        print(f"DEBUG: show_mobile_wallet_page({address}) called")
        # 現在のウォレットアドレスをセット
        if hasattr(self.wallet_core, 'current_wallet_address'):
            self.wallet_core.current_wallet_address = address
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
        self.wallet_page = wallet_page
        self.current_page = wallet_page.create()
        self.page.controls.clear()
        self.page.add(self.current_page)
        self.page.update()
        print("DEBUG: Mobile wallet page displayed for address", address)

    def lock_wallet(self):
        """Lock the wallet and return to lock screen"""
        print("DEBUG: lock_wallet called")
        self.is_locked = True
        self.continuous_scan_active = False  # Stop continuous scanning
        self.show_lock_page(
            title="Wallet Locked",
            subtitle="Enter password to unlock",
            wallet_exists=True,
            show_create=False
        )

    def on_send_transaction(self):
        """Handle send transaction action"""
        print("DEBUG: on_send_transaction called")
        try:
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
        except Exception as e:
            print(f"DEBUG: Error showing send page: {e}")
            import traceback
            traceback.print_exc()
            self.show_snackbar(f"Error opening send page: {str(e)}", "error")

    def on_receive(self):
        """Handle receive action"""
        print("DEBUG: on_receive called")
        try:
            receive_page = ReceivePage(
                self,
                on_back=self.show_wallet_page
            )
            self.current_page = receive_page.create()
            self.page.controls.clear()
            self.page.add(self.current_page)
            self.page.update()
            print("DEBUG: Receive page displayed")
        except Exception as e:
            print(f"DEBUG: Error showing receive page: {e}")
            import traceback
            traceback.print_exc()
            self.show_snackbar(f"Error opening receive page: {str(e)}", "error")

    def on_export_key(self):
        """Handle export key action"""
        print("DEBUG: on_export_key called")
        try:
            export_key_page = ExportKeyPage(
                self,
                on_back=lambda: self.show_wallet_page(reuse=True)
            )
            self.current_page = export_key_page.create()
            self.page.controls.clear()
            self.page.add(self.current_page)
            self.page.update()
            print("DEBUG: Export key page displayed")
        except Exception as e:
            print(f"DEBUG: Error showing export key page: {e}")
            import traceback
            traceback.print_exc()
            self.show_snackbar(f"Error opening export key page: {str(e)}", "error")

    def on_transaction_sent(self):
        """Handle transaction sent confirmation"""
        print("DEBUG: on_transaction_sent called")
        self.show_snackbar("Transaction sent successfully!", "success")
        # Return to wallet page
        self.show_wallet_page()

    def on_lock(self):
        """Handle lock action - lock the wallet"""
        print("DEBUG: on_lock called")
        self.is_locked = True
        self.show_lock_page(
            title="Wallet Locked",
            subtitle="Enter password to unlock",
            wallet_exists=True,
            show_create=False
        )
    def on_lock(self):
        """Handle lock action - lock the wallet using lunalib 1.7.3 API"""
        print("DEBUG: on_lock called")
        if self.wallet_core and self.wallet_core.current_wallet_address:
            self.wallet_core.lock_wallet(self.wallet_core.current_wallet_address)
        self.is_locked = True
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

    def on_settings(self):
        """Handle settings action"""
        print("DEBUG: on_settings called")
        self.show_snackbar("Settings feature", "info")

    def unlock_wallet(self, password):
        """Unlock the first wallet in the database using lunalib's SQLite backend"""
        def _run_on_ui(callback):
            try:
                if hasattr(self, 'page') and self.page and hasattr(self.page, 'call_from_thread'):
                    self.page.call_from_thread(callback)
                    return
                callback()
            except Exception:
                try:
                    callback()
                except Exception:
                    pass

        def unlock_thread():
            try:
                print("DEBUG: Starting unlock process (SQLite backend)...")
                print(f"DEBUG: wallet_core instance: {self.wallet_core}")
                print(f"DEBUG: wallet_core.db: {getattr(self.wallet_core, 'db', None)}")
                wallet_index = self.wallet_core.get_wallet_index()
                print(f"DEBUG: wallet_index: {wallet_index}")
                if not wallet_index:
                    print("DEBUG: No wallets found in database")
                    _run_on_ui(lambda: self.show_snackbar("No wallets found to unlock", "error"))
                    return
                address = wallet_index[0]["address"]
                print(f"DEBUG: Attempting to unlock wallet address: {address}")
                result = self.wallet_core.unlock_wallet(address, password)
                print(f"DEBUG: unlock_wallet result: {result}")
                success = result.get("success", False)
                def update_ui():
                    # File trace for builds
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
                    _trace("[UNLOCK] update_ui entered")
                    if success:
                        print("DEBUG: Unlock successful - transitioning to wallet page")
                        self.is_locked = False
                        self.last_activity_time = time.time()
                        self.show_snackbar("Wallet unlocked successfully", "success")
                        try:
                            _trace("[UNLOCK] calling show_wallet_page")
                            self.show_wallet_page()
                            _trace("[UNLOCK] show_wallet_page returned")
                        except Exception as wallet_page_error:
                            _trace(f"[UNLOCK] show_wallet_page failed: {wallet_page_error}")
                            print(f"DEBUG: Error showing wallet page: {wallet_page_error}")
                            import traceback
                            traceback.print_exc()
                            self.show_snackbar(f"Error showing wallet: {str(wallet_page_error)}", "error")
                            if hasattr(self, 'current_lock_page') and self.current_lock_page:
                                self.current_lock_page.hide_loading()
                            return
                        try:
                            if hasattr(self, 'page') and self.page:
                                self.page.update()
                                try:
                                    _trace(f"[UNLOCK] page controls after update: {len(self.page.controls)}")
                                except Exception:
                                    pass
                                _trace("[UNLOCK] page.update after show_wallet_page")
                            else:
                                _trace("[UNLOCK] page missing after show_wallet_page")
                        except Exception as upd_err:
                            _trace(f"[UNLOCK] page.update failed: {upd_err}")
                            print(f"DEBUG: page.update failed: {upd_err}")
                        try:
                            self.start_blockchain_sync()
                        except Exception as sync_error:
                            print(f"DEBUG: Error starting blockchain sync: {sync_error}")
                    else:
                        print(f"DEBUG: Unlock failed - {result.get('error')}")
                        self.show_snackbar(f"Failed to unlock wallet: {result.get('error', 'Unknown error')}", "error")
                        if hasattr(self, 'current_lock_page') and self.current_lock_page:
                            self.current_lock_page.hide_loading()
                _run_on_ui(update_ui)
            except Exception as e:
                print(f"DEBUG: Unlock error: {e}")
                import traceback
                traceback.print_exc()
                def show_error():
                    self.show_snackbar(f"Unlock error: {str(e)}", "error")
                    if hasattr(self, 'current_lock_page') and self.current_lock_page:
                        self.current_lock_page.hide_loading()
                _run_on_ui(show_error)
        threading.Thread(target=unlock_thread, daemon=True).start()

    def start_blockchain_sync(self):
        """Start blockchain synchronization for all wallets"""
        try:
            print("DEBUG: Starting blockchain sync for all wallets...")
            
            def sync_thread():
                """Synchronize blockchain for all wallets using lunalib."""
                try:
                    print("DEBUG: Starting blockchain sync using lunalib...")

                    self._show_scan_overlay("Scanning Transactions...")

                    # Perform a full blockchain scan using lunalib
                    if hasattr(self.blockchain_manager, 'scan_for_updates'):
                        self.blockchain_manager.scan_for_updates()
                        print("DEBUG: Blockchain sync completed using lunalib.")
                    else:
                        # Fallback: scan transactions for all wallets
                        if hasattr(self.wallet_core, 'wallets'):
                            for wallet_addr in self.wallet_core.wallets.keys():
                                txs = self.blockchain_manager.scan_transactions_for_address(wallet_addr)
                                print(f"DEBUG: Scanned {len(txs)} transactions for {wallet_addr[:12]}...")
                        print("DEBUG: Blockchain sync completed using fallback method.")

                    # Start continuous background monitoring
                    print("DEBUG: Starting continuous background monitoring...")
                    if hasattr(self.blockchain_manager, 'start_continuous_scan'):
                        self.blockchain_manager.start_continuous_scan()
                    else:
                        self.start_continuous_blockchain_scan()

                except Exception as e:
                    print(f"DEBUG: Blockchain sync error: {e}")
                finally:
                    self._hide_scan_overlay()
            
            threading.Thread(target=sync_thread, daemon=True).start()
            
        except Exception as e:
            print(f"DEBUG: Error starting blockchain sync: {e}")

    def _show_scan_overlay(self, text="Scanning Transactions..."):
        """Show scanning overlay on wallet page (main thread safe)."""
        try:
            self._scan_overlay_shown_at = time.time()

            def _do_show():
                if hasattr(self, "wallet_page") and self.wallet_page:
                    self.wallet_page.show_loading(text)

            if hasattr(self, "page") and self.page and hasattr(self.page, "call_from_thread"):
                self.page.call_from_thread(_do_show)
            else:
                _do_show()
        except Exception as e:
            print(f"DEBUG: Error showing scan overlay: {e}")

    def _hide_scan_overlay(self, min_visible_seconds=0.5):
        """Hide scanning overlay with a minimum visible time."""
        try:
            shown_at = getattr(self, "_scan_overlay_shown_at", 0)
            delay = max(0.0, min_visible_seconds - (time.time() - shown_at))

            def _do_hide():
                if hasattr(self, "wallet_page") and self.wallet_page:
                    self.wallet_page.hide_loading()

            def _delayed_hide():
                try:
                    if delay > 0:
                        time.sleep(delay)
                    if hasattr(self, "page") and self.page and hasattr(self.page, "call_from_thread"):
                        self.page.call_from_thread(_do_hide)
                    else:
                        _do_hide()
                except Exception as e:
                    print(f"DEBUG: Error hiding scan overlay: {e}")

            threading.Thread(target=_delayed_hide, daemon=True).start()
        except Exception as e:
            print(f"DEBUG: Error scheduling scan overlay hide: {e}")

    def scan_all_wallets_for_changes(self, force_full_scan=False):
        """
        Scan wallets for transactions.
        - If force_full_scan=True: Do complete blockchain scan from start, cache results, then update all balances
        - Otherwise: Only check for NEW transactions since last scan, update balances when new found
        """
        overlay_shown = False
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
                self._show_scan_overlay("Scanning Transactions...")
                overlay_shown = True
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
            self._show_scan_overlay("Scanning Transactions...")
            overlay_shown = True
            self._perform_incremental_scan(wallet_addresses, effective_start_height, latest_height)
            self.last_scanned_block = latest_height
            
        except Exception as e:
            print(f"DEBUG: Error in scan_all_wallets_for_changes: {e}")
            import traceback
            traceback.print_exc()
        finally:
            if overlay_shown:
                self._hide_scan_overlay()

    def _perform_full_blockchain_scan(self, wallet_addresses, latest_height):
        """Perform complete blockchain scan from genesis using batch API"""
        try:
            print(f"DEBUG: Starting full blockchain scan using batch API (0 to {latest_height})")
            
            # Use new batch method: scan_transactions_for_addresses(addresses: List[str])
            # Returns Dict[str, List[Dict]] where keys are addresses
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
        overlay_was_visible = bool(
            getattr(getattr(self, "wallet_page", None), "loading_overlay", None)
            and getattr(self.wallet_page.loading_overlay, "visible", False)
        )
        try:
            if not overlay_was_visible:
                self._show_scan_overlay("Scanning Transactions...")
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
                
                
        except Exception as e:
            print(f"ERROR in _scan_all_rewards_iteratively: {e}")
            import traceback
            traceback.print_exc()
        finally:
            if not overlay_was_visible:
                self._hide_scan_overlay()

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
                        else:
                            wallet_txs_count[wallet_addr]['transfer'] += 1
                            print(f"  Found transaction in block {block_height} for {wallet_addr[:12]}...")
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
                if hasattr(self, 'sound_manager') and self.sound_manager and hasattr(self.sound_manager, 'play_sound'):
                    self.sound_manager.play_sound("transaction")
                    print("Playing Transaction Sound via Sound Manager")
                elif hasattr(self, '_play_sound'):
                    self._play_sound("transaction")
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
                else:
                    print(f"✓ No pending transactions for {wallet_addr[:12]}...")
            
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
                            if tx_type in ("reward", "fee_distribution"):
                                if self._should_play_incoming_sound("reward"):
                                    self._play_sound("reward")
                                    self._mark_incoming_sound("reward")
                            else:
                                if self._should_play_incoming_sound("transaction"):
                                    self._play_transaction_sound()
                                    self._mark_incoming_sound("transaction")
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
        """Update balances for all wallets by calculating from scanned transactions"""
        try:
            print(f"\n=== UPDATING BALANCES FOR {len(wallet_addresses)} WALLETS ===")
            
            # Get all transactions from database
            all_txs = []
            if hasattr(self, 'database'):
                try:
                    # Try multiple methods to get transactions
                    if hasattr(self.database, 'get_wallet_transactions'):
                        # This requires iterating over wallets
                        for addr in wallet_addresses:
                            try:
                                txs = self.database.get_wallet_transactions(addr, limit=10000)
                                all_txs.extend(txs)
                            except:
                                pass
                    elif hasattr(self.database, 'get_transactions'):
                        for addr in wallet_addresses:
                            try:
                                txs = self.database.get_transactions(addr)
                                all_txs.extend(txs)
                            except:
                                pass
                    else:
                        print(f"DEBUG: No transaction retrieval method found")
                    
                    print(f"DEBUG: Found {len(all_txs)} total transactions in database")
                except Exception as e:
                    print(f"DEBUG: Error getting transactions from database: {e}")
            
            # Process each wallet
            for wallet_addr in wallet_addresses:
                if wallet_addr not in self.wallet_core.wallets:
                    continue
                
                wallet_obj = self.wallet_core.wallets[wallet_addr]
                wallet_addr_lower = wallet_addr.lower()
                
                print(f"\nDEBUG: Calculating balance for {wallet_addr[:12]}... (lowercase: {wallet_addr_lower[:12]}...)")
                
                # Calculate balance from scanned transactions
                confirmed_balance = 0.0
                pending_balance = 0.0
                
                reward_count = 0
                transfer_in_count = 0
                transfer_out_count = 0
                
                # Process confirmed transactions
                for tx in all_txs:
                    tx_status = tx.get('status', 'confirmed').lower()
                    if tx_status != 'confirmed':
                        continue
                    
                    # Handle both field name formats
                    tx_from = tx.get('from', tx.get('from_address', '')).lower()
                    tx_to = tx.get('to', tx.get('to_address', '')).lower()
                    reward_addr = tx.get('reward_address', '').lower()
                    tx_type = tx.get('type', tx.get('tx_type', 'transfer')).lower()
                    amount = float(tx.get('amount', 0))
                    fee = float(tx.get('fee', 0))
                    
                    # Mining reward
                    if tx_type == 'reward':
                        # Check if this reward is for us
                        if (tx_to == wallet_addr_lower or reward_addr == wallet_addr_lower):
                            confirmed_balance += amount
                            reward_count += 1
                            print(f"  ✓ Reward: +{amount} (to={tx_to[:12] if tx_to else 'none'}...)")
                    # Fee distribution (mining reward variant)
                    elif tx_type == 'fee_distribution':
                        # Check if this fee distribution is for us
                        recipient_addr = tx.get('recipient', '').lower()
                        if (tx_to == wallet_addr_lower or reward_addr == wallet_addr_lower or recipient_addr == wallet_addr_lower):
                            confirmed_balance += amount
                            reward_count += 1  # Count as reward for summary
                            print(f"  ✓ Fee distribution: +{amount} (to={tx_to[:12] if tx_to else 'none'}...)")
                    # Incoming transfer
                    elif tx_to == wallet_addr_lower:
                        confirmed_balance += amount
                        transfer_in_count += 1
                        print(f"  ✓ Transfer in: +{amount} from {tx_from[:12]}...")
                    # Outgoing transfer
                    elif tx_from == wallet_addr_lower:
                        confirmed_balance -= (amount + fee)
                        transfer_out_count += 1
                        print(f"  ✓ Transfer out: -{amount} - {fee} fee to {tx_to[:12]}...")
                
                # Store in wallet_core.wallets
                wallet_obj['confirmed_balance'] = max(0.0, confirmed_balance)
                wallet_obj['available_balance'] = max(0.0, confirmed_balance)
                wallet_obj['pending_balance'] = pending_balance
                wallet_obj['balance'] = max(0.0, confirmed_balance) + pending_balance
                
                print(f"✓ {wallet_addr[:12]}... Summary: {reward_count} rewards, {transfer_in_count} in, {transfer_out_count} out")
                print(f"  Final balance: {max(0.0, confirmed_balance):.6f} LKC")
                    
        except Exception as e:
            print(f"✗ Error updating balances: {e}")
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
                    # FIRST: Update sidebar balances
                    print(f">>> [1] Refreshing sidebar wallets...")
                    if hasattr(self.wallet_page, '_refresh_sidebar_wallets'):
                        self.wallet_page._refresh_sidebar_wallets()
                    
                    # SECOND: Update active wallet's balance card
                    print(f">>> [2] Recalculating balance from all transactions...")
                    if hasattr(self.wallet_page, 'recalculate_wallet_balances'):
                        if hasattr(self.wallet_core, 'current_wallet_address'):
                            self.wallet_page.recalculate_wallet_balances(self.wallet_core.current_wallet_address)
                    
                    print(f">>> [3] Updating balance card...")
                    if hasattr(self.wallet_page, '_update_wallet_data_ui_only'):
                        self.wallet_page._update_wallet_data_ui_only()
                
                print(f">>> [4] Updating transaction history...")
                if hasattr(self.wallet_page, 'refresh_transaction_history'):
                    try:
                        self.wallet_page.refresh_transaction_history()
                    except Exception as e:
                        print(f"DEBUG: Error refreshing transaction history: {e}")
                
                print(f">>> [5] Calling page.update()...")
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
            
            if not hasattr(self, 'wallet_core') or self.wallet_core:
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
                print(f"\n[ENHANCED SCAN] for {address}")
                print("=" * 60)
                
                # First get the original scan results
                original_txs = original_scan(address, start_height, end_height)
                print(f"Original scan found: {len(original_txs)} transactions")
                
                # Get blocks and scan manually (lunalib only)
                all_txs = []
                print("Scanning blocks manually via lunalib...")
                
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

    def debug_blockchain_data(self):
        """Debug blockchain data."""
        print("DEBUG: Blockchain data debugging started")
        # Add debugging logic here
    def _patch_blockchain_scanner(self):
        """Patch the blockchain scanner to use lunalib's BlockchainManager directly."""
        def blockchain_sync():
            try:
                print("DEBUG: Starting blockchain sync using lunalib...")
                if hasattr(self.blockchain_manager, 'scan_for_updates'):
                    self.blockchain_manager.scan_for_updates()
                    print("DEBUG: Blockchain sync completed using lunalib.")
                else:
                    # Fallback: scan transactions for all wallets
                    if hasattr(self.wallet_core, 'wallets'):
                        for wallet_addr in self.wallet_core.wallets.keys():
                            txs = self.blockchain_manager.scan_transactions_for_address(wallet_addr)
                            print(f"DEBUG: Scanned {len(txs)} transactions for {wallet_addr[:12]}...")
                    print("DEBUG: Blockchain sync completed using fallback method.")

                # Start continuous background monitoring
                print("DEBUG: Starting continuous background monitoring...")
                if hasattr(self.blockchain_manager, 'start_continuous_scan'):
                    self.blockchain_manager.start_continuous_scan()
                else:
                    self.start_continuous_blockchain_scan()

            except Exception as e:
                print(f"DEBUG: Blockchain sync error: {e}")

        threading.Thread(target=blockchain_sync, daemon=True).start()

    def show_create_wallet(self):
        """Display the wallet creation page or dialog."""
        print("DEBUG: show_create_wallet called")
        try:
            # Example implementation: Navigate to the wallet creation page
            from gui.page_create_wallet import CreateWalletPage
            create_wallet_page = CreateWalletPage(
                self,
                on_back=self.show_lock_page,
                on_wallet_created=self.refresh_wallet_list
            )
            # Store page as instance variable to prevent garbage collection
            self.create_wallet_page = create_wallet_page
            self.current_page = create_wallet_page.create()

            # Clear and add the new page to the UI
            self.page.controls.clear()
            self.page.controls.append(self.current_page)
            self.page.update()
            print("DEBUG: Create wallet page displayed successfully")
        except Exception as e:
            print(f"DEBUG: Error showing create wallet page: {e}")
            import traceback
            traceback.print_exc()
            self.show_snackbar(f"Error: {str(e)}", "error")

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
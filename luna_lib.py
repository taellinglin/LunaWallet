#!/usr/bin/env python3
"""
Luna Wallet - Library Module
Optimized version with incremental blockchain scanning, mempool monitoring, and caching
"""
import sys
import io
import os
import json
import time
import hashlib
import secrets
import threading
import requests
import sqlite3
import pickle
import gzip
from cryptography.fernet import Fernet
import base64
from typing import Dict, List, Optional, Tuple, Set
from dataclasses import dataclass
try:
    import cupy as cp
    CUDA_AVAILABLE = True
except ImportError:
    CUDA_AVAILABLE = False
    cp = None

class BlockchainCache:
    """Cache blockchain data locally to avoid redownloading"""
    
    def __init__(self, cache_dir=None):
        if cache_dir is None:
            cache_dir = SecureDataManager.get_data_dir()
        self.cache_dir = cache_dir
        self.cache_file = os.path.join(cache_dir, "blockchain_cache.db")
        self._init_cache()
    
    def _init_cache(self):
        """Initialize SQLite cache database"""
        conn = sqlite3.connect(self.cache_file)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS blocks (
                height INTEGER PRIMARY KEY,
                hash TEXT UNIQUE,
                block_data BLOB,
                timestamp REAL,
                last_accessed REAL
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS mempool (
                tx_hash TEXT PRIMARY KEY,
                tx_data BLOB,
                received_time REAL,
                address_involved TEXT
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS cache_meta (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        ''')
        conn.commit()
        conn.close()
    
    def save_block(self, height: int, block_hash: str, block_data: dict):
        """Save block to cache"""
        try:
            conn = sqlite3.connect(self.cache_file)
            cursor = conn.cursor()
            # Compress block data
            compressed_data = gzip.compress(pickle.dumps(block_data))
            cursor.execute('''
                INSERT OR REPLACE INTO blocks 
                (height, hash, block_data, timestamp, last_accessed)
                VALUES (?, ?, ?, ?, ?)
            ''', (height, block_hash, compressed_data, time.time(), time.time()))
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Cache save error: {e}")
    
    def get_block(self, height: int) -> Optional[dict]:
        """Get block from cache"""
        try:
            conn = sqlite3.connect(self.cache_file)
            cursor = conn.cursor()
            cursor.execute('''
                SELECT block_data FROM blocks WHERE height = ?
            ''', (height,))
            result = cursor.fetchone()
            cursor.execute('''
                UPDATE blocks SET last_accessed = ? WHERE height = ?
            ''', (time.time(), height))
            conn.commit()
            conn.close()
            
            if result:
                return pickle.loads(gzip.decompress(result[0]))
        except Exception as e:
            print(f"Cache read error: {e}")
        return None
    
    def get_block_range(self, start_height: int, end_height: int) -> List[dict]:
        """Get multiple blocks from cache"""
        blocks = []
        try:
            conn = sqlite3.connect(self.cache_file)
            cursor = conn.cursor()
            cursor.execute('''
                SELECT height, block_data FROM blocks 
                WHERE height BETWEEN ? AND ? 
                ORDER BY height
            ''', (start_height, end_height))
            results = cursor.fetchall()
            conn.close()
            
            for height, block_data in results:
                try:
                    block = pickle.loads(gzip.decompress(block_data))
                    blocks.append(block)
                    # Update access time
                    self.get_block(height)  # This updates last_accessed
                except:
                    continue
                    
        except Exception as e:
            print(f"Block range cache error: {e}")
        return blocks
    
    def save_mempool_tx(self, tx_hash: str, tx_data: dict, address_involved: str = ""):
        """Save mempool transaction to cache"""
        try:
            conn = sqlite3.connect(self.cache_file)
            cursor = conn.cursor()
            compressed_data = gzip.compress(pickle.dumps(tx_data))
            cursor.execute('''
                INSERT OR REPLACE INTO mempool 
                (tx_hash, tx_data, received_time, address_involved)
                VALUES (?, ?, ?, ?)
            ''', (tx_hash, compressed_data, time.time(), address_involved))
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Mempool cache error: {e}")
    
    def get_mempool_txs_for_address(self, address: str) -> List[dict]:
        """Get mempool transactions for specific address"""
        try:
            conn = sqlite3.connect(self.cache_file)
            cursor = conn.cursor()
            cursor.execute('''
                SELECT tx_data FROM mempool 
                WHERE address_involved = ? OR address_involved = ''
            ''', (address.lower(),))
            results = cursor.fetchall()
            conn.close()
            
            txs = []
            for result in results:
                try:
                    tx = pickle.loads(gzip.decompress(result[0]))
                    txs.append(tx)
                except:
                    continue
            return txs
        except Exception as e:
            print(f"Mempool read error: {e}")
            return []
    
    def clear_old_mempool(self, max_age_hours=2):
        """Clear mempool transactions older than specified hours"""
        try:
            cutoff = time.time() - (max_age_hours * 3600)
            conn = sqlite3.connect(self.cache_file)
            cursor = conn.cursor()
            cursor.execute('DELETE FROM mempool WHERE received_time < ?', (cutoff,))
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Mempool cleanup error: {e}")
    
    def get_highest_cached_height(self) -> int:
        """Get the highest block height we have cached"""
        try:
            conn = sqlite3.connect(self.cache_file)
            cursor = conn.cursor()
            cursor.execute('SELECT MAX(height) FROM blocks')
            result = cursor.fetchone()
            conn.close()
            return result[0] if result[0] is not None else -1
        except:
            return -1

class SecureDataManager:
    """Handles encrypted storage and data management"""

    @staticmethod
    def get_data_dir():
        """Get application data directory"""
        if getattr(sys, "frozen", False):
            base_dir = os.path.dirname(sys.executable)
        else:
            base_dir = os.path.dirname(os.path.abspath(__file__))
        data_dir = os.path.join(base_dir, "data")
        os.makedirs(data_dir, exist_ok=True)
        return data_dir

    @staticmethod
    def generate_key_from_password(password):
        """Generate encryption key from password"""
        return base64.urlsafe_b64encode(hashlib.sha256(password.encode()).digest())

    @staticmethod
    def save_encrypted_wallet(filename, data, password):
        """Save wallet with encryption"""
        try:
            key = SecureDataManager.generate_key_from_password(password)
            fernet = Fernet(key)
            encrypted_data = fernet.encrypt(json.dumps(data).encode())

            filepath = os.path.join(SecureDataManager.get_data_dir(), filename)
            with open(filepath, "wb") as f:
                f.write(encrypted_data)
            return True
        except Exception as e:
            print(f"Encryption error: {e}")
            return False

    @staticmethod
    def load_encrypted_wallet(filename, password):
        """Load encrypted wallet"""
        try:
            filepath = os.path.join(SecureDataManager.get_data_dir(), filename)
            if not os.path.exists(filepath):
                return None

            with open(filepath, "rb") as f:
                encrypted_data = f.read()

            key = SecureDataManager.generate_key_from_password(password)
            fernet = Fernet(key)
            decrypted_data = fernet.decrypt(encrypted_data)
            return json.loads(decrypted_data.decode())
        except Exception as e:
            print(f"Decryption error: {e}")
            return None

    @staticmethod
    def save_json(filename, data):
        """Save unencrypted JSON (for non-sensitive data)"""
        filepath = os.path.join(SecureDataManager.get_data_dir(), filename)
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)
        return True

    @staticmethod
    def load_json(filename, default=None):
        """Load unencrypted JSON"""
        if default is None:
            default = {}
        filepath = os.path.join(SecureDataManager.get_data_dir(), filename)
        if os.path.exists(filepath):
            with open(filepath, "r") as f:
                return json.load(f)
        return default

def setup_cuda():
    """Check and setup CUDA availability"""
    try:
        import cupy as cp
        if cp.cuda.runtime.getDeviceCount() > 0:
            print("✅ CUDA is available")
            return True
        else:
            print("❌ CUDA drivers found but no GPU available")
            return False
    except ImportError:
        print("❌ CuPy not installed - CUDA unavailable")
        return False
    except Exception as e:
        print(f"❌ CUDA check failed: {e}")
        return False


class Block:
    """Block representation"""
    def __init__(self, index: int, previous_hash: str, timestamp: float, 
                 transactions: List[Dict], miner: str, difficulty: int):
        self.index = index
        self.previous_hash = previous_hash
        self.timestamp = timestamp
        self.transactions = transactions
        self.miner = miner
        self.difficulty = difficulty
        self.nonce = 0
        self.hash = self.calculate_hash()
        
    def calculate_hash(self) -> str:
        """Calculate block hash"""
        block_data = f"{self.index}{self.previous_hash}{self.timestamp}{self.transactions}{self.miner}{self.difficulty}{self.nonce}"
        return hashlib.sha256(block_data.encode()).hexdigest()
    
    def mine_block(self) -> bool:
        """Mine the block (simplified - in real implementation this would use actual PoW)"""
        target = "0" * self.difficulty
        while not self.hash.startswith(target):
            self.nonce += 1
            self.hash = self.calculate_hash()
            if self.nonce % 1000 == 0:  # Check for interruption
                return False
        return True
    
    def to_dict(self) -> Dict:
        """Convert block to dictionary"""
        return {
            'index': self.index,
            'previous_hash': self.previous_hash,
            'timestamp': self.timestamp,
            'transactions': self.transactions,
            'miner': self.miner,
            'difficulty': self.difficulty,
            'nonce': self.nonce,
            'hash': self.hash
        }

@dataclass
class NodeConfig:
    """Node configuration"""
    miner_address: str = "LUN_Node_Miner_Default"
    difficulty: int = 4
    auto_mine: bool = False
    node_url: str = "https://bank.linglin.art"
    mining_interval: int = 30  # seconds between auto-mining attempts
    
    def save_config(self, filename="node_config.json"):
        """Save configuration to file"""
        config_data = {
            'miner_address': self.miner_address,
            'difficulty': self.difficulty,
            'auto_mine': self.auto_mine,
            'node_url': self.node_url,
            'mining_interval': self.mining_interval
        }
        try:
            with open(filename, 'w') as f:
                json.dump(config_data, f, indent=2)
            return True
        except Exception as e:
            print(f"Error saving config: {e}")
            return False
    
    def load_config(self, filename="node_config.json"):
        """Load configuration from file"""
        try:
            if os.path.exists(filename):
                with open(filename, 'r') as f:
                    config_data = json.load(f)
                self.miner_address = config_data.get('miner_address', self.miner_address)
                self.difficulty = config_data.get('difficulty', self.difficulty)
                self.auto_mine = config_data.get('auto_mine', self.auto_mine)
                self.node_url = config_data.get('node_url', self.node_url)
                self.mining_interval = config_data.get('mining_interval', self.mining_interval)
                return True
        except Exception as e:
            print(f"Error loading config: {e}")
        return False

class LunaLib:
    """
    Main Luna Wallet library class
    Optimized with incremental blockchain scanning, mempool monitoring, and caching
    """

    def __init__(self, auto_scan=True):
        self.wallet_file = "wallet_encrypted.dat"
        self.pending_file = "pending.json"
        self.scan_state_file = "scan_state.json"  # Track scan progress
        self.data_dir = SecureDataManager.get_data_dir()
        
        # Initialize empty state
        self.wallets = []
        self.pending_txs = []
        self.is_unlocked = False
        self.scanning = False
        self.scan_thread = None
        self.wallet_password = None

        # Scan optimization state
        self.scan_state = self._load_scan_state()
        self.last_full_scan = self.scan_state.get('last_full_scan', 0)
        
        # Performance settings
        self.scan_batch_size = 50  # Blocks per batch
        self.max_blocks_per_scan = 500  # Limit blocks per scan
        self.full_scan_interval = 3600  # Force full scan every hour

        # Blockchain cache
        self.blockchain_cache = BlockchainCache()
        
        # Network monitoring
        self.network_connected = False
        self.sync_progress = 0
        self.sync_status = "disconnected"
        self.last_network_check = 0
        self.mempool_watcher = None
        self.mempool_monitoring = False
        self.watched_tx_hashes: Set[str] = set()
        
        # Event callbacks
        self.on_balance_changed = None
        self.on_transaction_received = None
        self.on_sync_complete = None
        self.on_sync_progress = None
        self.on_error = None

        if auto_scan:
            self.start_auto_scan()

    def _load_scan_state(self):
        """Load scan state from file"""
        try:
            state = SecureDataManager.load_json(self.scan_state_file, {})
            # Initialize default structure if needed
            if 'wallets' not in state:
                state['wallets'] = {}
            if 'last_full_scan' not in state:
                state['last_full_scan'] = 0
            return state
        except Exception as e:
            print(f"DEBUG: Failed to load scan state: {e}")
            return {'wallets': {}, 'last_full_scan': 0}

    def _save_scan_state(self):
        """Save scan state to file"""
        try:
            SecureDataManager.save_json(self.scan_state_file, self.scan_state)
            return True
        except Exception as e:
            print(f"DEBUG: Failed to save scan state: {e}")
            return False

    # Core Wallet Operations
    def initialize_wallet(self, password, label="Primary Wallet"):
        """Initialize a new wallet with password protection"""
        try:
            # Validate password
            if not password or len(password) < 1:
                self._handle_error("Password cannot be empty")
                return False
                
            # Create first wallet
            wallet_address = self.create_wallet(label)
            if not wallet_address:
                self._handle_error("Failed to create wallet structure")
                return False
                
            print(f"DEBUG: Created wallet with address: {wallet_address}")
            
            # Save with encryption
            if self.save_wallet(password):
                self.is_unlocked = True
                print("DEBUG: Wallet successfully initialized and saved")
                return True
            else:
                self._handle_error("Failed to save encrypted wallet")
                # Clean up the created wallet if save fails
                self.wallets = []
                return False
                
        except Exception as e:
            self._handle_error(f"Initialization failed: {str(e)}")
            import traceback
            print(f"DEBUG: Traceback: {traceback.format_exc()}")
            return False

    def unlock_wallet(self, password):
        """Unlock wallet with password"""
        try:
            wallets = SecureDataManager.load_encrypted_wallet(
                self.wallet_file, password
            )
            if wallets is not None:
                self.wallets = wallets
                self.pending_txs = SecureDataManager.load_json(self.pending_file, [])
                self.is_unlocked = True
                self.wallet_password = password

                # Ensure proper wallet structure
                for wallet in self.wallets:
                    if "pending_send" not in wallet:
                        wallet["pending_send"] = 0.0
                    # Initialize scan state for new wallets
                    if wallet["address"] not in self.scan_state['wallets']:
                        self.scan_state['wallets'][wallet["address"]] = {
                            'last_scanned_height': 0,
                            'last_scan_time': 0
                        }

                # Start mempool monitoring
                self.start_mempool_monitoring()
                
                self._trigger_callback(self.on_balance_changed)
                return True
            return False
        except Exception as e:
            self._handle_error(f"Unlock failed: {e}")
            return False

    def lock_wallet(self):
        """Lock the wallet"""
        self.is_unlocked = False
        self.wallets = []
        self.pending_txs = []
        self.stop_mempool_monitoring()

    def save_wallet(self, password=None):
        """Save wallet with encryption"""
        if not self.is_unlocked:
            self._handle_error("Wallet not unlocked")
            return False
            
        if not self.wallets:
            self._handle_error("No wallets to save")
            return False

        try:
            # Use stored password if available, otherwise use provided password
            save_password = password or self.wallet_password
            if not save_password:
                self._handle_error("No password available for saving")
                return False
                
            success = SecureDataManager.save_encrypted_wallet(
                self.wallet_file, self.wallets, save_password
            )
            if success:
                SecureDataManager.save_json(self.pending_file, self.pending_txs)
                print("DEBUG: Wallet saved successfully")
                return True
            else:
                self._handle_error("SecureDataManager failed to save wallet")
                return False
                
        except Exception as e:
            self._handle_error(f"Save failed: {str(e)}")
            import traceback
            print(f"DEBUG: Save traceback: {traceback.format_exc()}")
            return False

    # Wallet Management
    def create_wallet(self, label):
        """Create a new wallet"""
        try:
            # Validate label
            if not label or not label.strip():
                label = "Primary Wallet"
                
            # Generate secure keys
            private_key = secrets.token_hex(32)
            if len(private_key) != 64:
                self._handle_error("Invalid private key generated")
                return None
                
            public_key = hashlib.sha256(private_key.encode()).hexdigest()
            address = f"LUN_{public_key[:16]}_{secrets.token_hex(4)}"
            
            wallet = {
                "address": address,
                "label": label.strip(),
                "public_key": public_key,
                "private_key": private_key,
                "balance": 0.0,
                "pending_send": 0.0,
                "transactions": [],
                "created": time.time(),
                "is_our_wallet": True
            }
            
            self.wallets.append(wallet)
            
            # Initialize scan state for new wallet
            if address not in self.scan_state['wallets']:
                self.scan_state['wallets'][address] = {
                    'last_scanned_height': 0,
                    'last_scan_time': 0
                }
                self._save_scan_state()
            
            print(f"DEBUG: Wallet created successfully: {address}")
            return address
            
        except Exception as e:
            self._handle_error(f"Create wallet failed: {str(e)}")
            return None

    def import_wallet(self, private_key_hex, label=""):
        """Import wallet from private key"""
        if not self.is_unlocked:
            return False

        try:
            if len(private_key_hex) != 64 or not all(
                c in "0123456789abcdef" for c in private_key_hex.lower()
            ):
                return False

            public_key = hashlib.sha256(private_key_hex.encode()).hexdigest()
            address = f"LUN_{public_key[:16]}_{secrets.token_hex(4)}"

            # Check for duplicates
            for wallet in self.wallets:
                if wallet["address"] == address:
                    return False

            wallet = {
                "address": address,
                "label": label or f"Imported_{address[-8:]}",
                "public_key": public_key,
                "private_key": private_key_hex,
                "balance": 0.0,
                "pending_send": 0.0,
                "transactions": [],
                "created": time.time(),
                "is_our_wallet": True,
            }

            self.wallets.append(wallet)
            
            # Initialize scan state for imported wallet
            if address not in self.scan_state['wallets']:
                self.scan_state['wallets'][address] = {
                    'last_scanned_height': 0,
                    'last_scan_time': 0
                }
                self._save_scan_state()
            
            self.save_wallet()
            return True

        except Exception as e:
            self._handle_error(f"Import failed: {e}")
            return False

    def export_wallet(self, address=None):
        """Export wallet private key (use with caution)"""
        if not self.is_unlocked or not self.wallets:
            return None

        wallet = (
            self.wallets[0]
            if address is None
            else next((w for w in self.wallets if w["address"] == address), None)
        )

        if wallet:
            return {
                "address": wallet["address"],
                "private_key": wallet["private_key"],
                "label": wallet["label"],
            }
        return None

    # Network and Blockchain Operations
    def check_network_connection(self) -> bool:
        """Check if we can connect to the network"""
        try:
            response = requests.get("https://bank.linglin.art/health", timeout=5)
            self.network_connected = response.status_code == 200
            self.last_network_check = time.time()
            return self.network_connected
        except:
            self.network_connected = False
            return False

    def _update_sync_progress(self, progress: int, message: str):
        """Update sync progress"""
        self.sync_progress = progress
        self.sync_status = message
        self._trigger_callback(self.on_sync_progress, progress, message)

    def download_blockchain_with_progress(self, progress_callback=None) -> bool:
        """Download blockchain with progress tracking - OPTIMIZED VERSION"""
        try:
            if progress_callback:
                progress_callback(0, "Getting blockchain info...")
            
            # Get current blockchain height using optimized endpoint
            try:
                response = requests.get("https://bank.linglin.art/blockchain/latest", timeout=10)
                if response.status_code == 200:
                    latest_block = response.json()
                    current_height = latest_block.get('index', 0)
                else:
                    # Fallback to full chain but only get length
                    response = requests.get("https://bank.linglin.art/blockchain", timeout=30)
                    if response.status_code == 200:
                        blockchain = response.json()
                        current_height = len(blockchain) - 1 if blockchain else 0
                    else:
                        if progress_callback:
                            progress_callback(0, f"API error: {response.status_code}")
                        return False
            except Exception as e:
                if progress_callback:
                    progress_callback(0, f"Network error: {str(e)}")
                return False
            
            if current_height == 0:
                if progress_callback:
                    progress_callback(100, "No blocks available")
                return True
            
            # Determine what we need to download
            cached_height = self.wallet_core.blockchain_cache.get_highest_cached_height()
            start_height = 0 if cached_height < 0 else cached_height + 1
            
            if start_height > current_height:
                if progress_callback:
                    progress_callback(100, "Up to date")
                return True
            
            total_blocks = current_height - start_height + 1
            if progress_callback:
                progress_callback(0, f"Downloading {start_height} to {current_height} ({total_blocks} blocks)")
            
            # Download in batches with progress
            batch_size = 50
            downloaded = 0
            
            for batch_start in range(start_height, current_height + 1, batch_size):
                batch_end = min(batch_start + batch_size - 1, current_height)
                
                # Update progress
                downloaded += (batch_end - batch_start + 1)
                progress = min(99, int((downloaded / total_blocks) * 100))
                if progress_callback:
                    progress_callback(progress, f"Downloading blocks {batch_start}-{batch_end}")
                
                # Get blocks using range endpoint if available
                try:
                    response = requests.get(
                        f"https://bank.linglin.art/blockchain/range?start={batch_start}&end={batch_end}",
                        timeout=30
                    )
                    if response.status_code == 200:
                        blocks = response.json()
                    else:
                        # Fallback: get full chain and filter
                        response = requests.get("https://bank.linglin.art/blockchain", timeout=60)
                        if response.status_code == 200:
                            full_chain = response.json()
                            blocks = [block for block in full_chain 
                                    if batch_start <= block.get('index', 0) <= batch_end]
                        else:
                            blocks = []
                except Exception as e:
                    print(f"Block range error: {e}")
                    blocks = []
                
                if not blocks:
                    if progress_callback:
                        progress_callback(0, f"Failed to download blocks {batch_start}-{batch_end}")
                    return False
                
                # Cache blocks using the existing blockchain cache
                for block in blocks:
                    height = block.get('index', batch_start)
                    block_hash = block.get('hash', '')
                    self.wallet_core.blockchain_cache.save_block(height, block_hash, block)
                
                # Small delay to be nice to the server
                time.sleep(0.05)
            
            if progress_callback:
                progress_callback(100, "Download complete")
            return True
            
        except Exception as e:
            print(f"Download error: {e}")
            if progress_callback:
                progress_callback(0, f"Error: {str(e)}")
            return False

    def get_mempool_with_progress(self, progress_callback=None):
        """Get mempool with progress tracking"""
        try:
            if progress_callback:
                progress_callback(0, "Loading mempool...")
            
            response = requests.get("https://bank.linglin.art/mempool", timeout=15)
            if response.status_code == 200:
                mempool = response.json()
                if progress_callback:
                    progress_callback(100, f"Loaded {len(mempool)} transactions")
                return mempool
            else:
                if progress_callback:
                    progress_callback(0, f"Mempool error: {response.status_code}")
                return []
                
        except Exception as e:
            print(f"Mempool error: {e}")
            if progress_callback:
                progress_callback(0, f"Error: {str(e)}")
            return []

    def check_network_connection(self) -> bool:
        """Check if we can connect to the network"""
        try:
            response = requests.get("https://bank.linglin.art/health", timeout=5)
            return response.status_code == 200
        except:
            return False

    # Mempool Monitoring
    def start_mempool_monitoring(self):
        """Start monitoring mempool for incoming transactions"""
        if self.mempool_monitoring:
            return
        
        self.mempool_monitoring = True
        self.mempool_watcher = threading.Thread(target=self._mempool_monitor, daemon=True)
        self.mempool_watcher.start()
        print("DEBUG: Mempool monitoring started")

    def stop_mempool_monitoring(self):
        """Stop mempool monitoring"""
        self.mempool_monitoring = False
        self.mempool_watcher = None
        print("DEBUG: Mempool monitoring stopped")

    def _mempool_monitor(self):
        """Monitor mempool for transactions involving our addresses"""
        check_count = 0
        while self.mempool_monitoring and self.is_unlocked:
            try:
                check_count += 1
                
                # Get our addresses
                our_addresses = {wallet['address'].lower() for wallet in self.wallets}
                if not our_addresses:
                    time.sleep(10)
                    continue
                
                # Get current mempool (check every 5 scans to reduce load)
                if check_count % 5 == 0:
                    mempool_txs = self._get_mempool()
                    if mempool_txs:
                        new_txs_found = self._process_mempool_transactions(mempool_txs, our_addresses)
                        if new_txs_found:
                            self._trigger_callback(self.on_transaction_received)
                
                # Clean old mempool data periodically
                if check_count % 50 == 0:
                    self.blockchain_cache.clear_old_mempool()
                
                time.sleep(2)  # Check every 2 seconds
                
            except Exception as e:
                print(f"Mempool monitor error: {e}")
                time.sleep(10)

    def _get_mempool(self) -> List[dict]:
        """Get current mempool transactions"""
        try:
            response = requests.get("https://bank.linglin.art/mempool", timeout=10)
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            print(f"Mempool fetch error: {e}")
        return []

    def _process_mempool_transactions(self, mempool_txs: List[dict], our_addresses: Set[str]) -> bool:
        """Process mempool transactions for our addresses - returns True if new transactions found"""
        new_txs_found = False
        
        for tx in mempool_txs:
            tx_hash = tx.get('hash')
            if not tx_hash or tx_hash in self.watched_tx_hashes:
                continue
            
            # Check if this involves our addresses
            from_addr = (tx.get('from') or tx.get('sender') or '').lower()
            to_addr = (tx.get('to') or tx.get('receiver') or '').lower()
            
            if from_addr in our_addresses or to_addr in our_addresses:
                # This is our transaction - add to watched list
                self.watched_tx_hashes.add(tx_hash)
                
                # Cache the transaction
                involved_address = from_addr if from_addr in our_addresses else to_addr
                self.blockchain_cache.save_mempool_tx(tx_hash, tx, involved_address)
                
                # Add to pending transactions if it's outgoing
                if from_addr in our_addresses and tx_hash not in [ptx.get('hash') for ptx in self.pending_txs]:
                    self.pending_txs.append({
                        "hash": tx_hash,
                        "from": from_addr,
                        "to": to_addr,
                        "amount": float(tx.get('amount', 0)),
                        "status": "pending",
                        "timestamp": time.time(),
                        "type": "transfer"
                    })
                    new_txs_found = True
                    print(f"DEBUG: New pending transaction detected: {tx_hash}")
                
                # Update wallet balances for pending state
                for wallet in self.wallets:
                    if wallet['address'].lower() == from_addr:
                        wallet['pending_send'] += float(tx.get('amount', 0))
                        new_txs_found = True
                
                if new_txs_found:
                    self._trigger_callback(self.on_balance_changed)
        
        return new_txs_found

    # Optimized Blockchain Scanning
    def scan_blockchain(self, force_full_scan=False):
        """Optimized blockchain scan - uses cache and checks mempool"""
        if not self.is_unlocked:
            return False

        print("DEBUG: Starting optimized blockchain scan...")
        self._update_sync_progress(0, "Starting blockchain scan...")
        
        # Get current blockchain height
        current_height = self._get_current_blockchain_height()
        if current_height is None:
            self._update_sync_progress(0, "Could not get blockchain height")
            return False

        print(f"DEBUG: Current blockchain height: {current_height}")

        # Check if we need a full scan
        needs_full_scan = (force_full_scan or 
                          time.time() - self.last_full_scan > self.full_scan_interval)

        updates = False
        total_wallets = len([w for w in self.wallets if w.get("is_our_wallet", True)])
        processed_wallets = 0

        for wallet in self.wallets:
            if not wallet.get("is_our_wallet", True):
                continue

            address = wallet["address"]
            wallet_scan_state = self.scan_state['wallets'].get(address, {})
            last_scanned_height = wallet_scan_state.get('last_scanned_height', 0)
            
            # Determine scan range
            if needs_full_scan or last_scanned_height == 0:
                start_height = 0
                scan_type = "full"
                print(f"DEBUG: Full scan for {address}")
            else:
                start_height = last_scanned_height + 1
                scan_type = "incremental"
                print(f"DEBUG: Incremental scan for {address} from block {start_height}")

            # Only scan if there are new blocks
            if current_height >= start_height:
                # Limit the number of blocks to scan in one go
                end_height = min(current_height, start_height + self.max_blocks_per_scan - 1)
                
                if start_height <= end_height:
                    old_balance = wallet["balance"]
                    old_tx_count = len(wallet["transactions"])
                    
                    # Scan the block range
                    blocks_scanned = self._scan_wallet_blocks(wallet, start_height, end_height)
                    
                    if blocks_scanned > 0:
                        print(f"DEBUG: Scanned {blocks_scanned} blocks for {address} ({scan_type} scan)")
                        
                        # Update scan state
                        self.scan_state['wallets'][address] = {
                            'last_scanned_height': end_height,
                            'last_scan_time': time.time(),
                            'scan_type': scan_type
                        }
                        
                        if needs_full_scan:
                            self.last_full_scan = time.time()
                            self.scan_state['last_full_scan'] = self.last_full_scan
                        
                        self._save_scan_state()

                    # Check mempool for this wallet
                    mempool_txs = self.blockchain_cache.get_mempool_txs_for_address(address)
                    for tx in mempool_txs:
                        if self._add_transaction_to_wallet(wallet, tx, "pending"):
                            updates = True

                    if (wallet["balance"] != old_balance or 
                        len(wallet["transactions"]) != old_tx_count):
                        updates = True
                        print(f"DEBUG: Wallet {address} updated - Balance: {wallet['balance']}, Transactions: {len(wallet['transactions'])}")

            processed_wallets += 1
            progress = int((processed_wallets / total_wallets) * 100)
            self._update_sync_progress(progress, f"Scanning wallet {processed_wallets}/{total_wallets}")

        # Update pending transactions status
        self._update_pending_transactions()

        if updates:
            self.save_wallet()
            self._trigger_callback(self.on_balance_changed)
            self._trigger_callback(self.on_transaction_received)

        self._update_sync_progress(100, "Scan complete")
        self._trigger_callback(self.on_sync_complete)
        return True

    def _scan_wallet_blocks(self, wallet, start_height, end_height):
        """Scan specific block range for wallet transactions using cache"""
        if start_height > end_height:
            return 0

        address = wallet["address"]
        known_tx_hashes = {tx.get("hash") for tx in wallet["transactions"]}
        blocks_scanned = 0
        
        print(f"DEBUG: Scanning blocks {start_height} to {end_height} for {address}")

        # Try to get blocks from cache first
        cached_blocks = self.blockchain_cache.get_block_range(start_height, end_height)
        if cached_blocks:
            print(f"DEBUG: Found {len(cached_blocks)} blocks in cache")
            for block in cached_blocks:
                blocks_scanned += 1
                self._process_block_for_wallet(wallet, block, known_tx_hashes)
        
        # If we didn't get all blocks from cache, fetch the rest from network
        cached_count = len(cached_blocks)
        expected_count = end_height - start_height + 1
        
        if cached_count < expected_count:
            missing_start = start_height + cached_count
            missing_end = end_height
            
            print(f"DEBUG: Fetching {missing_end - missing_start + 1} missing blocks from network")
            
            for batch_start in range(missing_start, missing_end + 1, self.scan_batch_size):
                batch_end = min(batch_start + self.scan_batch_size - 1, missing_end)
                
                blocks = self._get_blocks_range(batch_start, batch_end)
                if not blocks:
                    print(f"DEBUG: No blocks received for range {batch_start}-{batch_end}")
                    continue

                for block in blocks:
                    blocks_scanned += 1
                    self._process_block_for_wallet(wallet, block, known_tx_hashes)
                    # Cache the block
                    block_height = block.get('index', batch_start)
                    block_hash = block.get('hash', '')
                    self.blockchain_cache.save_block(block_height, block_hash, block)

                # Small delay to avoid overwhelming the server
                time.sleep(0.05)

        # Recalculate final balance
        wallet["balance"] = self._calculate_balance_from_transactions(wallet["transactions"], address)
        return blocks_scanned

    def _add_transaction_to_wallet(self, wallet, tx, status="confirmed"):
        """Add a transaction to wallet if not already present"""
        tx_hash = tx.get('hash')
        if not tx_hash:
            return False
            
        # Check if transaction already exists
        for existing_tx in wallet['transactions']:
            if existing_tx.get('hash') == tx_hash:
                return False
        
        # Add new transaction
        from_addr = tx.get('from') or tx.get('sender', '')
        to_addr = tx.get('to') or tx.get('receiver', '')
        amount = float(tx.get('amount', 0))
        
        new_tx = {
            'type': 'transfer',
            'from': from_addr,
            'to': to_addr,
            'amount': amount,
            'timestamp': tx.get('timestamp', time.time()),
            'block_height': tx.get('block_height'),
            'hash': tx_hash,
            'status': status,
            'fee': float(tx.get('fee', 0)),
            'memo': tx.get('memo', '')
        }
        
        wallet['transactions'].append(new_tx)
        return True

    def _process_block_for_wallet(self, wallet, block, known_tx_hashes):
        """Process a single block for wallet transactions"""
        address = wallet["address"]
        block_height = block.get("index", 0)
        
        # Check block reward
        miner = block.get("miner")
        reward = float(block.get("reward", 0))
        if miner and miner.lower() == address.lower() and reward > 0:
            reward_tx = {
                "type": "reward",
                "from": "network",
                "to": address,
                "amount": reward,
                "timestamp": block.get("timestamp", time.time()),
                "block_height": block_height,
                "hash": f"reward_{block_height}_{miner}",
                "status": "confirmed",
            }
            if reward_tx["hash"] not in known_tx_hashes:
                wallet["transactions"].append(reward_tx)
                known_tx_hashes.add(reward_tx["hash"])
                print(f"DEBUG: Found reward in block {block_height}: {reward} Luna")

        # Check regular transactions
        for tx in block.get("transactions", []):
            tx_hash = tx.get("hash")
            if not tx_hash or tx_hash in known_tx_hashes:
                continue

            from_addr = tx.get("from") or tx.get("sender")
            to_addr = tx.get("to") or tx.get("receiver")
            amount = float(tx.get("amount", 0))

            if (from_addr and from_addr.lower() == address.lower()) or \
               (to_addr and to_addr.lower() == address.lower()):
                
                enhanced_tx = {
                    "type": "transfer",
                    "from": from_addr,
                    "to": to_addr,
                    "amount": amount,
                    "timestamp": tx.get("timestamp", time.time()),
                    "block_height": block_height,
                    "hash": tx_hash,
                    "status": "confirmed",
                    "fee": float(tx.get("fee", 0)),
                    "memo": tx.get("memo", "")
                }
                
                wallet["transactions"].append(enhanced_tx)
                known_tx_hashes.add(tx_hash)
                
                direction = "incoming" if to_addr and to_addr.lower() == address.lower() else "outgoing"
                print(f"DEBUG: Found {direction} transaction in block {block_height}: {amount} Luna")

    def _get_current_blockchain_height(self):
        """Get current blockchain height - much faster than full chain"""
        try:
            # Try to get just the latest block
            response = requests.get("https://bank.linglin.art/blockchain/latest", timeout=10)
            if response.status_code == 200:
                latest_block = response.json()
                return latest_block.get('index', 0)
            
            # Fallback: get full chain but only if absolutely necessary
            print("DEBUG: Falling back to full chain for height")
            full_chain = self._get_blockchain()
            if full_chain:
                return len(full_chain) - 1
                
        except Exception as e:
            print(f"DEBUG: Blockchain height error: {e}")
        
        return None

    def _get_blocks_range(self, start_height, end_height):
        """Get specific block range - more efficient than full chain"""
        try:
            # Try range endpoint if available
            response = requests.get(
                f"https://bank.linglin.art/blockchain/range?start={start_height}&end={end_height}",
                timeout=30
            )
            if response.status_code == 200:
                return response.json()
            
            # Fallback: get full chain but filter to range
            print("DEBUG: Range endpoint not available, using full chain with filtering")
            full_chain = self._get_blockchain()
            if full_chain:
                return [block for block in full_chain 
                       if start_height <= block.get('index', 0) <= end_height]
                
        except Exception as e:
            print(f"DEBUG: Block range error: {e}")
        
        return []

    def _get_blockchain(self):
        """Get full blockchain data from network (fallback method)"""
        try:
            print("DEBUG: Fetching full blockchain data...")
            response = requests.get("https://bank.linglin.art/blockchain", timeout=60)
            if response.status_code == 200:
                blockchain = response.json()
                print(f"DEBUG: Received blockchain with {len(blockchain)} blocks")
                return blockchain
            else:
                print(f"DEBUG: Blockchain API returned status {response.status_code}")
        except Exception as e:
            print(f"DEBUG: Blockchain error: {e}")
        return []

    def _calculate_balance_from_transactions(self, transactions, address):
        """Calculate balance from transaction history"""
        balance = 0.0
        for tx in transactions:
            if tx.get("status") != "confirmed":
                continue

            tx_type = tx.get("type")
            from_addr = tx.get("from")
            to_addr = tx.get("to")
            amount = float(tx.get("amount", 0))

            if tx_type == "reward" and to_addr and to_addr.lower() == address.lower():
                balance += amount
            elif from_addr and from_addr.lower() == address.lower():
                balance -= amount + float(tx.get("fee", 0))
            elif to_addr and to_addr.lower() == address.lower():
                balance += amount

        return max(0.0, balance)

    def _update_pending_transactions(self):
        """Update pending transactions status based on blockchain"""
        if not self.pending_txs:
            return

        # Get recent blocks to check for confirmations
        current_height = self._get_current_blockchain_height()
        if current_height is None:
            return

        start_height = max(0, current_height - 20)  # Check last 20 blocks
        recent_blocks = self.blockchain_cache.get_block_range(start_height, current_height)
        if not recent_blocks:
            recent_blocks = self._get_blocks_range(start_height, current_height)

        blockchain_hashes = set()
        for block in recent_blocks:
            for tx in block.get("transactions", []):
                blockchain_hashes.add(tx.get("hash"))

        updated = False
        for pending_tx in self.pending_txs[:]:
            tx_hash = pending_tx.get("hash")
            if tx_hash in blockchain_hashes:
                # Transaction confirmed
                pending_tx["status"] = "confirmed"
                updated = True
                print(f"DEBUG: Transaction {tx_hash} confirmed")
                
                # Remove from pending_send
                for wallet in self.wallets:
                    if wallet["address"] == pending_tx.get("from"):
                        wallet["pending_send"] = max(
                            0,
                            wallet["pending_send"] - float(pending_tx.get("amount", 0)),
                        )
            elif pending_tx.get("timestamp", 0) < time.time() - 3600:
                # Transaction failed (older than 1 hour)
                pending_tx["status"] = "failed"
                updated = True

                # Refund pending balance
                for wallet in self.wallets:
                    if wallet["address"] == pending_tx.get("from"):
                        wallet["pending_send"] = max(
                            0,
                            wallet["pending_send"] - float(pending_tx.get("amount", 0)),
                        )
                print(f"DEBUG: Transaction {tx_hash} failed")

        if updated:
            SecureDataManager.save_json(self.pending_file, self.pending_txs)
            self._trigger_callback(self.on_balance_changed)

    # Transaction Operations
    def send_transaction(self, to_address, amount, memo="", password=None):
        """Send transaction to address with enhanced safety checks"""
        if not self.is_unlocked or not self.wallets:
            return False

        wallet = self.wallets[0]
        
        # Quick balance update before sending (incremental scan)
        self.scan_blockchain(force_full_scan=False)
        
        available_balance = wallet["balance"] - wallet["pending_send"]
        
        # Prevent negative balance with buffer for fees
        required_amount = amount + 0.00001
        if available_balance < required_amount:
            self._handle_error(f"Insufficient balance. Available: {available_balance:.6f} LKC, Required: {required_amount:.6f} LKC")
            return False
        
        # Check for duplicate pending transactions
        current_time = time.time()
        duplicate_check_window = 300
        
        for pending_tx in self.pending_txs:
            if (pending_tx.get("from") == wallet["address"] and 
                pending_tx.get("to") == to_address and 
                pending_tx.get("amount") == amount and
                pending_tx.get("status") == "pending" and
                current_time - pending_tx.get("timestamp", 0) < duplicate_check_window):
                self._handle_error("Duplicate transaction detected. Please wait for the previous transaction to confirm.")
                return False

        # Create transaction
        tx = {
            "type": "transfer",
            "from": wallet["address"],
            "to": to_address,
            "amount": float(amount),
            "fee": 0.00001,
            "nonce": int(time.time() * 1000),
            "timestamp": current_time,
            "memo": memo,
        }

        # Sign transaction
        tx_data = f"{tx['from']}{tx['to']}{tx['amount']}{tx['timestamp']}{tx['nonce']}"
        tx["signature"] = hashlib.sha256(tx_data.encode()).hexdigest()
        tx["hash"] = hashlib.sha256(json.dumps(tx, sort_keys=True).encode()).hexdigest()

        # Final balance check
        final_available = wallet["balance"] - wallet["pending_send"]
        if final_available < required_amount:
            self._handle_error(f"Balance changed. Available: {final_available:.6f} LKC, needed: {required_amount:.6f} LKC")
            return False

        # Broadcast to mempool
        try:
            print(f"DEBUG: Broadcasting transaction to {to_address} for {amount} LKC")
            response = requests.post("https://bank.linglin.art/mempool/add", json=tx, timeout=30)
            if response.status_code == 201:
                # Add to pending and watched list
                self.pending_txs.append({
                    "hash": tx["hash"],
                    "from": wallet["address"],
                    "to": to_address,
                    "amount": amount,
                    "status": "pending",
                    "timestamp": current_time,
                    "type": "transfer"
                })
                
                wallet["pending_send"] += amount
                self.watched_tx_hashes.add(tx["hash"])
                
                # Cache in mempool
                self.blockchain_cache.save_mempool_tx(tx["hash"], tx, wallet["address"].lower())
                
                self.save_wallet()
                self._trigger_callback(self.on_balance_changed)
                print(f"DEBUG: Transaction broadcast successful: {tx['hash']}")
                return True
            else:
                self._handle_error(f"Network error: {response.status_code} - {response.text}")
        except Exception as e:
            self._handle_error(f"Send failed: {e}")

        return False

    # Auto-scan functionality
    def start_auto_scan(self):
        """Start background auto-scanning"""
        if hasattr(self, "scanning") and self.scanning:
            return

        self.scanning = True
        self.scan_thread = threading.Thread(target=self._auto_scanner, daemon=True)
        self.scan_thread.start()

    def stop_auto_scan(self):
        """Stop background scanning"""
        if hasattr(self, "scanning"):
            self.scanning = False
        if hasattr(self, 'scan_thread') and self.scan_thread:
            self.scan_thread.join(timeout=5)

    def _auto_scanner(self):
        """Background auto-scanner with optimized scanning"""
        scan_count = 0
        while hasattr(self, "scanning") and self.scanning:
            try:
                if self.is_unlocked:
                    scan_count += 1
                    # Use incremental scans for auto-scans, full scans only periodically
                    force_full = (scan_count % 120 == 0)  # Full scan every 60 minutes (120 * 30s)
                    print(f"DEBUG: Auto-scan #{scan_count} ({'full' if force_full else 'incremental'})")
                    self.scan_blockchain(force_full_scan=force_full)
                time.sleep(30)  # Scan every 30 seconds
            except Exception as e:
                self._handle_error(f"Auto-scan error: {e}")
                time.sleep(60)

    # Data Access Methods for GUI
    def get_wallet_info(self):
        """Get wallet information for GUI"""
        if not self.is_unlocked or not self.wallets:
            return None

        wallet = self.wallets[0]
        wallet_scan_state = self.scan_state['wallets'].get(wallet["address"], {})
        
        return {
            "address": wallet["address"],
            "label": wallet["label"],
            "balance": wallet["balance"],
            "available_balance": wallet["balance"] - wallet["pending_send"],
            "pending_send": wallet["pending_send"],
            "transaction_count": len(wallet["transactions"]),
            "last_scan_time": wallet_scan_state.get('last_scan_time', 0),
            "last_scanned_height": wallet_scan_state.get('last_scanned_height', 0)
        }

    def get_transaction_history(self):
        """Get complete transaction history for GUI"""
        if not self.is_unlocked:
            return []

        all_transactions = []
        for wallet in self.wallets:
            for tx in wallet["transactions"]:
                tx["wallet_address"] = wallet["address"]
                tx["wallet_label"] = wallet["label"]
                all_transactions.append(tx)

        # Add pending transactions
        for pending_tx in self.pending_txs:
            if pending_tx.get("status") == "pending":
                pending_tx["wallet_address"] = pending_tx.get("from")
                pending_tx["wallet_label"] = "Pending"
                all_transactions.append(pending_tx)

        # Sort by timestamp (newest first)
        all_transactions.sort(key=lambda x: x.get("timestamp", 0), reverse=True)
        return all_transactions

    def generate_qr_code(self, address):
        """Generate QR code data for address"""
        try:
            import qrcode
            
            qr = qrcode.QRCode()
            qr.add_data(address)
            qr.make()
            img = qr.make_image()
            bio = io.BytesIO()
            img.save(bio)
            bio.seek(0)
            return bio
            
        except Exception as e:
            self._handle_error(f"QR generation error: {e}")
            return self._create_placeholder_qr(address)

    def _create_placeholder_qr(self, address):
        """Create a simple text-based placeholder when QR fails"""
        try:
            from PIL import Image, ImageDraw
            import textwrap
            
            img = Image.new('RGB', (200, 200), color='white')
            d = ImageDraw.Draw(img)
            
            wrapped_text = textwrap.fill(address, width=20)
            d.text((10, 10), wrapped_text, fill='black')
            
            bio = io.BytesIO()
            img.save(bio, format="PNG")
            bio.seek(0)
            return bio
        except:
            return None

    # Callback Management
    def _trigger_callback(self, callback, *args):
        """Safely trigger callback if set"""
        if callback:
            try:
                callback(*args)
            except Exception as e:
                print(f"Callback error: {e}")

    def _handle_error(self, message):
        """Handle and report errors"""
        print(f"Wallet Error: {message}")
        self._trigger_callback(self.on_error, message)

    # Cleanup
    def __del__(self):
        """Cleanup on destruction"""
        self.stop_auto_scan()
        self.stop_mempool_monitoring()
        if hasattr(self, "is_unlocked") and self.is_unlocked:
            self.save_wallet()
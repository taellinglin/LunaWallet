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
    def _get_manual_block_count(self):
        """Manual fallback method to count blocks when height endpoint fails"""
        try:
            import requests
            
            print("DEBUG: Using manual block count method...")
            
            # Method 1: Try the blocks endpoint
            try:
                response = requests.get('http://localhost:5555/blockchain/blocks', timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    blocks = data.get('blocks', [])
                    if blocks:
                        print(f"DEBUG: Manual count via blocks endpoint: {len(blocks)} blocks")
                        return len(blocks)
            except Exception as e:
                print(f"DEBUG: Blocks endpoint manual count failed: {e}")
            
            # Method 2: Try the range endpoint with a test range
            try:
                response = requests.get('http://localhost:5555/blockchain/range?start=0&end=1000', timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    blocks = data.get('blocks', [])
                    total_blocks = data.get('total_blocks', 0)
                    if total_blocks > 0:
                        print(f"DEBUG: Manual count via range endpoint total_blocks: {total_blocks}")
                        return total_blocks
                    elif blocks:
                        # If we got blocks but no total count, estimate from the range
                        if len(blocks) == 1001:  # 0-1000 inclusive = 1001 blocks
                            # We might have hit the limit, try to find the actual end
                            print("DEBUG: Range endpoint returned maximum blocks, checking higher ranges...")
                            # Try a higher range to find the actual end
                            for test_end in [5000, 10000, 50000]:
                                try:
                                    response = requests.get(f'http://localhost:5555/blockchain/range?start={test_end-100}&end={test_end}', timeout=5)
                                    if response.status_code == 200:
                                        test_data = response.json()
                                        test_blocks = test_data.get('blocks', [])
                                        if test_blocks:
                                            print(f"DEBUG: Found blocks at height ~{test_end}, continuing search...")
                                        else:
                                            print(f"DEBUG: No blocks at height {test_end}, blockchain ends around {test_end-100}")
                                            return test_end - 100
                                except:
                                    break
                            return 1000  # Fallback to the known maximum
                        else:
                            print(f"DEBUG: Manual count via range endpoint block count: {len(blocks)}")
                            return len(blocks)
            except Exception as e:
                print(f"DEBUG: Range endpoint manual count failed: {e}")
            
            # Method 3: Try latest block endpoint
            try:
                response = requests.get('http://localhost:5555/blockchain/latest-block', timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    block = data.get('block', {})
                    latest_index = block.get('index', 0)
                    if latest_index > 0:
                        print(f"DEBUG: Manual count via latest block index: {latest_index + 1}")
                        return latest_index + 1  # +1 because index is 0-based
            except Exception as e:
                print(f"DEBUG: Latest block manual count failed: {e}")
            
            # Method 4: Try system health endpoint
            try:
                response = requests.get('http://localhost:5555/system/health', timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    blockchain_info = data.get('blockchain', {})
                    total_blocks = blockchain_info.get('total_blocks', 0)
                    if total_blocks > 0:
                        print(f"DEBUG: Manual count via system health: {total_blocks} blocks")
                        return total_blocks
            except Exception as e:
                print(f"DEBUG: System health manual count failed: {e}")
            
            # Method 5: Direct incremental probe (last resort)
            print("DEBUG: Attempting incremental block probe...")
            for height in range(0, 10000, 100):  # Check every 100 blocks up to 10,000
                try:
                    response = requests.get(f'http://localhost:5555/blockchain/block/{height}', timeout=2)
                    if response.status_code != 200:
                        print(f"DEBUG: Block {height} not found, blockchain height is approximately {height-1}")
                        return max(0, height - 1)
                except:
                    break
            
            print("DEBUG: All manual block count methods failed")
            return 0
            
        except Exception as e:
            print(f"ERROR in manual block count: {e}")
            return 0
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

    def scan_blockchain(self, force_full_scan=False, progress_callback=None):
        """Optimized blockchain scan - scan ALL blocks without limits"""
        if not self.is_unlocked:
            return False

        print("DEBUG: Starting FULL blockchain scan...")
        self._update_sync_progress(0, "Starting full blockchain scan...")
        
        # DEBUG: Check height first
        self.debug_blockchain_height()
        
        try:
            # Get current blockchain height
            current_height = self._get_current_blockchain_height()
            
            # If height is 0 but we know there are blocks, force a manual check
            if current_height == 0:
                print("DEBUG: Height returned 0, attempting manual block count...")
                current_height = self._get_manual_block_count()
            
            print(f"DEBUG: Final blockchain height: {current_height}")

            if current_height <= 0:
                print("DEBUG: No blocks to scan")
                self._update_sync_progress(100, "No blocks to scan")
                return True

            # ALWAYS do full scan and scan ALL blocks
            updates = False
            valid_wallets = [w for w in self.wallets if isinstance(w, dict) and w.get("is_our_wallet", True)]
            total_wallets = len(valid_wallets)
            
            if total_wallets == 0:
                print("DEBUG: No valid wallets to scan")
                return True

            print(f"DEBUG: Scanning {current_height} blocks for {total_wallets} wallets")

            for wallet_index, wallet in enumerate(valid_wallets):
                try:
                    address = wallet.get("address")
                    if not address:
                        continue

                    print(f"DEBUG: [{wallet_index+1}/{total_wallets}] Scanning ALL blocks 0-{current_height-1} for {address}")

                    old_balance = wallet.get("balance", 0)
                    old_tx_count = len(wallet.get("transactions", []))
                    
                    # SCAN ALL BLOCKS in larger batches
                    batch_size = 500  # Increased batch size
                    total_blocks_scanned = 0
                    total_transactions_found = 0
                    
                    for batch_start in range(0, current_height, batch_size):
                        batch_end = min(batch_start + batch_size - 1, current_height - 1)
                        
                        progress = int((batch_start / current_height) * 80) + int((wallet_index / total_wallets) * 20)
                        self._update_sync_progress(
                            progress, 
                            f"Scanning {address}: blocks {batch_start}-{batch_end}/{current_height-1}"
                        )
                        
                        print(f"DEBUG: Scanning batch {batch_start}-{batch_end} for {address}")
                        
                        blocks_scanned, transactions_found = self._scan_wallet_blocks_batch(wallet, batch_start, batch_end)
                        total_blocks_scanned += blocks_scanned
                        total_transactions_found += transactions_found
                        
                        # Small delay to prevent overwhelming the API
                        time.sleep(0.1)
                    
                    print(f"DEBUG: Scanned {total_blocks_scanned} blocks, found {total_transactions_found} transactions for {address}")
                    
                    # Update wallet balance
                    self._update_wallet_balance(wallet)
                    
                    # Update scan state
                    self.scan_state['wallets'][address] = {
                        'last_scanned_height': current_height - 1,
                        'last_scan_time': time.time(),
                        'scan_type': 'full',
                        'blocks_scanned': total_blocks_scanned,
                        'transactions_found': total_transactions_found
                    }
                    
                    self.last_full_scan = time.time()
                    self.scan_state['last_full_scan'] = self.last_full_scan
                    self._save_scan_state()

                    # Check for updates
                    new_balance = wallet.get("balance", 0)
                    new_tx_count = len(wallet.get("transactions", []))
                    
                    if (new_balance != old_balance or new_tx_count != old_tx_count):
                        updates = True
                        print(f"DEBUG: Wallet {address} UPDATED - Balance: {old_balance} → {new_balance}, Transactions: {old_tx_count} → {new_tx_count}")
                    else:
                        print(f"DEBUG: No changes for {address} - Balance: {new_balance}, Transactions: {new_tx_count}")

                except Exception as e:
                    print(f"ERROR scanning wallet {wallet.get('address', 'unknown')}: {e}")
                    import traceback
                    print(f"Traceback: {traceback.format_exc()}")
                    continue

            # Final updates
            self._update_sync_progress(95, "Saving wallet data...")
            
            if updates:
                self.save_wallet()
                self._trigger_callback(self.on_balance_changed)
                self._trigger_callback(self.on_transaction_received)
                print("DEBUG: Wallet updated and callbacks triggered")
            else:
                print("DEBUG: No updates found during scan")

            self._update_sync_progress(100, "Full scan complete")
            self._trigger_callback(self.on_sync_complete)
            
            # Print final summary
            self._print_scan_summary(valid_wallets)
            return True

        except Exception as e:
            print(f"CRITICAL ERROR in scan_blockchain: {e}")
            import traceback
            print(f"Traceback: {traceback.format_exc()}")
            self._update_sync_progress(0, f"Scan failed: {str(e)}")
            return False

    def _scan_wallet_blocks_batch(self, wallet, start_height, end_height):
        """Scan a batch of blocks and return (blocks_scanned, transactions_found)"""
        try:
            if not isinstance(wallet, dict):
                return 0, 0
                
            address = wallet.get("address")
            
            # Get blockchain data via API
            blockchain_data = self._get_blockchain_range_via_api(start_height, end_height)
            
            if not blockchain_data:
                print(f"WARNING: No blockchain data retrieved for range {start_height}-{end_height}")
                return 0, 0
            
            blocks_scanned = 0
            transactions_found = 0
            known_tx_hashes = set()
            
            # Scan the available blocks
            for block_data in blockchain_data:
                try:
                    if not isinstance(block_data, dict):
                        continue
                    
                    block_height = block_data.get('index', 0)
                    
                    # Process the block
                    if self._process_block_for_wallet(wallet, block_data, known_tx_hashes):
                        blocks_scanned += 1
                        transactions_found += 1  # We found at least one transaction
                    
                except Exception as e:
                    print(f"ERROR processing block {block_height}: {e}")
                    continue
            
            return blocks_scanned, transactions_found
            
        except Exception as e:
            print(f"ERROR in _scan_wallet_blocks_batch: {e}")
            return 0, 0
    def _update_wallet_balance(self, wallet):
        """Update wallet balance based on transactions"""
        try:
            if not isinstance(wallet, dict):
                return
                
            balance = 0.0
            transactions = wallet.get("transactions", [])
            
            for tx in transactions:
                if not isinstance(tx, dict):
                    continue
                    
                tx_type = tx.get("type")
                amount = float(tx.get("amount", 0))
                to_addr = tx.get("to")
                from_addr = tx.get("from")
                address = wallet.get("address")
                
                # Add incoming transactions
                if to_addr and str(to_addr).lower() == str(address).lower():
                    balance += amount
                # Subtract outgoing transactions  
                elif from_addr and str(from_addr).lower() == str(address).lower():
                    balance -= amount
            
            wallet["balance"] = balance
            print(f"DEBUG: Updated balance for {wallet.get('address')}: {balance}")
            
        except Exception as e:
            print(f"ERROR updating wallet balance: {e}")
    def debug_blockchain_state(self):
        """Debug the actual blockchain state"""
        print("=== BLOCKCHAIN STATE DEBUG ===")
        
        # Check blockchain daemon
        if hasattr(self, 'blockchain_daemon_instance') and self.blockchain_daemon_instance:
            blockchain = getattr(self.blockchain_daemon_instance, 'blockchain', [])
            print(f"Blockchain daemon has {len(blockchain)} blocks")
            
            for i, block in enumerate(blockchain):
                print(f"Block {i}: {block.get('index', 'N/A')} - {block.get('hash', 'N/A')[:20]}...")
                print(f"  Transactions: {len(block.get('transactions', []))}")
        else:
            print("No blockchain daemon instance found")
        
        # Try to get blockchain via API
        try:
            import requests
            response = requests.get('http://localhost:5555/blockchain/height', timeout=5)
            if response.status_code == 200:
                data = response.json()
                print(f"API Blockchain height: {data.get('height')}")
            
            response = requests.get('http://localhost:5555/blockchain/latest', timeout=5)
            if response.status_code == 200:
                data = response.json()
                print(f"Latest block: {data.get('block')}")
        except Exception as e:
            print(f"API call failed: {e}")
    def _create_genesis_block_data(self):
        """Create actual genesis block data based on your blockchain"""
        genesis_data = {
            "index": 0,
            "timestamp": 1727672773,  # 2025-09-30 07:06:13
            "transactions": [
                {
                    "type": "GTX_Genesis",  # Based on your blockchain type
                    "hash": "genesis_0000000000000000000000000000000000000000000000000000000000000000",
                    "serial_number": "00000001",  # Example serial
                    "denomination": "1.0",  # Example amount
                    "issued_to": "LUN_9cc3cf8fff072881_8b71766e",  # Example address
                    "description": "Luna Coin Genesis Block",
                    "timestamp": 1727672773,
                    "public_key": "genesis_public_key",
                    "signature": "genesis_signature"
                }
            ],
            "previous_hash": "0",
            "nonce": 0,
            "miner": "genesis",
            "hash": "54455c2db8115abb1873a0c5b4b8a2d6c7e8f9a0b1c2d3e4f5a6b7c8d9e0f1",  # Full hash
            "difficulty": 0,
            "mining_time": 0
        }
        return genesis_data
    def scan_specific_blocks_for_address(self, address, block_range=None):
        """Scan specific blocks for a particular address (for debugging)"""
        if block_range is None:
            block_range = (0, 100)  # Scan first 100 blocks
        
        print(f"=== SCANNING BLOCKS {block_range[0]}-{block_range[1]} FOR {address} ===")
        
        # Find the wallet
        wallet = None
        for w in self.wallets:
            if isinstance(w, dict) and w.get('address') == address:
                wallet = w
                break
        
        if not wallet:
            print(f"ERROR: Wallet not found for address {address}")
            return
        
        start_height, end_height = block_range
        blocks_scanned = self._scan_wallet_blocks(wallet, start_height, end_height)
        
        print(f"=== SCAN COMPLETE: Scanned {blocks_scanned} blocks ===")
        print(f"Wallet balance: {wallet.get('balance', 0)}")
        print(f"Transactions found: {len(wallet.get('transactions', []))}")
        
        # Print recent transactions
        transactions = wallet.get('transactions', [])
        for tx in transactions[-5:]:  # Last 5 transactions
            print(f"  TX: {tx.get('type')} - {tx.get('amount')} - {tx.get('hash')[:20]}...")
    def _scan_wallet_blocks(self, wallet, start_height, end_height):
        """Scan blocks for wallet transactions using direct blockchain access"""
        try:
            if not isinstance(wallet, dict):
                print(f"ERROR: _scan_wallet_blocks received non-dict wallet: {type(wallet)} - {wallet}")
                return 0
                
            blocks_scanned = 0
            address = wallet.get("address")
            
            print(f"DEBUG: Scanning blocks {start_height} to {end_height} for {address}")
            
            # Get blockchain data via API - get ALL blocks in range
            blockchain_data = self._get_blockchain_range_via_api(start_height, end_height)
            
            if not blockchain_data:
                print(f"WARNING: No blockchain data retrieved for range {start_height}-{end_height}")
                return 0
            
            print(f"DEBUG: Retrieved {len(blockchain_data)} blocks from API")
            
            # Track found transactions for this scan
            known_tx_hashes = set()
            transactions_found = 0
            
            # Scan the available blocks
            for block_data in blockchain_data:
                try:
                    if not isinstance(block_data, dict):
                        print(f"WARNING: Block data is not a dictionary: {type(block_data)}")
                        continue
                    
                    block_height = block_data.get('index', 0)
                    
                    # Validate block has expected structure
                    if 'index' not in block_data:
                        print(f"WARNING: Block missing index: {block_data}")
                        continue
                    
                    print(f"DEBUG: Processing block {block_height} with {len(block_data.get('transactions', []))} transactions")
                    
                    # Process the block
                    if self._process_block_for_wallet(wallet, block_data, known_tx_hashes):
                        blocks_scanned += 1
                        transactions_found += 1
                        print(f"DEBUG: Found transactions in block {block_height} for {address}")
                    
                except Exception as e:
                    print(f"ERROR processing block {block_height}: {e}")
                    continue
            
            print(f"DEBUG: Scanned {blocks_scanned} blocks, found {transactions_found} transactions for {address}")
            return blocks_scanned
            
        except Exception as e:
            print(f"ERROR in _scan_wallet_blocks: {e}")
            import traceback
            print(f"Traceback: {traceback.format_exc()}")
            return 0
    def debug_blockchain_height(self):
        """Debug method to check blockchain height from all sources"""
        print("=== BLOCKCHAIN HEIGHT DEBUG ===")
        
        try:
            import requests
            import json
            
            # Method 1: Direct API call to height endpoint
            print("1. Checking /blockchain/height endpoint...")
            try:
                response = requests.get('http://localhost:5555/blockchain/height', timeout=10)
                print(f"   Status: {response.status_code}")
                if response.status_code == 200:
                    data = response.json()
                    print(f"   Response: {json.dumps(data, indent=2)}")
                    height = data.get('height')
                    success = data.get('success')
                    print(f"   Height: {height}, Success: {success}")
                else:
                    print(f"   Error: {response.text}")
            except Exception as e:
                print(f"   Exception: {e}")
            
            # Method 2: Blocks endpoint to count blocks
            print("2. Checking /blockchain/blocks endpoint...")
            try:
                response = requests.get('http://localhost:5555/blockchain/blocks', timeout=10)
                print(f"   Status: {response.status_code}")
                if response.status_code == 200:
                    data = response.json()
                    blocks_count = len(data.get('blocks', []))
                    success = data.get('success')
                    print(f"   Blocks count: {blocks_count}, Success: {success}")
                    # Show first few blocks if available
                    blocks = data.get('blocks', [])
                    if blocks:
                        print(f"   First 3 blocks:")
                        for i, block in enumerate(blocks[:3]):
                            print(f"     Block {i}: index={block.get('index')}, hash={block.get('hash', '')[:20]}...")
                else:
                    print(f"   Error: {response.text}")
            except Exception as e:
                print(f"   Exception: {e}")
            
            # Method 3: Latest block endpoint
            print("3. Checking /blockchain/latest-block endpoint...")
            try:
                response = requests.get('http://localhost:5555/blockchain/latest-block', timeout=10)
                print(f"   Status: {response.status_code}")
                if response.status_code == 200:
                    data = response.json()
                    block = data.get('block', {})
                    block_index = block.get('index')
                    success = data.get('success')
                    print(f"   Latest block index: {block_index}, Success: {success}")
                    if block:
                        print(f"   Latest block hash: {block.get('hash', '')[:20]}...")
                else:
                    print(f"   Error: {response.text}")
            except Exception as e:
                print(f"   Exception: {e}")
            
            # Method 4: Range endpoint to verify block count
            print("4. Checking /blockchain/range endpoint...")
            try:
                # Test a small range to see if it works
                response = requests.get('http://localhost:5555/blockchain/range?start=0&end=5', timeout=10)
                print(f"   Status: {response.status_code}")
                if response.status_code == 200:
                    data = response.json()
                    blocks_count = len(data.get('blocks', []))
                    success = data.get('success')
                    total_blocks = data.get('total_blocks')
                    print(f"   Range blocks count: {blocks_count}, Total blocks: {total_blocks}, Success: {success}")
                else:
                    print(f"   Error: {response.text}")
            except Exception as e:
                print(f"   Exception: {e}")
            
            # Method 5: Check blockchain viewer endpoint
            print("5. Checking /blockchain-viewer endpoint...")
            try:
                response = requests.get('http://localhost:5555/blockchain-viewer', timeout=10)
                print(f"   Status: {response.status_code}")
                if response.status_code == 200:
                    print("   Blockchain viewer is accessible")
                else:
                    print(f"   Error: {response.status_code}")
            except Exception as e:
                print(f"   Exception: {e}")
            
            # Method 6: Direct daemon access (if available)
            print("6. Checking blockchain daemon directly...")
            try:
                if hasattr(self, 'blockchain_daemon_instance') and self.blockchain_daemon_instance:
                    blockchain = getattr(self.blockchain_daemon_instance, 'blockchain', [])
                    height = len(blockchain) if blockchain else 0
                    print(f"   Daemon blockchain height: {height}")
                    if blockchain:
                        print(f"   First 3 blocks in daemon:")
                        for i, block in enumerate(blockchain[:3]):
                            print(f"     Block {i}: index={block.get('index')}, hash={block.get('hash', '')[:20]}...")
                else:
                    print("   No blockchain daemon instance found")
            except Exception as e:
                print(f"   Exception: {e}")
                
            # Method 7: System health endpoint
            print("7. Checking /system/health endpoint...")
            try:
                response = requests.get('http://localhost:5555/system/health', timeout=10)
                print(f"   Status: {response.status_code}")
                if response.status_code == 200:
                    data = response.json()
                    blockchain_info = data.get('blockchain', {})
                    mempool_info = data.get('mempool', {})
                    print(f"   Blockchain: {blockchain_info.get('total_blocks', 'N/A')} blocks")
                    print(f"   Mempool: {mempool_info.get('total_transactions', 'N/A')} transactions")
                else:
                    print(f"   Error: {response.text}")
            except Exception as e:
                print(f"   Exception: {e}")
                
            print("="*50)
            
        except Exception as e:
            print(f"CRITICAL ERROR in debug_blockchain_height: {e}")
            import traceback
            print(f"Traceback: {traceback.format_exc()}")
    def _print_scan_summary(self, wallets):
        """Print a summary of the scan results"""
        print("\n" + "="*50)
        print("SCAN SUMMARY")
        print("="*50)
        
        total_balance = 0
        total_transactions = 0
        
        for wallet in wallets:
            if isinstance(wallet, dict):
                address = wallet.get('address', 'Unknown')
                balance = wallet.get('balance', 0)
                tx_count = len(wallet.get('transactions', []))
                
                total_balance += balance
                total_transactions += tx_count
                
                print(f"{address[:20]}...: {balance:10.2f} Luna, {tx_count:4d} transactions")
        
        print("-"*50)
        print(f"TOTAL: {total_balance:10.2f} Luna, {total_transactions:4d} transactions")
        print("="*50)
    def _get_blockchain_range_via_api(self, start_height, end_height):
        """Get a range of blocks via API calls with better error handling"""
        try:
            import requests
            
            # Validate range
            if start_height > end_height:
                print(f"ERROR: Invalid range {start_height}-{end_height}")
                return []
            
            range_size = end_height - start_height + 1
            print(f"DEBUG: Requesting {range_size} blocks ({start_height}-{end_height}) from API")
            
            # Use the range endpoint to get multiple blocks at once
            range_url = f'http://localhost:5555/blockchain/range?start={start_height}&end={end_height}'
            
            try:
                response = requests.get(range_url, timeout=60)  # Increased timeout for large ranges
            except requests.exceptions.Timeout:
                print(f"WARNING: API timeout for range {start_height}-{end_height}, trying smaller batch...")
                # Fall back to smaller batches
                return self._get_blockchain_range_small_batches(start_height, end_height)
            
            if response.status_code == 200:
                data = response.json()
                blocks = data.get('blocks', [])
                print(f"DEBUG: API returned {len(blocks)} blocks for range {start_height}-{end_height}")
                return blocks
            else:
                print(f"ERROR: API range request failed with status {response.status_code}")
                print(f"Response: {response.text}")
                # Fall back to smaller batches
                return self._get_blockchain_range_small_batches(start_height, end_height)
                
        except Exception as e:
            print(f"ERROR getting blockchain range via API: {e}")
            # Fall back to smaller batches
            return self._get_blockchain_range_small_batches(start_height, end_height)

    def _get_blockchain_range_small_batches(self, start_height, end_height, batch_size=100):
        """Get blocks in smaller batches to avoid API issues"""
        print(f"DEBUG: Using small batch method for range {start_height}-{end_height}")
        
        all_blocks = []
        for batch_start in range(start_height, end_height + 1, batch_size):
            batch_end = min(batch_start + batch_size - 1, end_height)
            
            try:
                import requests
                range_url = f'http://localhost:5555/blockchain/range?start={batch_start}&end={batch_end}'
                response = requests.get(range_url, timeout=30)
                
                if response.status_code == 200:
                    data = response.json()
                    blocks = data.get('blocks', [])
                    all_blocks.extend(blocks)
                    print(f"DEBUG: Small batch {batch_start}-{batch_end}: got {len(blocks)} blocks")
                else:
                    print(f"WARNING: Small batch {batch_start}-{batch_end} failed: {response.status_code}")
                    
                # Small delay between batches
                time.sleep(0.05)
                
            except Exception as e:
                print(f"ERROR in small batch {batch_start}-{batch_end}: {e}")
                continue
        
        print(f"DEBUG: Small batch method collected {len(all_blocks)} total blocks")
        return all_blocks
    def _get_blockchain_via_api(self):
        """Get blockchain data via API calls"""
        try:
            import requests
            
            # Get blockchain height first
            height_response = requests.get('http://localhost:5555/blockchain/height', timeout=10)
            if height_response.status_code != 200:
                print("ERROR: Could not get blockchain height via API")
                return []
                
            height_data = height_response.json()
            total_blocks = height_data.get('height', 0)
            print(f"DEBUG: API reports blockchain height: {total_blocks}")
            
            if total_blocks == 0:
                return []
            
            # Get all blocks
            blocks_response = requests.get('http://localhost:5555/blockchain/blocks', timeout=10)
            if blocks_response.status_code == 200:
                blocks_data = blocks_response.json()
                return blocks_data.get('blocks', [])
            else:
                print("ERROR: Could not get blocks via API")
                return []
                
        except Exception as e:
            print(f"ERROR getting blockchain via API: {e}")
            return []
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
        """Process a single block for wallet transactions - returns True if transactions found"""
        try:
            # Validate wallet
            if not isinstance(wallet, dict):
                print(f"ERROR: Wallet is not a dictionary: {wallet}")
                return False
                
            address = wallet.get("address")
            if not address:
                print("ERROR: Wallet missing address")
                return False

            # Validate block
            if not isinstance(block, dict):
                print(f"ERROR: Block is not a dictionary: {block}")
                return False
                
            block_height = block.get("index", 0)
            transactions_found = False
            
            # Check block reward - SAFE ACCESS
            miner = block.get("miner")
            reward = 0.0
            
            # Try multiple ways to get reward amount
            reward_keys = ["reward", "mining_reward", "block_reward"]
            for key in reward_keys:
                reward_value = block.get(key)
                if reward_value is not None:
                    try:
                        reward = float(reward_value)
                        break
                    except (ValueError, TypeError):
                        continue
            
            # Process reward if valid
            if miner and reward > 0:
                try:
                    miner_str = str(miner).lower() if miner else ""
                    address_str = str(address).lower() if address else ""
                    
                    if miner_str == address_str:
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
                        
                        tx_hash = reward_tx.get("hash")
                        if tx_hash and tx_hash not in known_tx_hashes:
                            # Ensure transactions list exists
                            if "transactions" not in wallet:
                                wallet["transactions"] = []
                            wallet["transactions"].append(reward_tx)
                            known_tx_hashes.add(tx_hash)
                            transactions_found = True
                            print(f"DEBUG: Found reward in block {block_height}: {reward} Luna")
                except Exception as e:
                    print(f"ERROR processing reward for block {block_height}: {e}")

            # Check regular transactions with SAFE ACCESS
            transactions = block.get("transactions", [])
            if not isinstance(transactions, list):
                transactions = []
                
            for tx in transactions:
                try:
                    if not isinstance(tx, dict):
                        print(f"WARNING: Invalid transaction format: {tx}")
                        continue
                        
                    tx_hash = tx.get("hash")
                    if not tx_hash or tx_hash in known_tx_hashes:
                        continue

                    # Safe access to transaction fields
                    from_addr = tx.get("from") or tx.get("sender")
                    to_addr = tx.get("to") or tx.get("receiver")
                    
                    # Safe amount conversion
                    amount = 0.0
                    amount_value = tx.get("amount")
                    if amount_value is not None:
                        try:
                            amount = float(amount_value)
                        except (ValueError, TypeError):
                            amount = 0.0

                    # Check if transaction involves our wallet
                    from_match = from_addr and str(from_addr).lower() == str(address).lower()
                    to_match = to_addr and str(to_addr).lower() == str(address).lower()
                    
                    if from_match or to_match:
                        # Build enhanced transaction with safe defaults
                        enhanced_tx = {
                            "type": "transfer",
                            "from": from_addr or "unknown",
                            "to": to_addr or "unknown", 
                            "amount": amount,
                            "timestamp": tx.get("timestamp", time.time()),
                            "block_height": block_height,
                            "hash": tx_hash,
                            "status": "confirmed",
                            "fee": float(tx.get("fee", 0)),
                            "memo": tx.get("memo", "")
                        }
                        
                        # Ensure transactions list exists
                        if "transactions" not in wallet:
                            wallet["transactions"] = []
                            
                        wallet["transactions"].append(enhanced_tx)
                        known_tx_hashes.add(tx_hash)
                        transactions_found = True
                        
                        direction = "incoming" if to_match else "outgoing"
                        print(f"DEBUG: Found {direction} transaction in block {block_height}: {amount} Luna")
                        
                except Exception as e:
                    print(f"ERROR processing transaction {tx.get('hash', 'unknown')}: {e}")
                    continue

            return transactions_found
            
        except Exception as e:
            print(f"CRITICAL ERROR in _process_block_for_wallet: {e}")
            import traceback
            print(f"Traceback: {traceback.format_exc()}")
            return False

    def _get_current_blockchain_height(self):
        """Get current blockchain height from multiple sources"""
        try:
            # Try API first
            import requests
            print("DEBUG: Attempting to get blockchain height via API...")
            
            response = requests.get('http://localhost:5555/blockchain/height', timeout=10)
            if response.status_code == 200:
                data = response.json()
                height = data.get('height', 0)
                print(f"DEBUG: API blockchain height response: {data}")
                print(f"DEBUG: Parsed height: {height}")
                return height
            else:
                print(f"DEBUG: API height request failed: {response.status_code} - {response.text}")
            
            # Try the blocks endpoint as fallback
            response = requests.get('http://localhost:5555/blockchain/blocks', timeout=10)
            if response.status_code == 200:
                data = response.json()
                blocks = data.get('blocks', [])
                height = len(blocks)
                print(f"DEBUG: Blocks endpoint returned {height} blocks")
                return height
            
            # Try daemon as last resort
            if hasattr(self, 'blockchain_daemon_instance') and self.blockchain_daemon_instance:
                blockchain = getattr(self.blockchain_daemon_instance, 'blockchain', [])
                height = len(blockchain) if blockchain else 0
                print(f"DEBUG: Daemon blockchain height: {height}")
                return height
                
            print("DEBUG: All height detection methods failed")
            return 0
            
        except Exception as e:
            print(f"ERROR getting blockchain height: {e}")
            import traceback
            print(f"Traceback: {traceback.format_exc()}")
            return 0

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
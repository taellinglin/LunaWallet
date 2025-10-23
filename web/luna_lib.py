#!/usr/bin/env python3
"""
Luna Wallet - Library Module
Optimized version with incremental blockchain scanning and performance improvements
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
from cryptography.fernet import Fernet
import base64
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
try:
    import cupy as cp
    CUDA_AVAILABLE = True
except ImportError:
    CUDA_AVAILABLE = False
    cp = None

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
    Optimized with incremental blockchain scanning and performance improvements
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

        # Event callbacks
        self.on_balance_changed = None
        self.on_transaction_received = None
        self.on_sync_complete = None
        self.on_error = None
        self.on_blockchain_progress = None  # Progress callback for downloads
        self.on_blockchain_download_complete = None  # Completion callback

        # Blockchain download state
        self.blockchain_cache = []
        self.is_downloading_blockchain = False
        self.download_progress = 0.0
        self.total_blocks_to_download = 0

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

    # Optimized Blockchain Operations
    def scan_blockchain(self, force_full_scan=False):
        """Optimized blockchain scan - only scans new blocks"""
        if not self.is_unlocked:
            return False

        print("DEBUG: Starting optimized blockchain scan...")
        
        # Get current blockchain height first (fast operation)
        current_height = self._get_current_blockchain_height()
        if current_height is None:
            print("DEBUG: Could not get blockchain height")
            return False

        print(f"DEBUG: Current blockchain height: {current_height}")

        # Check if we need a full scan (once per hour or if forced)
        needs_full_scan = (force_full_scan or 
                          time.time() - self.last_full_scan > self.full_scan_interval)

        updates = False
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

                    if (wallet["balance"] != old_balance or 
                        len(wallet["transactions"]) != old_tx_count):
                        updates = True
                        print(f"DEBUG: Wallet {address} updated - Balance: {wallet['balance']}, Transactions: {len(wallet['transactions'])}")
                        self._trigger_callback(self.on_transaction_received)

        # Update pending transactions with recent blocks only
        recent_blocks = self._get_recent_blocks(20)  # Only get recent blocks for pending check
        if recent_blocks:
            self._update_pending_transactions(recent_blocks)

        if updates:
            self.save_wallet()
            self._trigger_callback(self.on_balance_changed)

        self._trigger_callback(self.on_sync_complete)
        return True

    def _scan_wallet_blocks(self, wallet, start_height, end_height):
        """Scan specific block range for wallet transactions"""
        if start_height > end_height:
            return 0

        address = wallet["address"]
        known_tx_hashes = {tx.get("hash") for tx in wallet["transactions"]}
        blocks_scanned = 0
        
        print(f"DEBUG: Scanning blocks {start_height} to {end_height} for {address}")

        # Scan in batches to avoid memory issues and be gentle on the server
        for batch_start in range(start_height, end_height + 1, self.scan_batch_size):
            batch_end = min(batch_start + self.scan_batch_size - 1, end_height)
            
            print(f"DEBUG: Fetching blocks {batch_start} to {batch_end}")
            blocks = self._get_blocks_range(batch_start, batch_end)
            if not blocks:
                print(f"DEBUG: No blocks received for range {batch_start}-{batch_end}")
                continue

            for block in blocks:
                blocks_scanned += 1
                self._process_block_for_wallet(wallet, block, known_tx_hashes)

            # Small delay to avoid overwhelming the server
            time.sleep(0.05)

        # Recalculate final balance
        wallet["balance"] = self._calculate_balance_from_transactions(wallet["transactions"], address)
        return blocks_scanned

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

    def _get_recent_blocks(self, count=20):
        """Get only recent blocks for pending transaction checks"""
        try:
            current_height = self._get_current_blockchain_height()
            if current_height is None:
                return []
                
            start_height = max(0, current_height - count + 1)
            return self._get_blocks_range(start_height, current_height)
            
        except Exception as e:
            print(f"DEBUG: Recent blocks error: {e}")
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

    def download_full_blockchain(self):
        """Download and cache the full blockchain with progress updates"""
        if self.is_downloading_blockchain:
            self._handle_error("Blockchain download already in progress")
            return False

        try:
            self.is_downloading_blockchain = True
            self.download_progress = 0.0
            self.blockchain_cache = []

            print("DEBUG: Starting full blockchain download...")

            # Get current blockchain height first
            current_height = self._get_current_blockchain_height()
            if current_height is None:
                self.is_downloading_blockchain = False
                return False

            self.total_blocks_to_download = current_height + 1
            print(f"DEBUG: Downloading {self.total_blocks_to_download} blocks")

            # Download in batches to avoid memory issues and provide progress updates
            batch_size = 100
            blocks_downloaded = 0

            for batch_start in range(0, self.total_blocks_to_download, batch_size):
                batch_end = min(batch_start + batch_size - 1, current_height)

                print(f"DEBUG: Downloading blocks {batch_start} to {batch_end}")
                blocks = self._get_blocks_range(batch_start, batch_end)

                if not blocks:
                    print(f"DEBUG: No blocks received for range {batch_start}-{batch_end}")
                    continue

                self.blockchain_cache.extend(blocks)
                blocks_downloaded += len(blocks)

                # Update progress
                self.download_progress = blocks_downloaded / self.total_blocks_to_download
                self._trigger_callback(self.on_blockchain_progress, self.download_progress, blocks_downloaded, self.total_blocks_to_download)

                print(f"DEBUG: Progress: {self.download_progress:.2%} ({blocks_downloaded}/{self.total_blocks_to_download} blocks)")

                # Small delay to be gentle on the server
                time.sleep(0.1)

            # Final progress update
            self.download_progress = 1.0
            self._trigger_callback(self.on_blockchain_progress, 1.0, self.total_blocks_to_download, self.total_blocks_to_download)

            print(f"DEBUG: Blockchain download complete! Cached {len(self.blockchain_cache)} blocks")
            self._trigger_callback(self.on_blockchain_download_complete, self.blockchain_cache)

            self.is_downloading_blockchain = False
            return True

        except Exception as e:
            self._handle_error(f"Blockchain download failed: {e}")
            self.is_downloading_blockchain = False
            return False

    def get_cached_blockchain(self):
        """Get the cached blockchain data"""
        return self.blockchain_cache if self.blockchain_cache else None

    def clear_blockchain_cache(self):
        """Clear the cached blockchain data"""
        self.blockchain_cache = []
        self.download_progress = 0.0
        self.total_blocks_to_download = 0
        print("DEBUG: Blockchain cache cleared")

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

    def _update_pending_transactions(self, blockchain):
        """Update pending transactions status"""
        blockchain_hashes = set()

        for block in blockchain:
            for tx in block.get("transactions", []):
                blockchain_hashes.add(tx.get("hash"))

        updated = False
        for pending_tx in self.pending_txs[:]:
            if pending_tx.get("hash") in blockchain_hashes:
                pending_tx["status"] = "confirmed"
                updated = True
                print(f"DEBUG: Transaction {pending_tx['hash']} confirmed")
            elif pending_tx.get("timestamp", 0) < time.time() - 3600:
                pending_tx["status"] = "failed"
                updated = True

                # Refund pending balance
                for wallet in self.wallets:
                    if wallet["address"] == pending_tx.get("from"):
                        wallet["pending_send"] = max(
                            0,
                            wallet["pending_send"] - float(pending_tx.get("amount", 0)),
                        )
                print(f"DEBUG: Transaction {pending_tx['hash']} failed")

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
                # Add to pending
                self.pending_txs.append({
                    "hash": tx["hash"],
                    "from": wallet["address"],
                    "to": to_address,
                    "amount": amount,
                    "status": "pending",
                    "timestamp": current_time
                })

                wallet["pending_send"] += amount
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
        if hasattr(self, "is_unlocked") and self.is_unlocked:
            self.save_wallet()

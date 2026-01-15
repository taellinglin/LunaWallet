# app/cache_manager.py

import os
import sqlite3
import json
from pathlib import Path
from typing import Optional, Dict, Any

class BlockchainCacheManager:
    """
    Manages blockchain cache state and persistence.
    Stores last scanned block height and cache metadata.
    """
    
    def __init__(self, cache_dir: Optional[str] = None):
        """Initialize cache manager with cache directory"""
        if cache_dir is None:
            cache_dir = os.path.join(os.path.expanduser("~"), ".luna_wallet")
        
        self.cache_dir = cache_dir
        self.cache_state_file = os.path.join(cache_dir, "cache_state.db")
        
        # Ensure cache directory exists
        os.makedirs(cache_dir, exist_ok=True)
        
        # Initialize cache state database
        self._init_cache_state_db()
    
    def _init_cache_state_db(self):
        """Initialize the cache state database"""
        try:
            conn = sqlite3.connect(self.cache_state_file)
            cursor = conn.cursor()
            
            # Create cache_state table if it doesn't exist
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS cache_state (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    updated_at REAL
                )
            ''')
            
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Error initializing cache state DB: {e}")
    
    def get_last_scanned_block(self) -> int:
        """Get the last scanned block height from cache state"""
        try:
            conn = sqlite3.connect(self.cache_state_file)
            cursor = conn.cursor()
            
            cursor.execute('SELECT value FROM cache_state WHERE key = ?', ('last_scanned_block',))
            result = cursor.fetchone()
            conn.close()
            
            if result:
                return int(result[0])
            return 0
            
        except Exception as e:
            print(f"Error getting last scanned block: {e}")
            return 0
    
    def set_last_scanned_block(self, height: int):
        """Save the last scanned block height to cache state"""
        try:
            import time
            conn = sqlite3.connect(self.cache_state_file)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT OR REPLACE INTO cache_state (key, value, updated_at)
                VALUES (?, ?, ?)
            ''', ('last_scanned_block', str(height), time.time()))
            
            conn.commit()
            conn.close()
            
            print(f"✓ Saved last scanned block: {height}")
            
        except Exception as e:
            print(f"Error setting last scanned block: {e}")
    
    def get_cache_metadata(self) -> Dict[str, Any]:
        """Get all cache metadata"""
        try:
            conn = sqlite3.connect(self.cache_state_file)
            cursor = conn.cursor()
            
            cursor.execute('SELECT key, value, updated_at FROM cache_state')
            rows = cursor.fetchall()
            conn.close()
            
            metadata = {}
            for row in rows:
                key, value, updated_at = row
                try:
                    # Try to parse as JSON first
                    metadata[key] = json.loads(value)
                except:
                    # Otherwise store as string
                    metadata[key] = value
                metadata[f"{key}_updated_at"] = updated_at
            
            return metadata
            
        except Exception as e:
            print(f"Error getting cache metadata: {e}")
            return {}
    
    def set_cache_value(self, key: str, value: Any):
        """Set a cache metadata value"""
        try:
            import time
            conn = sqlite3.connect(self.cache_state_file)
            cursor = conn.cursor()
            
            # Convert value to JSON string
            value_str = json.dumps(value) if not isinstance(value, str) else value
            
            cursor.execute('''
                INSERT OR REPLACE INTO cache_state (key, value, updated_at)
                VALUES (?, ?, ?)
            ''', (key, value_str, time.time()))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            print(f"Error setting cache value {key}: {e}")
    
    def clear_cache_state(self):
        """Clear all cache state (but not the blockchain cache itself)"""
        try:
            conn = sqlite3.connect(self.cache_state_file)
            cursor = conn.cursor()
            
            cursor.execute('DELETE FROM cache_state')
            
            conn.commit()
            conn.close()
            
            print("✓ Cache state cleared")
            
        except Exception as e:
            print(f"Error clearing cache state: {e}")

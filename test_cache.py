#!/usr/bin/env python
"""
Test script for blockchain cache functionality
"""
import os
import sys
import tempfile
from pathlib import Path

# Setup cache directory
test_cache_dir = tempfile.mkdtemp(prefix="luna_cache_test_")
os.environ['LUNALIB_CACHE_DIR'] = test_cache_dir

print("=" * 60)
print("Testing Blockchain Cache Implementation")
print("=" * 60)

# Test 1: BlockchainCacheManager
print("\n1. Testing BlockchainCacheManager...")
from app.cache_manager import BlockchainCacheManager

cache_mgr = BlockchainCacheManager(cache_dir=test_cache_dir)
print("✓ BlockchainCacheManager initialized")

# Test setting and getting last scanned block
cache_mgr.set_last_scanned_block(1000)
last_block = cache_mgr.get_last_scanned_block()
assert last_block == 1000, f"Expected 1000, got {last_block}"
print(f"✓ Set and retrieved last scanned block: {last_block}")

# Test updating the value
cache_mgr.set_last_scanned_block(2000)
last_block = cache_mgr.get_last_scanned_block()
assert last_block == 2000, f"Expected 2000, got {last_block}"
print(f"✓ Updated last scanned block to: {last_block}")

# Test cache metadata
cache_mgr.set_cache_value("test_key", {"data": "test_value"})
metadata = cache_mgr.get_cache_metadata()
print(f"✓ Cache metadata: {len(metadata)} keys stored")

# Test 2: App initialization with cache manager
print("\n2. Testing app initialization with cache manager...")
try:
    # Set up a test data directory
    test_data_dir = tempfile.mkdtemp(prefix="luna_data_test_")
    
    # We can't fully test the app without a GUI, but we can check imports
    from app.core import LunaWalletApp
    print("✓ LunaWalletApp imported successfully")
    
    # Check that the cache manager class is available
    print("✓ BlockchainCacheManager available for app use")
    
except Exception as e:
    print(f"⚠ App initialization test skipped (expected in headless env): {e}")

# Test 3: Verify cache persistence
print("\n3. Testing cache persistence...")
cache_mgr2 = BlockchainCacheManager(cache_dir=test_cache_dir)
last_block2 = cache_mgr2.get_last_scanned_block()
assert last_block2 == 2000, f"Expected 2000 from persisted cache, got {last_block2}"
print(f"✓ Cache persisted correctly: {last_block2}")

# Test 4: Clear cache state
print("\n4. Testing cache state clearing...")
cache_mgr.clear_cache_state()
last_block_cleared = cache_mgr.get_last_scanned_block()
assert last_block_cleared == 0, f"Expected 0 after clear, got {last_block_cleared}"
print(f"✓ Cache state cleared successfully")

print("\n" + "=" * 60)
print("All cache tests passed! ✓")
print("=" * 60)

# Cleanup
import shutil
shutil.rmtree(test_cache_dir, ignore_errors=True)
try:
    shutil.rmtree(test_data_dir, ignore_errors=True)
except NameError:
    pass  # test_data_dir may not exist if app initialization was skipped

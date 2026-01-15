# Blockchain Cache Implementation

## Overview

This implementation adds efficient blockchain caching to LunaWallet, eliminating the need to rescan the entire blockchain on every startup.

## Features

### 1. Persistent Cache State
- **Last Scanned Block**: Stored in SQLite database (`cache_state.db`)
- **Cache Metadata**: Additional cache information (timestamps, etc.)
- **Location**: `~/.luna_wallet/cache_state.db` (or user's data directory)

### 2. Smart Scanning Strategy

#### First Boot (No Cache)
1. Shows "Initial blockchain scan..." notification
2. Performs full blockchain scan from genesis block
3. Processes and stores all transactions
4. Saves last scanned block height to cache
5. Shows "Blockchain scan complete!" notification

#### Subsequent Boots (With Cache)
1. Loads last scanned block from cache
2. Shows "Loading from cache (block X)..." notification
3. Only scans NEW blocks since last cached block
4. Updates cache with new last scanned block
5. Shows "Blockchain sync completed" notification

#### Continuous Monitoring
- Background scan every 30 seconds
- Only checks for new blocks since last scan
- No full blockchain rescans
- Minimal network usage

## Technical Details

### Cache Manager (`app/cache_manager.py`)

```python
from app.cache_manager import BlockchainCacheManager

# Initialize cache manager
cache_mgr = BlockchainCacheManager(cache_dir="/path/to/data")

# Get last scanned block
last_block = cache_mgr.get_last_scanned_block()  # Returns 0 if no cache

# Save last scanned block
cache_mgr.set_last_scanned_block(5000)

# Store custom cache values
cache_mgr.set_cache_value("custom_key", {"data": "value"})

# Get all cache metadata
metadata = cache_mgr.get_cache_metadata()

# Clear cache state (but not blockchain cache)
cache_mgr.clear_cache_state()
```

### Integration with App

The cache manager is automatically initialized in `LunaWalletApp.__init__()`:

```python
# app/core.py
def __init__(self):
    # ... other initialization ...
    
    # Initialize cache manager
    from app.cache_manager import BlockchainCacheManager
    self.cache_manager = BlockchainCacheManager(cache_dir=self._get_data_directory())
    
    # Load last scanned block from cache
    self.last_scanned_block = self.cache_manager.get_last_scanned_block()
```

### Scanning Logic

#### Full Blockchain Scan
- Triggered when `last_scanned_block == 0` (first boot)
- Uses `blockchain_manager.scan_transactions_for_addresses()` batch API
- Processes all transactions from genesis to latest block
- Saves all transactions to database
- Updates cache with latest block height

#### Incremental Scan
- Triggered when `last_scanned_block > 0` (subsequent boots)
- Only scans blocks from `last_scanned_block + 1` to latest
- Much faster than full scan
- Updates cache with new latest block height

## Benefits

1. **Faster Startup**: Only scans new blocks instead of entire blockchain
2. **Reduced Network Usage**: Minimal data transfer for incremental updates
3. **Better User Experience**: Clear progress notifications
4. **Persistent State**: Cache survives app restarts
5. **Efficient Monitoring**: Background scanning without redundant work

## Configuration

The cache can be configured through environment variables or code:

```python
# Environment variable
os.environ['LUNALIB_CACHE_DIR'] = '/custom/cache/dir'

# Or in code
cache_mgr = BlockchainCacheManager(cache_dir='/custom/cache/dir')
```

## Testing

Run the test suite to verify cache functionality:

```bash
python test_cache.py
```

Tests verify:
- Cache initialization
- Setting and getting last scanned block
- Cache persistence across instances
- Metadata storage
- Cache clearing

## Compatibility

- Works with both `flet run` (development) and `flet build` (production)
- Compatible with Windows, macOS, and Linux
- Uses standard SQLite database for cross-platform support
- No external dependencies beyond existing requirements

## Troubleshooting

### Cache Not Working
1. Check that cache directory exists and is writable
2. Verify `cache_state.db` file is created in data directory
3. Check logs for "Loaded last scanned block from cache: X" message

### Slow Initial Scan
- This is expected on first boot
- Subsequent boots will be much faster
- Progress notifications show scan status

### Cache Corruption
If cache becomes corrupted, simply delete the cache state:

```python
cache_mgr.clear_cache_state()
```

Or manually delete: `~/.luna_wallet/cache_state.db`

## Future Enhancements

Potential improvements:
- Cache cleanup for old blocks
- Compression of cached data
- Multiple cache strategies (memory + disk)
- Cache validation and recovery
- Progress bar with percentage
- Estimated time remaining

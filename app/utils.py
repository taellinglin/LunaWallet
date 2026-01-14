from pathlib import Path

def setup_cache_directory():
    """Create cache directory for lunalib with proper permissions"""
    try:
        cache_locations = [
            Path.home() / "AppData" / "Local" / "lunalib" / "cache",
            Path.home() / ".lunalib" / "cache",
            Path("./.lunalib_cache"),
            Path("/tmp/lunalib_cache")
        ]
        for cache_dir in cache_locations:
            try:
                cache_dir.mkdir(parents=True, exist_ok=True)
                if cache_dir.exists():
                    print(f"DEBUG: Using cache directory: {cache_dir}")
                    return cache_dir
            except Exception:
                continue
        print("WARNING: Could not create any cache directory!")
    except Exception as e:
        print(f"ERROR: setup_cache_directory failed: {e}")

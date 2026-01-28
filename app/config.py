import os
import sys
import tempfile

_flet_storage = os.getenv("FLET_APP_STORAGE")

# Android fallback: prefer app-private storage if FLET_APP_STORAGE is not set
if not _flet_storage and ("android" in sys.platform):
	android_private = os.getenv("ANDROID_PRIVATE") or os.path.expanduser("~")
	_flet_storage = android_private
	os.environ.setdefault("FLET_APP_STORAGE", _flet_storage)

if _flet_storage:
	DATA_DIR = os.path.join(_flet_storage, "luna_wallet")
else:
	DATA_DIR = os.path.expanduser("~/.luna_wallet")

try:
	os.makedirs(DATA_DIR, exist_ok=True)
except Exception:
	# Last-resort fallback to temp directory
	fallback_dir = os.path.join(tempfile.gettempdir(), "luna_wallet")
	os.makedirs(fallback_dir, exist_ok=True)
	DATA_DIR = fallback_dir

DB_PATH = os.path.join(DATA_DIR, "wallets.db")

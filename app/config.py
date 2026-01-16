import os

_flet_storage = os.getenv("FLET_APP_STORAGE")
if _flet_storage:
	DATA_DIR = os.path.join(_flet_storage, "luna_wallet")
else:
	DATA_DIR = os.path.expanduser("~/.luna_wallet")
os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(DATA_DIR, "wallets.db")

import os

DATA_DIR = os.path.expanduser("~/.luna_wallet")
os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(DATA_DIR, "wallets.db")

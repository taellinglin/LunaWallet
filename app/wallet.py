# app/wallet.py

from lunalib.core.wallet import LunaWallet

class WalletService:
    def __init__(self):
        self.core = LunaWallet()

    def create_wallet(self, name, password):
        return self.core.create_wallet(name, password)

    def import_wallet(self, data, password):
        return self.core.import_wallet(data, password)

    def unlock_wallet(self, address, password):
        return self.core.unlock_wallet(address, password)

    def lock_wallet(self):
        return self.core.lock_wallet()

    def get_wallet_balance(self, address):
        """ウォレットのバランス取得（confirmed, pending, available）"""
        wallet = self.core.wallets.get(address)
        if wallet:
            return {
                "confirmed": wallet.get("confirmed_balance", 0.0),
                "pending": wallet.get("pending_balance", 0.0),
                "available": wallet.get("available_balance", 0.0),
            }
        return {"confirmed": 0.0, "pending": 0.0, "available": 0.0}

    def get_all_wallet_balances(self):
        """全ウォレットのバランス取得"""
        return {addr: self.get_wallet_balance(addr) for addr in self.core.wallets}

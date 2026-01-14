# app/mempool.py

from lunalib.core.mempool import MempoolManager

class MempoolService:
    def __init__(self):
        self.manager = MempoolManager()

    def get_pending_transactions(self, address):
        """指定アドレスの未承認トランザクションを取得"""
        return self.manager.get_pending_transactions(address)

    def get_pending_transactions_batch(self, addresses, fetch_remote=True):
        """複数アドレスの未承認トランザクションを一括取得"""
        return self.manager.get_pending_transactions_for_addresses(addresses, fetch_remote=fetch_remote)

# app/blockchain.py

from lunalib.core.blockchain import BlockchainManager

class BlockchainService:
    def __init__(self, endpoint_url="https://bank.linglin.art"):
        self.manager = BlockchainManager(endpoint_url=endpoint_url)

    def get_latest_block(self):
        return self.manager.get_latest_block()

    def get_block(self, height):
        return self.manager.get_block(height)

    def scan_transactions_for_address(self, address, start_height=0, end_height=None):
        return self.manager.scan_transactions_for_address(address, start_height, end_height)

    def scan_transactions_for_addresses(self, addresses, start_height=0, end_height=None):
        return self.manager.scan_transactions_for_addresses(addresses, start_height=start_height, end_height=end_height)

    def scan_for_updates(self):
        if hasattr(self.manager, 'scan_for_updates'):
            self.manager.scan_for_updates()

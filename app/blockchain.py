# app/blockchain.py

from lunalib.core.blockchain import BlockchainManager
import requests
import socket

class BlockchainService:
    def __init__(self, endpoint_url="https://bank.linglin.art"):
        self.endpoint_url = endpoint_url.rstrip("/")
        self.manager = BlockchainManager(endpoint_url=endpoint_url)
        self.peers = []

        # Patch manager with peer helpers for UI access
        try:
            self.manager.get_peer_count = self.get_peer_count
            self.manager.refresh_peers = self.refresh_peers
            self.manager.register_as_peer = self.register_as_peer
        except Exception:
            pass

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

    def _get_base_url(self) -> str:
        if "/api/" in self.endpoint_url:
            return self.endpoint_url.split("/api/")[0]
        return self.endpoint_url

    def _parse_peers(self, data):
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return data.get('peers') or data.get('nodes') or data.get('data') or []
        return []

    def refresh_peers(self) -> int:
        base_url = self._get_base_url()
        endpoints = [
            f"{base_url}/api/peers",
            f"{base_url}/peers",
            f"{base_url}/api/p2p/peers",
            f"{base_url}/p2p/peers",
        ]
        for endpoint in endpoints:
            try:
                response = requests.get(endpoint, timeout=5)
                if response.status_code == 200:
                    peers = self._parse_peers(response.json())
                    if peers is not None:
                        self.peers = peers
                        try:
                            self.manager.peers = peers
                        except Exception:
                            pass
                        return len(peers)
            except Exception:
                continue
        return len(self.peers) if self.peers else 0

    def get_peer_count(self) -> int:
        try:
            if hasattr(self.manager, 'peers') and self.manager.peers:
                return len(self.manager.peers)
        except Exception:
            pass
        if self.peers:
            return len(self.peers)
        return self.refresh_peers()

    def register_as_peer(self, my_address: str = None, my_port: int = None) -> bool:
        base_url = self._get_base_url()
        if not my_address:
            try:
                hostname = socket.gethostname()
                my_address = socket.gethostbyname(hostname)
            except Exception:
                my_address = "127.0.0.1"
        if not my_port:
            my_port = 8545

        endpoints = [
            f"{base_url}/api/peers/register",
            f"{base_url}/peers/register",
            f"{base_url}/peer/add",
        ]

        payloads = [
            {
                'address': my_address,
                'port': my_port,
                'node_type': 'wallet',
                'version': '1.0.0'
            },
            {
                'node_id': f"wallet-{my_address}:{my_port}",
                'timestamp': __import__("time").time(),
                'capabilities': ['sync', 'relay'],
                'peer_url': f"http://{my_address}:{my_port}"
            }
        ]

        for endpoint in endpoints:
            for payload in payloads:
                try:
                    response = requests.post(endpoint, json=payload, timeout=5)
                    if response.status_code in (200, 201):
                        return True
                except Exception:
                    continue
        return False

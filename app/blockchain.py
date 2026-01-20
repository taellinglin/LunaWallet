# app/blockchain.py

from lunalib.core.blockchain import BlockchainManager
from lunalib.core.p2p import P2PClient
import threading
import os

class BlockchainService:

    def __init__(self, endpoint_url="https://bank.linglin.art"):
        self.endpoint_url = endpoint_url.rstrip("/")
        self.manager = BlockchainManager(endpoint_url=endpoint_url)
        self.peers = []
        self.p2p_client = None
        self.p2p_enabled = str(os.getenv("LUNALIB_P2P_ENABLED", "")).strip().lower() in ("1", "true", "yes")
        self.p2p_skip_empty_peers = str(os.getenv("LUNALIB_P2P_SKIP_EMPTY_PEERS", "1")).strip().lower() in ("1", "true", "yes")

        # Patch manager with peer helpers for UI access
        try:
            self.manager.get_peer_count = self.get_peer_count
            self.manager.refresh_peers = self.refresh_peers
            self.manager.register_as_peer = self.register_as_peer
        except Exception:
            pass

        # Start P2P client in background (non-blocking) only if enabled
        if self.p2p_enabled:
            try:
                self._ensure_p2p_client(start_in_background=True)
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

    def _ensure_p2p_client(self, start_in_background: bool = False):
        if not self.p2p_enabled:
            return
        if self.p2p_client is None:
            self.p2p_client = P2PClient(primary_node_url=self.endpoint_url, prefer_peers=False)
            try:
                self.p2p_client.peer_seed_urls = []
            except Exception:
                pass
            if self.p2p_skip_empty_peers:
                try:
                    original_update = self.p2p_client._update_peer_list

                    def _safe_update_peer_list():
                        if not self.p2p_client.peer_seed_urls and not self.p2p_client.peers:
                            return []
                        return original_update()

                    self.p2p_client._update_peer_list = _safe_update_peer_list
                except Exception:
                    pass
        if start_in_background and not getattr(self.p2p_client, 'is_running', False):
            threading.Thread(target=self.p2p_client.start, daemon=True).start()

    def get_p2p_status(self) -> dict:
        """Return P2P client status for UI (running, peer_count)."""
        try:
            if not self.p2p_enabled:
                return {"running": False, "peers": 0}
            self._ensure_p2p_client(start_in_background=False)
            running = bool(getattr(self.p2p_client, 'is_running', False)) if self.p2p_client else False
            peers = len(getattr(self.p2p_client, 'peers', []) or []) if self.p2p_client else 0
            return {"running": running, "peers": peers}
        except Exception:
            return {"running": False, "peers": 0}

    def refresh_peers(self) -> int:
        try:
            if not self.p2p_enabled:
                return 0
            self._ensure_p2p_client(start_in_background=True)
            if self.p2p_client:
                self.peers = list(getattr(self.p2p_client, 'peers', []) or [])
                try:
                    self.manager.peers = self.peers
                except Exception:
                    pass
        except Exception:
            pass
        return len(self.peers) if self.peers else 0

    def get_peer_count(self) -> int:
        try:
            if not self.p2p_enabled:
                return 0
            if self.p2p_client and getattr(self.p2p_client, 'peers', None) is not None:
                return len(self.p2p_client.peers)
        except Exception:
            pass
        return self.refresh_peers()

    def register_as_peer(self, my_address: str = None, my_port: int = None) -> bool:
        try:
            if not self.p2p_enabled:
                return False
            self._ensure_p2p_client(start_in_background=True)
            return bool(self.p2p_client)
        except Exception:
            return False

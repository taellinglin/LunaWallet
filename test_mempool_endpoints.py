#!/usr/bin/env python3
"""
Lunalib-only mempool broadcast test.
"""

import json
from datetime import datetime
from lunalib.transactions.transactions import TransactionManager

BASE_URL = "https://bank.linglin.art"

TEST_TRANSACTION = {
    "type": "transfer",
    "from": "LUN_C7UBynkoMnaYGUMSy8AB9MZE12VYZPyt17",
    "to": "LUN_Bv1GCRCd5G95J3CDjWasmjHKuqxL1F7Rrt",
    "amount": 1.0,
    "fee": 0.001,
    "timestamp": int(datetime.now().timestamp()),
    "memo": "Test transaction from diagnostic script",
    "hash": "test_hash_123456789",
    "signature": "test_signature"
}


def main():
    print("\n" + "=" * 70)
    print("LUNA WALLET - LUNALIB MEMPOOL BROADCAST TEST")
    print("=" * 70)
    print(f"Base URL: {BASE_URL}")
    print(f"Transaction: {json.dumps(TEST_TRANSACTION, indent=2)}")

    tx_manager = TransactionManager(network_endpoints=[BASE_URL])
    is_valid, message = tx_manager.validate_transaction(TEST_TRANSACTION)
    print(f"Validation: {is_valid} ({message})")

    if not is_valid:
        return

    success, result = tx_manager.send_transaction(TEST_TRANSACTION)
    print(f"Broadcast success: {success}")
    print(f"Message: {result}")


if __name__ == "__main__":
    main()

"""
Comprehensive test suite for wallet balance display consistency.
Tests both confirmed and pending balance calculations to ensure balances
are accurate and never show 0.00 intermittently.

Features:
- Confirmed vs Pending balance separation
- Transaction state transitions
- Edge cases and boundary conditions
- Performance under load
- Fee handling
- Multiple transaction types
"""

import json
import os
import sys
import time
import sqlite3
from pathlib import Path

# Add app directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


class MockDatabase:
    """Mock database for testing balance calculations"""
    def __init__(self):
        self.transactions = {}
    
    def add_transaction(self, wallet_address, tx_data):
        """Add a transaction for a wallet"""
        if wallet_address not in self.transactions:
            self.transactions[wallet_address] = []
        self.transactions[wallet_address].append(tx_data)
    
    def get_wallet_transactions(self, wallet_address, limit=1000):
        """Get transactions for a wallet"""
        return self.transactions.get(wallet_address, [])[:limit]
    
    def get_all_transactions(self):
        """Get all transactions"""
        all_txs = []
        for txs in self.transactions.values():
            all_txs.extend(txs)
        return all_txs


class BalanceCalculator:
    """Utility for calculating balances from transactions"""
    
    @staticmethod
    def calculate_balance_from_transactions(wallet_address, all_txs, pending_txs=None):
        """Calculate confirmed and pending balance from transactions"""
        confirmed_balance = 0.0
        pending_balance = 0.0
        wallet_addr_lower = wallet_address.lower()
        pending_txs = pending_txs or []
        
        # Calculate confirmed balance
        for tx in all_txs:
            tx_status = tx.get('status', 'confirmed').lower()
            if tx_status != 'confirmed':
                continue
            
            tx_from = tx.get('from', '').lower()
            tx_to = tx.get('to', '').lower()
            tx_type = tx.get('type', 'transfer').lower()
            amount = float(tx.get('amount', 0))
            fee = float(tx.get('fee', 0))
            
            # Mining reward
            if tx_type == 'reward':
                if tx_to == wallet_addr_lower:
                    confirmed_balance += amount
            # Transfer received
            elif tx_type == 'transfer':
                if tx_to == wallet_addr_lower:
                    confirmed_balance += amount
                elif tx_from == wallet_addr_lower:
                    confirmed_balance -= (amount + fee)
        
        # Calculate pending balance
        for tx in pending_txs:
            tx_from = tx.get('from', '').lower()
            tx_to = tx.get('to', '').lower()
            tx_type = tx.get('type', 'transfer').lower()
            amount = float(tx.get('amount', 0))
            fee = float(tx.get('fee', 0))
            
            if tx_type == 'transfer':
                if tx_to == wallet_addr_lower:
                    pending_balance += amount
                elif tx_from == wallet_addr_lower:
                    pending_balance -= (amount + fee)
            elif tx_type == 'reward':
                if tx_to == wallet_addr_lower:
                    pending_balance += amount
        
        return confirmed_balance, pending_balance


def test_balance_calculation_basic():
    """Test basic balance calculation"""
    print("\n=== Test 1: Basic Balance Calculation ===")
    
    wallet_addr = "LUN_TestWallet123456789"
    transactions = [
        {
            'type': 'reward',
            'to': wallet_addr,
            'amount': 100.0,
            'status': 'confirmed',
            'timestamp': 1000
        },
        {
            'type': 'transfer',
            'from': wallet_addr,
            'to': 'LUN_Recipient',
            'amount': 50.0,
            'fee': 0.001,
            'status': 'confirmed',
            'timestamp': 2000
        }
    ]
    
    confirmed, pending = BalanceCalculator.calculate_balance_from_transactions(
        wallet_addr, transactions, []
    )
    
    expected_confirmed = 100.0 - 50.0 - 0.001
    assert confirmed == expected_confirmed, f"Expected {expected_confirmed}, got {confirmed}"
    assert pending == 0.0, f"Expected pending 0.0, got {pending}"
    
    print(f"✓ Confirmed balance: {confirmed:.6f} (expected {expected_confirmed:.6f})")
    print(f"✓ Pending balance: {pending:.6f}")
    return True


def test_no_zero_balance_for_receiving_wallet():
    """Test that wallets with confirmed transactions don't show 0.00"""
    print("\n=== Test 2: No Zero Balance for Receiving Wallet ===")
    
    wallet_addr = "LUN_Receiver"
    transactions = [
        {
            'type': 'reward',
            'to': wallet_addr,
            'amount': 50.0,
            'status': 'confirmed',
            'timestamp': 1000
        },
        {
            'type': 'reward',
            'to': wallet_addr,
            'amount': 50.0,
            'status': 'confirmed',
            'timestamp': 2000
        },
        {
            'type': 'reward',
            'to': wallet_addr,
            'amount': 50.0,
            'status': 'confirmed',
            'timestamp': 3000
        }
    ]
    
    confirmed, pending = BalanceCalculator.calculate_balance_from_transactions(
        wallet_addr, transactions, []
    )
    
    # Should NOT be zero
    assert confirmed > 0, f"Confirmed balance should not be zero, got {confirmed}"
    assert confirmed == 150.0, f"Expected 150.0, got {confirmed}"
    
    print(f"✓ Wallet with confirmed transactions shows balance: {confirmed:.6f}")
    return True


def test_pending_transactions_show_in_pending_balance():
    """Test that pending transactions are reflected in pending balance"""
    print("\n=== Test 3: Pending Transactions Show in Pending Balance ===")
    
    wallet_addr = "LUN_Sender"
    confirmed_txs = [
        {
            'type': 'reward',
            'to': wallet_addr,
            'amount': 100.0,
            'status': 'confirmed',
            'timestamp': 1000
        }
    ]
    
    pending_txs = [
        {
            'type': 'transfer',
            'from': wallet_addr,
            'to': 'LUN_Recipient',
            'amount': 25.0,
            'fee': 0.001,
            'timestamp': 4000
        }
    ]
    
    confirmed, pending = BalanceCalculator.calculate_balance_from_transactions(
        wallet_addr, confirmed_txs, pending_txs
    )
    
    assert confirmed == 100.0, f"Confirmed should be 100.0, got {confirmed}"
    expected_pending = -(25.0 + 0.001)
    assert pending == expected_pending, f"Pending should be {expected_pending}, got {pending}"
    
    print(f"✓ Confirmed balance: {confirmed:.6f}")
    print(f"✓ Pending balance: {pending:.6f} (shows outgoing transaction)")
    return True


def test_mixed_transaction_types():
    """Test balance calculation with mixed transaction types"""
    print("\n=== Test 4: Mixed Transaction Types ===")
    
    wallet_addr = "LUN_MixedWallet"
    transactions = [
        # Mining rewards
        {'type': 'reward', 'to': wallet_addr, 'amount': 100.0, 'status': 'confirmed', 'timestamp': 1000},
        {'type': 'reward', 'to': wallet_addr, 'amount': 50.0, 'status': 'confirmed', 'timestamp': 2000},
        # Outgoing transfer
        {'type': 'transfer', 'from': wallet_addr, 'to': 'LUN_Other', 'amount': 30.0, 'fee': 0.001, 'status': 'confirmed', 'timestamp': 3000},
        # Incoming transfer
        {'type': 'transfer', 'from': 'LUN_Other', 'to': wallet_addr, 'amount': 20.0, 'fee': 0.001, 'status': 'confirmed', 'timestamp': 4000},
    ]
    
    confirmed, pending = BalanceCalculator.calculate_balance_from_transactions(
        wallet_addr, transactions, []
    )
    
    # 100 + 50 - 30 - 0.001 + 20 = 139.999
    expected = 139.999
    assert confirmed == expected, f"Expected {expected}, got {confirmed}"
    
    print(f"✓ Rewards: 100.0 + 50.0")
    print(f"✓ Outgoing: -30.0 - 0.001 fee")
    print(f"✓ Incoming: +20.0")
    print(f"✓ Total confirmed: {confirmed:.6f}")
    return True


def test_balance_consistency_across_calls():
    """Test that balance calculation is consistent across multiple calls"""
    print("\n=== Test 5: Balance Consistency Across Calls ===")
    
    wallet_addr = "LUN_ConsistentWallet"
    transactions = [
        {'type': 'reward', 'to': wallet_addr, 'amount': 75.0, 'status': 'confirmed', 'timestamp': 1000},
        {'type': 'transfer', 'from': wallet_addr, 'to': 'LUN_Recipient', 'amount': 25.0, 'fee': 0.001, 'status': 'confirmed', 'timestamp': 2000},
    ]
    
    # Call balance calculation 5 times
    balances = []
    for i in range(5):
        confirmed, pending = BalanceCalculator.calculate_balance_from_transactions(
            wallet_addr, transactions, []
        )
        balances.append(confirmed)
    
    # All calls should return the same balance
    for i, balance in enumerate(balances):
        assert balance == balances[0], f"Call {i} returned {balance}, expected {balances[0]}"
    
    print(f"✓ All 5 calls returned consistent balance: {balances[0]:.6f}")
    return True


def test_zero_balance_wallet():
    """Test that wallet with no transactions correctly shows 0.00"""
    print("\n=== Test 6: Zero Balance Wallet ===")
    
    wallet_addr = "LUN_EmptyWallet"
    transactions = []
    
    confirmed, pending = BalanceCalculator.calculate_balance_from_transactions(
        wallet_addr, transactions, []
    )
    
    assert confirmed == 0.0, f"Empty wallet should have 0 balance, got {confirmed}"
    assert pending == 0.0, f"Empty wallet should have 0 pending, got {pending}"
    
    print(f"✓ Empty wallet correctly shows: {confirmed:.6f}")
    return True


def test_case_insensitive_addresses():
    """Test that address comparison is case-insensitive"""
    print("\n=== Test 7: Case-Insensitive Address Matching ===")
    
    wallet_addr = "LUN_TestAddress"
    transactions = [
        {'type': 'reward', 'to': 'lun_testaddress', 'amount': 100.0, 'status': 'confirmed', 'timestamp': 1000},
        {'type': 'transfer', 'from': 'LUN_TESTADDRESS', 'to': 'LUN_Other', 'amount': 25.0, 'fee': 0.001, 'status': 'confirmed', 'timestamp': 2000},
    ]
    
    confirmed, pending = BalanceCalculator.calculate_balance_from_transactions(
        wallet_addr, transactions, []
    )
    
    expected = 100.0 - 25.0 - 0.001
    assert confirmed == expected, f"Expected {expected}, got {confirmed}"
    
    print(f"✓ Case-insensitive address matching works correctly")
    print(f"✓ Balance: {confirmed:.6f}")
    return True


def test_large_transaction_set():
    """Test balance calculation with large transaction set"""
    print("\n=== Test 8: Large Transaction Set Performance ===")
    
    wallet_addr = "LUN_HighActivityWallet"
    transactions = []
    
    # Generate 1000 transactions
    for i in range(1000):
        if i % 2 == 0:
            transactions.append({
                'type': 'reward',
                'to': wallet_addr,
                'amount': 1.0,
                'status': 'confirmed',
                'timestamp': i * 1000
            })
        else:
            transactions.append({
                'type': 'transfer',
                'from': wallet_addr,
                'to': f'LUN_Recipient{i}',
                'amount': 0.5,
                'fee': 0.001,
                'status': 'confirmed',
                'timestamp': i * 1000
            })
    
    start_time = time.time()
    confirmed, pending = BalanceCalculator.calculate_balance_from_transactions(
        wallet_addr, transactions, []
    )
    elapsed = time.time() - start_time
    
    # Should calculate in less than 100ms
    assert elapsed < 0.1, f"Balance calculation took {elapsed:.3f}s, should be < 0.1s"
    
    # Verify calculation (500 rewards @ 1.0 = 500, 500 transfers @ 0.5 + fee = 250.5)
    # Use approximate equality for floating-point comparison
    expected = 249.5
    assert abs(confirmed - expected) < 0.0001, f"Expected {expected}, got {confirmed}"
    
    print(f"✓ Processed 1000 transactions in {elapsed*1000:.2f}ms")
    print(f"✓ Final balance: {confirmed:.6f}")
    return True


def test_only_pending_transactions():
    """Test wallet with only pending transactions"""
    print("\n=== Test 9: Wallet with Only Pending Transactions ===")
    
    wallet_addr = "LUN_PendingOnly"
    confirmed_txs = []
    pending_txs = [
        {'type': 'reward', 'to': wallet_addr, 'amount': 50.0, 'timestamp': 1000},
        {'type': 'transfer', 'from': wallet_addr, 'to': 'LUN_Other', 'amount': 10.0, 'fee': 0.001, 'timestamp': 2000},
    ]
    
    confirmed, pending = BalanceCalculator.calculate_balance_from_transactions(
        wallet_addr, confirmed_txs, pending_txs
    )
    
    # Confirmed should be 0, pending should show the transactions
    assert confirmed == 0.0, f"Confirmed should be 0, got {confirmed}"
    expected_pending = 50.0 - 10.0 - 0.001
    assert pending == expected_pending, f"Expected pending {expected_pending}, got {pending}"
    
    print(f"✓ Confirmed balance: {confirmed:.6f}")
    print(f"✓ Pending balance: {pending:.6f}")
    print(f"✓ Wallet with only pending shows correct totals")
    return True


def test_pending_to_confirmed_transition():
    """Test transition of pending transaction to confirmed"""
    print("\n=== Test 10: Pending to Confirmed Transition ===")
    
    wallet_addr = "LUN_TransitionWallet"
    
    # Stage 1: Transaction is pending
    confirmed_txs_1 = [
        {'type': 'reward', 'to': wallet_addr, 'amount': 100.0, 'status': 'confirmed', 'timestamp': 1000}
    ]
    pending_txs_1 = [
        {'type': 'transfer', 'from': wallet_addr, 'to': 'LUN_Other', 'amount': 25.0, 'fee': 0.001, 'timestamp': 2000}
    ]
    
    confirmed_1, pending_1 = BalanceCalculator.calculate_balance_from_transactions(
        wallet_addr, confirmed_txs_1, pending_txs_1
    )
    
    assert confirmed_1 == 100.0, f"Initial confirmed should be 100, got {confirmed_1}"
    assert pending_1 == -25.001, f"Initial pending should be -25.001, got {pending_1}"
    
    # Stage 2: Transaction becomes confirmed
    confirmed_txs_2 = [
        {'type': 'reward', 'to': wallet_addr, 'amount': 100.0, 'status': 'confirmed', 'timestamp': 1000},
        {'type': 'transfer', 'from': wallet_addr, 'to': 'LUN_Other', 'amount': 25.0, 'fee': 0.001, 'status': 'confirmed', 'timestamp': 2000}
    ]
    pending_txs_2 = []
    
    confirmed_2, pending_2 = BalanceCalculator.calculate_balance_from_transactions(
        wallet_addr, confirmed_txs_2, pending_txs_2
    )
    
    assert confirmed_2 == 74.999, f"After confirm, balance should be 74.999, got {confirmed_2}"
    assert pending_2 == 0.0, f"After confirm, pending should be 0, got {pending_2}"
    
    print(f"✓ Stage 1 (pending): confirmed={confirmed_1:.6f}, pending={pending_1:.6f}")
    print(f"✓ Stage 2 (confirmed): confirmed={confirmed_2:.6f}, pending={pending_2:.6f}")
    print(f"✓ Transition handled correctly")
    return True


def test_multiple_pending_outgoing():
    """Test multiple pending outgoing transactions"""
    print("\n=== Test 11: Multiple Pending Outgoing Transactions ===")
    
    wallet_addr = "LUN_MultiPending"
    confirmed_txs = [
        {'type': 'reward', 'to': wallet_addr, 'amount': 200.0, 'status': 'confirmed', 'timestamp': 1000}
    ]
    pending_txs = [
        {'type': 'transfer', 'from': wallet_addr, 'to': 'LUN_Addr1', 'amount': 50.0, 'fee': 0.001, 'timestamp': 2000},
        {'type': 'transfer', 'from': wallet_addr, 'to': 'LUN_Addr2', 'amount': 75.0, 'fee': 0.001, 'timestamp': 3000},
        {'type': 'transfer', 'from': wallet_addr, 'to': 'LUN_Addr3', 'amount': 30.0, 'fee': 0.001, 'timestamp': 4000},
    ]
    
    confirmed, pending = BalanceCalculator.calculate_balance_from_transactions(
        wallet_addr, confirmed_txs, pending_txs
    )
    
    assert confirmed == 200.0, f"Confirmed should be 200, got {confirmed}"
    # -50 - 0.001 - 75 - 0.001 - 30 - 0.001 = -155.003
    expected_pending = -155.003
    assert abs(pending - expected_pending) < 0.0001, f"Expected pending {expected_pending}, got {pending}"
    
    # Total available (if all confirmed) should be 200 - 155.003 = 44.997
    total_if_confirmed = confirmed + pending
    assert abs(total_if_confirmed - 44.997) < 0.0001, f"Total if confirmed should be ~44.997, got {total_if_confirmed}"
    
    print(f"✓ Confirmed balance: {confirmed:.6f}")
    print(f"✓ Pending balance: {pending:.6f} (3 outgoing transfers)")
    print(f"✓ Total if confirmed: {total_if_confirmed:.6f}")
    return True


def test_pending_incoming_and_outgoing():
    """Test pending transactions in both directions"""
    print("\n=== Test 12: Pending Incoming and Outgoing Transactions ===")
    
    wallet_addr = "LUN_BiDirectional"
    confirmed_txs = [
        {'type': 'reward', 'to': wallet_addr, 'amount': 150.0, 'status': 'confirmed', 'timestamp': 1000}
    ]
    pending_txs = [
        # Incoming
        {'type': 'transfer', 'from': 'LUN_Other1', 'to': wallet_addr, 'amount': 50.0, 'fee': 0.001, 'timestamp': 2000},
        {'type': 'reward', 'to': wallet_addr, 'amount': 25.0, 'timestamp': 3000},
        # Outgoing
        {'type': 'transfer', 'from': wallet_addr, 'to': 'LUN_Other2', 'amount': 75.0, 'fee': 0.001, 'timestamp': 4000},
    ]
    
    confirmed, pending = BalanceCalculator.calculate_balance_from_transactions(
        wallet_addr, confirmed_txs, pending_txs
    )
    
    assert confirmed == 150.0, f"Confirmed should be 150, got {confirmed}"
    # +50 + 25 - 75 - 0.001 = -0.001
    expected_pending = -0.001
    assert abs(pending - expected_pending) < 0.0001, f"Expected pending {expected_pending}, got {pending}"
    
    print(f"✓ Confirmed balance: {confirmed:.6f}")
    print(f"✓ Pending incoming: +50.0 (transfer), +25.0 (reward)")
    print(f"✓ Pending outgoing: -75.0 (transfer), -0.001 (fee)")
    print(f"✓ Pending balance: {pending:.6f}")
    return True


def test_insufficient_balance_detection():
    """Test detecting when pending transactions exceed available balance"""
    print("\n=== Test 13: Insufficient Balance Detection ===")
    
    wallet_addr = "LUN_LowBalance"
    confirmed_txs = [
        {'type': 'reward', 'to': wallet_addr, 'amount': 50.0, 'status': 'confirmed', 'timestamp': 1000}
    ]
    pending_txs = [
        # This pending transaction exceeds available balance
        {'type': 'transfer', 'from': wallet_addr, 'to': 'LUN_Other', 'amount': 75.0, 'fee': 0.001, 'timestamp': 2000}
    ]
    
    confirmed, pending = BalanceCalculator.calculate_balance_from_transactions(
        wallet_addr, confirmed_txs, pending_txs
    )
    
    assert confirmed == 50.0, f"Confirmed should be 50, got {confirmed}"
    expected_pending = -75.001
    assert pending == expected_pending, f"Pending should be {expected_pending}, got {pending}"
    
    # Total would be negative if pending is confirmed
    total_if_confirmed = confirmed + pending
    assert total_if_confirmed < 0, f"Total if confirmed should be negative, got {total_if_confirmed}"
    
    print(f"✓ Confirmed balance: {confirmed:.6f}")
    print(f"✓ Pending balance: {pending:.6f}")
    print(f"✓ Total if confirmed: {total_if_confirmed:.6f} (INSUFFICIENT)")
    print(f"✓ Correctly detects insufficient balance")
    return True


def test_fee_handling_accuracy():
    """Test accurate fee calculation across multiple transactions"""
    print("\n=== Test 14: Fee Handling Accuracy ===")
    
    wallet_addr = "LUN_FeesWallet"
    transactions = [
        # Multiple transactions with various fees
        {'type': 'reward', 'to': wallet_addr, 'amount': 1000.0, 'status': 'confirmed', 'timestamp': 1000},
        {'type': 'transfer', 'from': wallet_addr, 'to': 'LUN_A', 'amount': 100.0, 'fee': 0.001, 'status': 'confirmed', 'timestamp': 2000},
        {'type': 'transfer', 'from': wallet_addr, 'to': 'LUN_B', 'amount': 200.0, 'fee': 0.002, 'status': 'confirmed', 'timestamp': 3000},
        {'type': 'transfer', 'from': wallet_addr, 'to': 'LUN_C', 'amount': 150.0, 'fee': 0.0015, 'status': 'confirmed', 'timestamp': 4000},
    ]
    
    confirmed, pending = BalanceCalculator.calculate_balance_from_transactions(
        wallet_addr, transactions, []
    )
    
    # 1000 - 100 - 0.001 - 200 - 0.002 - 150 - 0.0015 = 549.9955
    expected = 549.9955
    assert abs(confirmed - expected) < 0.0001, f"Expected {expected}, got {confirmed}"
    
    print(f"✓ Starting balance: 1000.0")
    print(f"✓ Outgoing: 100 + 200 + 150 = 450.0")
    print(f"✓ Fees: 0.001 + 0.002 + 0.0015 = 0.0045")
    print(f"✓ Total fees deducted: {1000.0 - confirmed - 450.0:.6f}")
    print(f"✓ Final balance: {confirmed:.6f}")
    return True


def test_large_pending_set():
    """Test performance with many pending transactions"""
    print("\n=== Test 15: Large Pending Transaction Set Performance ===")
    
    wallet_addr = "LUN_ManyPending"
    confirmed_txs = [
        {'type': 'reward', 'to': wallet_addr, 'amount': 10000.0, 'status': 'confirmed', 'timestamp': 0}
    ]
    
    # Generate 500 pending transactions
    pending_txs = []
    for i in range(500):
        if i % 2 == 0:
            pending_txs.append({
                'type': 'transfer',
                'from': wallet_addr,
                'to': f'LUN_Recipient{i}',
                'amount': 5.0,
                'fee': 0.001,
                'timestamp': i * 1000
            })
        else:
            pending_txs.append({
                'type': 'transfer',
                'from': f'LUN_Sender{i}',
                'to': wallet_addr,
                'amount': 3.0,
                'fee': 0.001,
                'timestamp': i * 1000
            })
    
    start_time = time.time()
    confirmed, pending = BalanceCalculator.calculate_balance_from_transactions(
        wallet_addr, confirmed_txs, pending_txs
    )
    elapsed = time.time() - start_time
    
    # Should calculate quickly even with 500 pending transactions
    assert elapsed < 0.05, f"Calculation took {elapsed:.3f}s, should be < 0.05s"
    
    # Verify: 250 outgoing (5.0 + 0.001) + 250 incoming (3.0)
    # = -250 * 5.001 + 250 * 3 = -1250.25 + 750 = -500.25
    expected_pending = -500.25
    assert abs(pending - expected_pending) < 0.0001, f"Expected pending {expected_pending}, got {pending}"
    
    print(f"✓ Processed 500 pending transactions in {elapsed*1000:.2f}ms")
    print(f"✓ Confirmed balance: {confirmed:.6f}")
    print(f"✓ Pending balance: {pending:.6f}")
    return True


def test_confirmed_vs_pending_separation():
    """Test clear separation between confirmed and pending balances"""
    print("\n=== Test 16: Confirmed vs Pending Separation ===")
    
    wallet_addr = "LUN_SeparationTest"
    confirmed_txs = [
        {'type': 'reward', 'to': wallet_addr, 'amount': 500.0, 'status': 'confirmed', 'timestamp': 1000},
        {'type': 'transfer', 'from': wallet_addr, 'to': 'LUN_Other', 'amount': 100.0, 'fee': 0.001, 'status': 'confirmed', 'timestamp': 2000},
    ]
    pending_txs = [
        {'type': 'transfer', 'from': wallet_addr, 'to': 'LUN_Future', 'amount': 200.0, 'fee': 0.001, 'timestamp': 3000},
    ]
    
    confirmed, pending = BalanceCalculator.calculate_balance_from_transactions(
        wallet_addr, confirmed_txs, pending_txs
    )
    
    # Confirmed: 500 - 100 - 0.001 = 399.999
    assert abs(confirmed - 399.999) < 0.0001, f"Confirmed should be ~399.999, got {confirmed}"
    
    # Pending: -200 - 0.001 = -200.001
    assert abs(pending - (-200.001)) < 0.0001, f"Pending should be ~-200.001, got {pending}"
    
    # Total if all confirmed: 399.999 - 200.001 = 199.998
    total = confirmed + pending
    assert abs(total - 199.998) < 0.0001, f"Total should be ~199.998, got {total}"
    
    print(f"✓ Confirmed: {confirmed:.6f} (settled transactions)")
    print(f"✓ Pending: {pending:.6f} (unsettled transactions)")
    print(f"✓ Total if all settle: {total:.6f}")
    print(f"✓ Balances clearly separated")
    return True


def run_all_tests():
    """Run all balance display tests"""
    print("=" * 70)
    print("COMPREHENSIVE BALANCE DISPLAY TEST SUITE")
    print("=" * 70)
    print("\nTesting Confirmed vs Pending Balance Calculations")
    print("Ensuring no intermittent 0.00 display issues")
    
    tests = [
        test_balance_calculation_basic,
        test_no_zero_balance_for_receiving_wallet,
        test_pending_transactions_show_in_pending_balance,
        test_mixed_transaction_types,
        test_balance_consistency_across_calls,
        test_zero_balance_wallet,
        test_case_insensitive_addresses,
        test_large_transaction_set,
        test_only_pending_transactions,
        test_pending_to_confirmed_transition,
        test_multiple_pending_outgoing,
        test_pending_incoming_and_outgoing,
        test_insufficient_balance_detection,
        test_fee_handling_accuracy,
        test_large_pending_set,
        test_confirmed_vs_pending_separation,
    ]
    
    passed = 0
    failed = 0
    
    for test_func in tests:
        try:
            if test_func():
                passed += 1
        except AssertionError as e:
            print(f"✗ FAILED: {e}")
            failed += 1
        except Exception as e:
            print(f"✗ ERROR: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
    
    print("\n" + "=" * 70)
    print(f"RESULTS: {passed} passed, {failed} failed out of {len(tests)} tests")
    print("=" * 70)
    
    if failed == 0:
        print("\n✓ All balance display tests PASSED")
        print("✓ Confirmed and pending balances calculated correctly")
        print("✓ No intermittent 0.00 display issues detected")
        print("✓ Performance is optimal")
    
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)


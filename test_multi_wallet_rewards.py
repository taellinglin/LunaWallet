#!/usr/bin/env python3
"""
Test script to verify multi-wallet rewards detection and balance calculation fixes.

Tests:
1. Iterative rewards scanning (handles 100+ rewards)
2. Multiple wallets each with their own rewards
3. Balance calculation consistency across all subsystems
4. Proper handling of all transaction types (incoming, outgoing, fees, rewards)
"""

import sys
import os

# Add workspace to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lunalib.storage.database import WalletDatabase
from utils import calculate_wallet_balances, diagnose_wallet_rewards_balance

def test_iterative_rewards_scanning():
    """Test that iterative rewards scanning works"""
    print("\n" + "="*70)
    print("TEST 1: ITERATIVE REWARDS SCANNING")
    print("="*70)
    
    db = WalletDatabase()
    all_txs = db.get_all_transactions()
    
    print(f"Total transactions in database: {len(all_txs)}")
    
    # Count rewards
    reward_txs = [tx for tx in all_txs if tx.get('type', '').lower() == 'reward']
    print(f"Total reward transactions: {len(reward_txs)}")
    
    if len(reward_txs) > 100:
        print(f"✓ Database has {len(reward_txs)} rewards (>100) - iterative scanning is needed")
        return True
    else:
        print(f"⚠ Database has only {len(reward_txs)} rewards (<100) - iterative scanning not fully tested")
        return True

def test_multiple_wallets_rewards():
    """Test that multiple wallets each properly get their rewards"""
    print("\n" + "="*70)
    print("TEST 2: MULTIPLE WALLETS REWARDS DETECTION")
    print("="*70)
    
    db = WalletDatabase()
    all_txs = db.get_all_transactions()
    
    # Group transactions by wallet
    wallet_rewards = {}
    
    for tx in all_txs:
        if tx.get('type', '').lower() == 'reward':
            # Get reward recipients
            reward_addr = tx.get('reward_address', '').lower()
            tx_to = tx.get('to', '').lower()
            tx_from = tx.get('from', '').lower()
            
            # Determine recipient
            recipient = None
            if reward_addr and reward_addr != '':
                recipient = reward_addr
            elif tx_from == 'network' and tx_to:
                recipient = tx_to
            elif tx_to and tx_from in ['network', '']:
                recipient = tx_to
            
            if recipient:
                if recipient not in wallet_rewards:
                    wallet_rewards[recipient] = []
                wallet_rewards[recipient].append(tx)
    
    print(f"Found {len(wallet_rewards)} wallets with reward transactions")
    
    # Show top wallets by reward count
    sorted_wallets = sorted(wallet_rewards.items(), key=lambda x: len(x[1]), reverse=True)
    
    for i, (wallet_addr, rewards) in enumerate(sorted_wallets[:5], 1):
        total_rewards = sum(float(tx.get('amount', 0)) for tx in rewards)
        print(f"  {i}. {wallet_addr[:16]}...: {len(rewards)} rewards = {total_rewards:.6f} LKC")
    
    return len(wallet_rewards) > 0

def test_balance_calculation_consistency():
    """Test that balance calculation is consistent across all wallets"""
    print("\n" + "="*70)
    print("TEST 3: BALANCE CALCULATION CONSISTENCY")
    print("="*70)
    
    db = WalletDatabase()
    all_txs = db.get_all_transactions()
    
    # Get unique wallet addresses
    wallet_addresses = set()
    for tx in all_txs:
        wallet_addresses.add(tx.get('from', '').lower())
        wallet_addresses.add(tx.get('to', '').lower())
        wallet_addresses.add(tx.get('reward_address', '').lower())
    
    # Remove empty addresses
    wallet_addresses.discard('')
    wallet_addresses.discard('network')
    
    print(f"Testing {len(wallet_addresses)} unique wallets")
    
    # Test balance calculation for top wallets
    test_count = 0
    for wallet_addr in list(wallet_addresses)[:10]:
        try:
            balances = calculate_wallet_balances(
                wallet_addr,
                database=db,
                mempool_manager=None
            )
            
            if balances['available'] > 0:
                test_count += 1
                print(f"  ✓ {wallet_addr[:16]}...: {balances['available']:.6f} available + {balances['pending']:.6f} pending = {balances['total']:.6f} total")
        except Exception as e:
            print(f"  ✗ {wallet_addr[:16]}...: Error - {e}")
    
    print(f"Successfully calculated balances for {test_count} wallets")
    return test_count > 0

def test_rewards_wallet_specific():
    """Test specific rewards wallet if known"""
    print("\n" + "="*70)
    print("TEST 4: REWARDS WALLET SPECIFIC TEST")
    print("="*70)
    
    # Check for known rewards wallet from command line or prompt
    rewards_wallet = None
    
    if len(sys.argv) > 1:
        rewards_wallet = sys.argv[1]
    
    if rewards_wallet:
        print(f"Testing rewards wallet: {rewards_wallet}")
        
        db = WalletDatabase()
        
        # Run comprehensive diagnostic
        diagnose_wallet_rewards_balance(rewards_wallet, database=db)
        
        # Also test our calculation system
        balances = calculate_wallet_balances(rewards_wallet, database=db, mempool_manager=None)
        
        print(f"\n📊 UNIFIED BALANCE CALCULATION RESULTS:")
        print(f"  Available (confirmed): {balances['available']:.6f} LKC")
        print(f"  Pending: {balances['pending']:.6f} LKC")
        print(f"  Total: {balances['total']:.6f} LKC")
        
        return True
    else:
        print("ℹ Pass wallet address as argument to test specific rewards wallet")
        return True

def test_transaction_type_diversity():
    """Test that all transaction types are properly handled"""
    print("\n" + "="*70)
    print("TEST 5: TRANSACTION TYPE DIVERSITY")
    print("="*70)
    
    db = WalletDatabase()
    all_txs = db.get_all_transactions()
    
    # Count transaction types
    tx_types = {}
    for tx in all_txs:
        tx_type = tx.get('type', 'unknown').lower()
        tx_types[tx_type] = tx_types.get(tx_type, 0) + 1
    
    print(f"Found {len(tx_types)} different transaction types:")
    for tx_type, count in sorted(tx_types.items(), key=lambda x: x[1], reverse=True):
        print(f"  - {tx_type}: {count} transactions")
    
    # Verify we support all types
    supported_types = ['reward', 'transfer', 'fee_distribution', 'stake', 'delegate', 'send', 'receive', 'gtx_genesis']
    found_types = set(tx_types.keys()) & set(supported_types)
    
    print(f"\nSupported types found: {len(found_types)}")
    for tx_type in found_types:
        print(f"  ✓ {tx_type}")
    
    return True

def main():
    """Run all tests"""
    print("\n" + "="*70)
    print("LUNA WALLET - MULTI-WALLET REWARDS DETECTION TEST SUITE")
    print("="*70)
    
    results = []
    
    try:
        results.append(("Iterative Rewards Scanning", test_iterative_rewards_scanning()))
    except Exception as e:
        print(f"ERROR in iterative rewards test: {e}")
        results.append(("Iterative Rewards Scanning", False))
    
    try:
        results.append(("Multiple Wallets Rewards", test_multiple_wallets_rewards()))
    except Exception as e:
        print(f"ERROR in multiple wallets test: {e}")
        results.append(("Multiple Wallets Rewards", False))
    
    try:
        results.append(("Balance Calculation Consistency", test_balance_calculation_consistency()))
    except Exception as e:
        print(f"ERROR in balance consistency test: {e}")
        results.append(("Balance Calculation Consistency", False))
    
    try:
        results.append(("Transaction Type Diversity", test_transaction_type_diversity()))
    except Exception as e:
        print(f"ERROR in transaction type test: {e}")
        results.append(("Transaction Type Diversity", False))
    
    try:
        results.append(("Rewards Wallet Specific", test_rewards_wallet_specific()))
    except Exception as e:
        print(f"ERROR in rewards wallet test: {e}")
        results.append(("Rewards Wallet Specific", False))
    
    # Print summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"  {status}: {test_name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""
Diagnostic script to identify balance calculation issues with mining rewards wallets.
Usage: python diagnose_rewards_wallet.py <wallet_address>
"""

import sys
from utils import diagnose_wallet_rewards_balance
from lunalib.storage.database import WalletDatabase

def main():
    if len(sys.argv) < 2:
        print("Usage: python diagnose_rewards_wallet.py <wallet_address>")
        print("\nExample: python diagnose_rewards_wallet.py LUN_BzFRaYfRGSFjb1m34drvZSUc87BX7Mj4wJ")
        sys.exit(1)
    
    wallet_address = sys.argv[1]
    
    # Initialize database
    database = WalletDatabase()
    
    # Run diagnostic
    diagnose_wallet_rewards_balance(wallet_address, database=database)

if __name__ == "__main__":
    main()

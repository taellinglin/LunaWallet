#!/usr/bin/env python
import sys
sys.path.append('.')

from app.core import LunaWalletApp

# Initialize app
app = LunaWalletApp()

# Load wallet data first
print('Loading wallets...')
app.load_wallet_data()

if hasattr(app.wallet_core, 'wallets') and app.wallet_core.wallets:
    wallets = list(app.wallet_core.wallets.keys())
    print('Found wallets:', len(wallets))
    for w in wallets:
        print(' ', w[:20] + '...')
    
    # Perform full blockchain scan
    print('\nPerforming blockchain scan...')
    app.scan_all_wallets_for_changes(force_full_scan=True)
    print('\nScan complete')
else:
    print('No wallets')

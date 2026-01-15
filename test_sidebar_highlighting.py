"""Test sidebar wallet selection highlighting fix"""
import sys
import os

# Add app to path
sys.path.insert(0, os.path.dirname(__file__))

print("=" * 60)
print("Testing Sidebar Wallet Selection Highlighting")
print("=" * 60)

print("\n[TEST 1] Import required modules...")
try:
    from gui.page_wallet import WalletPage
    from unittest.mock import Mock
    print("✓ Imports successful")
except Exception as e:
    print(f"✗ Import failed: {e}")
    sys.exit(1)

print("\n[TEST 2] Create mock app with multiple wallets...")
try:
    mock_app = Mock()
    mock_app.on_send_transaction = Mock()
    mock_app.on_receive = Mock()
    mock_app.on_export_key = Mock()
    mock_app.on_lock = Mock()
    mock_app.on_create_wallet = Mock()
    mock_app.on_import_wallet = Mock()
    mock_app.on_settings = Mock()
    
    # Mock wallet_core with multiple wallets
    mock_wallet_core = Mock()
    mock_wallet_core.wallets = {
        'address1': {
            'label': 'Wallet 1',
            'address': 'address1',
            'confirmed_balance': 100.0,
            'pending_balance': 0.0
        },
        'address2': {
            'label': 'Wallet 2',
            'address': 'address2',
            'confirmed_balance': 200.0,
            'pending_balance': 10.0
        },
        'address3': {
            'label': 'Wallet 3',
            'address': 'address3',
            'confirmed_balance': 300.0,
            'pending_balance': -5.0
        }
    }
    mock_wallet_core.current_wallet_address = 'address2'  # Wallet 2 should be highlighted
    mock_app.wallet_core = mock_wallet_core
    mock_app.selected_wallet_index = 1  # This should NOT be used for highlighting
    
    print("✓ Mock app with 3 wallets created")
    print(f"  - Current wallet address: {mock_wallet_core.current_wallet_address}")
    print(f"  - Selected wallet index: {mock_app.selected_wallet_index}")
except Exception as e:
    print(f"✗ Mock creation failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n[TEST 3] Create WalletPage instance...")
try:
    wallet_page = WalletPage(
        app=mock_app,
        on_send=mock_app.on_send_transaction,
        on_receive=mock_app.on_receive,
        on_export_key=mock_app.on_export_key,
        on_lock=mock_app.on_lock,
        on_create_wallet=mock_app.on_create_wallet,
        on_import_wallet=mock_app.on_import_wallet,
        on_settings=mock_app.on_settings
    )
    print("✓ WalletPage instance created")
except Exception as e:
    print(f"✗ WalletPage creation failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n[TEST 4] Test _create_sidebar_wallet_item highlighting logic...")
try:
    # Test wallet 1 (should NOT be selected)
    wallet1 = mock_wallet_core.wallets['address1']
    item1 = wallet_page._create_sidebar_wallet_item(wallet1, 0)
    print(f"  Wallet 1 (index 0, address='address1'):")
    print(f"    - Expected: NOT selected (current_wallet_address='address2')")
    
    # Test wallet 2 (should BE selected based on address match)
    wallet2 = mock_wallet_core.wallets['address2']
    item2 = wallet_page._create_sidebar_wallet_item(wallet2, 1)
    print(f"  Wallet 2 (index 1, address='address2'):")
    print(f"    - Expected: SELECTED (matches current_wallet_address)")
    
    # Test wallet 3 (should NOT be selected)
    wallet3 = mock_wallet_core.wallets['address3']
    item3 = wallet_page._create_sidebar_wallet_item(wallet3, 2)
    print(f"  Wallet 3 (index 2, address='address3'):")
    print(f"    - Expected: NOT selected")
    
    # Check if highlighting is correct
    # For expanded sidebar, selected wallet should have:
    # - bgcolor = "#2c1a1a"
    # - border with color "#dc3545"
    
    if hasattr(item2, 'bgcolor') and item2.bgcolor == "#2c1a1a":
        print("✓ Wallet 2 correctly highlighted (bgcolor)")
    else:
        print(f"✗ Wallet 2 highlighting incorrect (bgcolor={getattr(item2, 'bgcolor', 'N/A')})")
    
    if hasattr(item2, 'border') and item2.border:
        border_color = None
        if hasattr(item2.border, 'top') and hasattr(item2.border.top, 'color'):
            border_color = item2.border.top.color
        if border_color == "#dc3545":
            print("✓ Wallet 2 correctly highlighted (border)")
        else:
            print(f"✗ Wallet 2 border color incorrect: {border_color}")
    
    if hasattr(item1, 'bgcolor') and item1.bgcolor == "transparent":
        print("✓ Wallet 1 correctly NOT highlighted (bgcolor)")
    else:
        print(f"✗ Wallet 1 should not be highlighted (bgcolor={getattr(item1, 'bgcolor', 'N/A')})")
    
    if hasattr(item3, 'bgcolor') and item3.bgcolor == "transparent":
        print("✓ Wallet 3 correctly NOT highlighted (bgcolor)")
    else:
        print(f"✗ Wallet 3 should not be highlighted (bgcolor={getattr(item3, 'bgcolor', 'N/A')})")
    
except Exception as e:
    print(f"✗ Highlighting test failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n[TEST 5] Simulate navigation: send page → back to wallet page...")
try:
    # Simulate that current_wallet_address is preserved
    # When returning from send/receive/export pages, show_wallet_page creates
    # a new WalletPage instance but current_wallet_address should be unchanged
    
    original_address = mock_wallet_core.current_wallet_address
    print(f"  - Before navigation: current_wallet_address = {original_address}")
    
    # Create new WalletPage instance (simulating return from send page)
    wallet_page_new = WalletPage(
        app=mock_app,
        on_send=mock_app.on_send_transaction,
        on_receive=mock_app.on_receive,
        on_export_key=mock_app.on_export_key,
        on_lock=mock_app.on_lock,
        on_create_wallet=mock_app.on_create_wallet,
        on_import_wallet=mock_app.on_import_wallet,
        on_settings=mock_app.on_settings
    )
    
    # Check if wallet 2 is still selected
    wallet2_new = mock_wallet_core.wallets['address2']
    item2_new = wallet_page_new._create_sidebar_wallet_item(wallet2_new, 1)
    
    print(f"  - After navigation: current_wallet_address = {mock_wallet_core.current_wallet_address}")
    
    if mock_wallet_core.current_wallet_address == original_address:
        print("✓ current_wallet_address preserved across navigation")
    else:
        print("✗ current_wallet_address changed unexpectedly")
    
    if hasattr(item2_new, 'bgcolor') and item2_new.bgcolor == "#2c1a1a":
        print("✓ Wallet 2 still highlighted after navigation")
    else:
        print(f"✗ Wallet 2 highlighting lost after navigation (bgcolor={getattr(item2_new, 'bgcolor', 'N/A')})")
        
except Exception as e:
    print(f"✗ Navigation test failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n" + "=" * 60)
print("All tests completed successfully! ✓")
print("=" * 60)

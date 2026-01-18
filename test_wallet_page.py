"""Quick test to identify the unlock blocking issue"""
import sys
import os

# Add app to path
sys.path.insert(0, os.path.dirname(__file__))

print("[DEBUG] Test 1: Can we import required modules?")
try:
    from gui.page_wallet import WalletPage
    print("[DEBUG] ✓ WalletPage imported successfully")
except Exception as e:
    print(f"[DEBUG] ✗ Failed to import WalletPage: {e}")
    sys.exit(1)

print("\n[DEBUG] Test 2: Can we create a mock WalletPage?")
try:
    from unittest.mock import Mock
    
    mock_app = Mock()
    mock_app.on_send_transaction = Mock()
    mock_app.on_receive = Mock()
    mock_app.on_export_key = Mock()
    mock_app.on_lock = Mock()
    mock_app.on_create_wallet = Mock()
    mock_app.on_import_wallet = Mock()
    mock_app.on_settings = Mock()
    
    print("[DEBUG] Creating WalletPage instance...")
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
    print("[DEBUG] ✓ WalletPage instance created successfully")
    
    print("[DEBUG] Calling wallet_page.create()...")
    ui = wallet_page.create()
    print("[DEBUG] ✓ wallet_page.create() completed successfully")
    print(f"[DEBUG]   Result type: {type(ui)}")
    
except Exception as e:
    print(f"[DEBUG] ✗ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n[DEBUG] All tests passed!")

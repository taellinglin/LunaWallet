import flet as ft
import threading
import time
import json
import io
import os
import sys
from typing import Dict, List, Optional
import hashlib
import secrets
import base64
from cryptography.fernet import Fernet
from datetime import datetime
from PIL import Image
import pystray

# Import the wallet library
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from luna_lib import LunaLib, SecureDataManager

class LunaWalletApp:
    """Luna Wallet Application with System Tray and Red Theme"""
    
    def __init__(self):
        self.wallet_core = LunaLib(auto_scan=False)  # Don't auto-scan until unlocked
        self.minimized_to_tray = False
        self.current_tab_index = 0
        self.snack_bar = None
        self.selected_wallet_index = 0  # Track currently selected wallet
        self.last_activity_time = time.time()  # Track user activity for auto-lock
        self.auto_lock_minutes = 30  # Auto-lock after 30 minutes of inactivity
        self.is_locked = True  # Start locked

        # System tray
        self.tray_icon = None
        self.tray_thread = None

        # Set up wallet callbacks
        self.wallet_core.on_balance_changed = self.on_balance_changed
        self.wallet_core.on_transaction_received = self.on_transaction_received
        self.wallet_core.on_sync_complete = self.on_sync_complete
        self.wallet_core.on_error = self.on_error

        # Refs for UI elements
        self.refs = {}
    def on_balance_changed(self):
        """Handle balance updates"""
        self.update_balance_display()
        self.auto_save_wallet()
        
    def on_transaction_received(self):
        """Handle new transactions"""
        self.update_transaction_history()
        self.add_log_message("New transaction received", "success")
        self.auto_save_wallet()
        
    def on_sync_complete(self):
        """Handle sync completion"""
        self.update_balance_display()
        self.update_transaction_history()
        self.add_log_message("Blockchain sync completed", "success")
        self.auto_save_wallet()
        
    def on_error(self, error_msg):
        """Handle errors"""
        self.add_log_message(f"Error: {error_msg}", "error")
        
    def create_main_ui(self, page: ft.Page):
        """Create the main wallet interface"""
        self.page = page
        
        # Page setup with custom font
        page.title = "Luna Wallet"
        page.theme_mode = ft.ThemeMode.DARK
        page.fonts = {
            "Custom": "./font.ttf"
        }
        page.theme = ft.Theme(
            font_family="Custom", # Try this if available
        )
        
        page.padding = 0
        page.window.width = 1000
        page.window.height = 800
        page.window.min_width = 1000
        page.window.min_height = 800
        page.window.center()
        
        # Set window icon
        page.window.icon = "./wallet_icon.png"
        
        # Handle window events
        page.on_window_event = self.on_window_event
        
        # Track user activity
        page.on_keyboard_event = self.on_keyboard_activity
        page.on_click = self.on_mouse_activity
        
        # Create main layout (will be locked initially)
        self.main_layout = self.create_main_layout()
        page.add(self.main_layout)
        
        # Check if wallet file exists
        wallet_file_path = os.path.join(SecureDataManager.get_data_dir(), "wallet_encrypted.dat")
        if os.path.exists(wallet_file_path):
            # Wallet file exists, show unlock screen
            self.show_lock_screen("Welcome Back", "Please unlock your wallet to continue")
        else:
            # No wallet file, show create wallet screen
            self.show_lock_screen("Welcome to Luna Wallet", "Create your first wallet to get started", show_create=True)
        
        # Start activity monitor for auto-lock
        threading.Thread(target=self.activity_monitor, daemon=True).start()

    def show_lock_screen(self, title, subtitle, show_create=False):
        """Show lock screen overlay"""
        self.is_locked = True

        # Create a full-screen overlay for lock screen
        overlay_container = ft.Container(
            width=self.page.window.width,
            height=self.page.window.height,
            left=0,
            top=-self.page.window.height,  # Start above the screen
            bgcolor="#1a0f0f",
            padding=20,
            animate_position=ft.Animation(500, "easeOut"),
        )
        def unlock_wallet(e=None):
            if not password_field:
                return
            password = password_field.value
            
            if not password:
                self.show_snack_bar("Please enter a password")
                return
            
            # Show loading indicator
            for control in main_content.content.controls:
                if isinstance(control, ft.Row) and control.controls:
                    if isinstance(control.controls[0], ft.ElevatedButton):
                        control.controls[0].disabled = True
                        control.controls[0].text = "Unlocking..."
                        break
            
            if password_field:
                password_field.disabled = True
            
            self.page.update()
            
            # Unlock in background thread
            def unlock_thread():
                success = self.wallet_core.unlock_wallet(password)
            
                def update_ui():
                    if success:
                        self.is_locked = False
                        self.last_activity_time = time.time()
                        self.add_log_message("Wallet unlocked successfully", "success")
                        self.update_balance_display()
                        self.update_wallets_list()
                        self.update_transaction_history()
                        
                        # Animate out
                        overlay_container.top = -self.page.height
                        self.page.update()
                        time.sleep(0.5)
                        self.page.overlay.clear()
                        self.page.update()
                        
                        # Start auto-scan now that we're unlocked
                        self.wallet_core.start_auto_scan()
                        
                        self.show_snack_bar("Wallet unlocked!")
                    else:
                        self.add_log_message("Failed to unlock wallet", "error")
                        # Reset UI
                        for control in main_content.content.controls:
                            if isinstance(control, ft.Row) and control.controls:
                                if isinstance(control.controls[0], ft.ElevatedButton):
                                    control.controls[0].disabled = False
                                    control.controls[0].text = "Unlock Wallet"
                                    break
                        
                        if password_field:
                            password_field.disabled = False
                            password_field.value = ""
                            password_field.focus()
                        
                        self.page.update()
                        self.show_snack_bar("Failed to unlock wallet - wrong password")
                        
                self.page.run_thread(update_ui)
            
            threading.Thread(target=unlock_thread, daemon=True).start()
        # Main content container that centers everything
        def create_wallet(e):
            # Animate out
            overlay_container.top = -self.page.height
            self.page.update()
            time.sleep(0.5)
            self.page.overlay.clear()
            self.page.update()
            self.show_create_wallet_dialog()
        main_content = ft.Container(
            content=ft.Column([
                # Header with red icon and text
                ft.Row([
                    ft.Container(
                        content=ft.Image(
                            src="./wallet_icon.png",
                            width=100,
                            height=100,
                            fit=ft.ImageFit.CONTAIN,
                            color="#dc3545",
                            color_blend_mode=ft.BlendMode.SRC_IN,
                            error_content=ft.Text("🔴", size=50)
                        ),
                        margin=ft.margin.only(right=25),
                        bgcolor="#00000000",  # Make background transparent
                    ),
                    ft.Column([
                        ft.Text(title, size=32, color="#dc3545", weight="bold"),
                        ft.Text(subtitle, size=18, color="#f8d7da"),
                    ])
                ], alignment=ft.MainAxisAlignment.CENTER),
                
                ft.Container(height=40),
                
                # Password field (only show if not creating)
                ft.Container(
                    content=ft.TextField(
                        label="Wallet Password",
                        hint_text="Enter your wallet password",
                        password=True,
                        can_reveal_password=True,
                        width=400,
                        color="#f8d7da",
                        border_color="#5c2e2e",
                        autofocus=True,
                    ) if not show_create else ft.Container(height=0),
                    alignment=ft.alignment.center
                ),
                
                ft.Container(height=20),
                
                # Action button
                ft.Row([
                    ft.ElevatedButton(
                        "Create New Wallet" if show_create else "Unlock Wallet",
                        on_click=create_wallet if show_create else unlock_wallet,
                        style=ft.ButtonStyle(
                            color="#ffffff",
                            bgcolor="#dc3545",
                            padding=ft.padding.symmetric(horizontal=30, vertical=15),
                            shape=ft.RoundedRectangleBorder(radius=4)
                        ),
                        height=45
                    )
                ], alignment=ft.MainAxisAlignment.CENTER),
                
                ft.Container(height=20),
                
                # Additional options
                ft.Row([
                    ft.TextButton(
                        "Create New Wallet Instead",
                        on_click=create_wallet,
                        style=ft.ButtonStyle(color="#dc3545")
                    ) if not show_create else ft.Container()
                ], alignment=ft.MainAxisAlignment.CENTER)
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            alignment=ft.alignment.center,
            width=self.page.width,
            height=self.page.height,
        )
        
        # Get references to controls
        password_field = None
        if not show_create:
            for control in main_content.content.controls:
                if hasattr(control, 'content') and isinstance(control.content, ft.TextField):
                    password_field = control.content
                    break
        
        
        
        
        
        # Set up password field on_submit
        if password_field:
            password_field.on_submit = unlock_wallet
        
        overlay_container.content = main_content
        self.page.overlay.append(overlay_container)
        self.page.update()
        
        # Animate in
        overlay_container.top = 0
        self.page.update()
            
    def lock_wallet(self):
        """Lock the wallet and show lock screen"""
        self.is_locked = True
        self.wallet_core.lock_wallet()
        self.show_lock_screen("Wallet Locked", "Please unlock to continue")
        self.add_log_message("Wallet locked", "info")
        
    def activity_monitor(self):
        """Monitor user activity and auto-lock after timeout"""
        while True:
            try:
                current_time = time.time()
                inactive_time = current_time - self.last_activity_time
                
                # Auto-lock after specified minutes of inactivity
                if (not self.is_locked and 
                    inactive_time > self.auto_lock_minutes * 60 and 
                    self.wallet_core.is_unlocked):
                    self.add_log_message(f"Auto-locking wallet after {self.auto_lock_minutes} minutes of inactivity", "info")
                    self.lock_wallet()
                
                time.sleep(10)  # Check every 10 seconds
            except Exception as e:
                print(f"Activity monitor error: {e}")
                time.sleep(10)
    
    def on_keyboard_activity(self, e):
        if not self.is_locked:
            self.last_activity_time = time.time()

    def create_main_layout(self):
        sidebar = self.create_sidebar()
        
        # Main content area with tabs
        main_content = self.create_main_content()
        
        # Main layout
        return ft.Row(
            [sidebar, ft.VerticalDivider(width=1, color="#5c2e2e"), main_content],
            expand=True,
            spacing=0
        )

    def on_mouse_activity(self, e):
        """Track mouse activity"""
        if not self.is_locked:
            self.last_activity_time = time.time()

    def on_window_resize(self, e):
        """Handle window resize events"""
        # Log the resize event
        self.add_log_message(f"Window resized to {e.width}x{e.height}", "info")

        # Update any size-dependent UI elements if needed
        # For now, just ensure overlays are properly positioned
        pass
            
    def create_sidebar(self):
        """Create the sidebar with wallet info and quick actions"""
        # Sidebar width
        sidebar_width = 240
        
        # Wallet status
        self.refs['lbl_wallet_name'] = ft.Ref[ft.Text]()
        self.refs['lbl_address'] = ft.Ref[ft.Text]()
        self.refs['lbl_balance'] = ft.Ref[ft.Text]()
        self.refs['lbl_available'] = ft.Ref[ft.Text]()
        self.refs['lbl_pending'] = ft.Ref[ft.Text]()
        self.refs['lbl_transactions'] = ft.Ref[ft.Text]()
        
        wallet_status = ft.Container(
            content=ft.Column([
                ft.Text("👛 Wallet Status", size=14, color="#f8d7da"),
                ft.Text("Name: --", ref=self.refs['lbl_wallet_name'], size=12, color="#f8d7da"),
                ft.Text("Address: --", ref=self.refs['lbl_address'], size=10, color="#f8d7da"),
                ft.Text("Balance: --", ref=self.refs['lbl_balance'], size=12, color="#f8d7da"),
                ft.Text("Available: --", ref=self.refs['lbl_available'], size=10, color="#f8d7da"),
                ft.Text("Pending: --", ref=self.refs['lbl_pending'], size=10, color="#f8d7da"),
                ft.Text("Transactions: --", ref=self.refs['lbl_transactions'], size=10, color="#f8d7da"),
            ], spacing=4),
            padding=10,
            bgcolor="#2c1a1a",
            border_radius=4,
            margin=5,
            width=sidebar_width - 30
        )
        
        # Quick actions - Full width buttons
        self.refs['btn_receive'] = ft.Ref[ft.ElevatedButton]()
        self.refs['btn_send'] = ft.Ref[ft.ElevatedButton]()
        self.refs['btn_sync'] = ft.Ref[ft.ElevatedButton]()
        self.refs['btn_new_wallet'] = ft.Ref[ft.ElevatedButton]()
        self.refs['btn_import'] = ft.Ref[ft.ElevatedButton]()
        self.refs['btn_lock'] = ft.Ref[ft.ElevatedButton]()
        
        # Button style for consistent full width buttons
        button_style = ft.ButtonStyle(
            color="#ffffff",
            bgcolor="#dc3545",
            padding=ft.padding.symmetric(horizontal=16, vertical=6),
            shape=ft.RoundedRectangleBorder(radius=2)
        )
        
        quick_actions = ft.Container(
            content=ft.Column([
                ft.Text("Quick Actions", size=12, color="#f8d7da"),
                ft.ElevatedButton(
                    "📥 Receive",
                    ref=self.refs['btn_receive'],
                    on_click=lambda _: self.show_receive_dialog(),
                    style=button_style,
                    height=32
                ),
                ft.ElevatedButton(
                    "📤 Send",
                    ref=self.refs['btn_send'],
                    on_click=lambda _: self.show_send_dialog(),
                    style=button_style,
                    height=32
                ),
                ft.ElevatedButton(
                    "🔄 Sync Now",
                    ref=self.refs['btn_sync'],
                    on_click=lambda _: self.manual_sync(),
                    style=button_style,
                    height=32
                ),
                ft.ElevatedButton(
                    "🆕 New Wallet",
                    ref=self.refs['btn_new_wallet'],
                    on_click=lambda _: self.show_create_wallet_dialog(),
                    style=button_style,
                    height=32
                ),
                ft.ElevatedButton(
                    "📁 Import Wallet",
                    ref=self.refs['btn_import'],
                    on_click=lambda _: self.show_import_dialog(),
                    style=button_style,
                    height=32
                ),
                ft.ElevatedButton(
                    "🔒 Lock Wallet",
                    ref=self.refs['btn_lock'],
                    on_click=lambda _: self.lock_wallet(),
                    style=ft.ButtonStyle(
                        color="#ffffff",
                        bgcolor="#6c757d",
                        padding=ft.padding.symmetric(horizontal=16, vertical=10),
                        shape=ft.RoundedRectangleBorder(radius=3)
                    ),
                    height=32
                ),
            ], spacing=8),
            padding=10,
            bgcolor="#2c1a1a",
            border_radius=2,
            margin=5,
            width=sidebar_width - 30
        )
        
        # Network status
        self.refs['lbl_connection'] = ft.Ref[ft.Text]()
        self.refs['lbl_sync_status'] = ft.Ref[ft.Text]()
        self.refs['progress_sync'] = ft.Ref[ft.ProgressBar]()
        
        network_status = ft.Container(
            content=ft.Column([
                ft.Text("🌐 Network Status", size=14, color="#f8d7da"),
                ft.Text("Status: 🔴 Disconnected", ref=self.refs['lbl_connection'], size=12, color="#f8d7da"),
                ft.Text("Last Sync: --", ref=self.refs['lbl_sync_status'], size=10, color="#f8d7da"),
                ft.ProgressBar(
                    ref=self.refs['progress_sync'],
                    visible=False,
                    color="#dc3545",
                    bgcolor="#5c2e2e"
                )
            ], spacing=6),
            padding=10,
            bgcolor="#2c1a1a",
            border_radius=4,
            margin=5,
            width=sidebar_width - 30
        )
        
        # App icon at bottom
        app_icon = ft.Container(
            content=ft.Row([
                ft.Container(
                    content=ft.Image(
                        src="./wallet_icon.png",
                        width=64,
                        height=64,
                        fit=ft.ImageFit.CONTAIN,
                        color="#dc3545",
                        color_blend_mode=ft.BlendMode.SRC_IN,
                        error_content=ft.Text("🔴", size=24)
                    ),
                    padding=10,
                    bgcolor="#00000000",
                    border_radius=4,
                )
            ], alignment=ft.MainAxisAlignment.CENTER),
            padding=10,
            margin=5,
            width=sidebar_width - 30
        )
        
        # Sidebar layout with menu
        sidebar_content = ft.Column([
            ft.Container(
                content=ft.Row([
                    ft.PopupMenuButton(
                        content=ft.Text("☰", color="#f8d7da", size=14),
                        tooltip="System Menu",
                        items=[
                            ft.PopupMenuItem(text="Lock Wallet", on_click=lambda _: self.lock_wallet()),
                            ft.PopupMenuItem(text="Save Wallet", on_click=lambda _: self.manual_save_wallet()),
                            ft.PopupMenuItem(),
                            ft.PopupMenuItem(text="Restore", on_click=lambda _: self.restore_from_tray() if self.minimized_to_tray else None),
                            ft.PopupMenuItem(text="Minimize to Tray", on_click=lambda _: self.minimize_to_tray()),
                            ft.PopupMenuItem(),
                            ft.PopupMenuItem(text="Start Auto-Sync", on_click=lambda _: self.wallet_core.start_auto_scan()),
                            ft.PopupMenuItem(text="Stop Auto-Sync", on_click=lambda _: self.wallet_core.stop_auto_scan()),
                            ft.PopupMenuItem(),
                            ft.PopupMenuItem(text="About", on_click=lambda _: self.show_about_dialog()),
                            ft.PopupMenuItem(text="Exit", on_click=lambda _: self.page.window.close()),
                        ]
                    ),
                    ft.Container(
                        content=ft.Image(
                            src="./wallet_icon.png",
                            width=32,
                            height=32,
                            fit=ft.ImageFit.CONTAIN,
                            color="#dc3545",
                            color_blend_mode=ft.BlendMode.SRC_IN,
                            error_content=ft.Text("🔴", size=16)
                        ),
                        margin=ft.margin.only(right=8),
                    ),
                    ft.Text("Luna Wallet", size=24, color="#f8d7da"),
                ]),
                width=sidebar_width - 30
            ),
            ft.Divider(height=1, color="#5c2e2e"),
            wallet_status,
            ft.Divider(height=1, color="#5c2e2e"),
            quick_actions,
            network_status,
            ft.Container(expand=True),  # Spacer
            app_icon
        ], spacing=10, horizontal_alignment=ft.CrossAxisAlignment.CENTER)
        
        return ft.Container(
            content=sidebar_content,
            width=sidebar_width,
            padding=15,
            bgcolor="#1a0f0f"
        )
        
    def create_main_content(self):
        """Create the main content area with tabs"""
        # Transactions tab
        self.refs['transactions_table'] = ft.Ref[ft.DataTable]()
        transactions_tab = self.create_transactions_tab()
        
        # Wallets tab
        self.refs['wallets_table'] = ft.Ref[ft.DataTable]()
        wallets_tab = self.create_wallets_tab()
        
        # Log tab
        self.refs['log_output'] = ft.Ref[ft.Column]()
        log_tab = self.create_log_tab()
        
        # Tabs
        tabs = ft.Tabs(
            selected_index=0,
            on_change=self.on_tab_change,
            tabs=[
                ft.Tab(
                    text="📊 Transactions",
                    content=transactions_tab
                ),
                ft.Tab(
                    text="👛 Wallets", 
                    content=wallets_tab
                ),
                ft.Tab(
                    text="📋 Log",
                    content=log_tab
                ),
            ],
            expand=True
        )
        
        return ft.Container(
            content=tabs,
            expand=True,
            padding=10,
            bgcolor="#2c1a1a"
        )
        
    def create_transactions_tab(self):
        """Create transactions history tab"""
        # Create data table
        data_table = ft.DataTable(
            ref=self.refs['transactions_table'],
            columns=[
                ft.DataColumn(ft.Text("Date", color="#f8d7da")),
                ft.DataColumn(ft.Text("Type", color="#f8d7da")),
                ft.DataColumn(ft.Text("From/To", color="#f8d7da")),
                ft.DataColumn(ft.Text("Amount", color="#f8d7da")),
                ft.DataColumn(ft.Text("Status", color="#f8d7da")),
                ft.DataColumn(ft.Text("Memo", color="#f8d7da")),
            ],
            rows=[],
            vertical_lines=ft.BorderSide(1, "#5c2e2e"),
            horizontal_lines=ft.BorderSide(1, "#5c2e2e"),
            bgcolor="#1a0f0f",
        )
        
        return ft.Container(
            content=ft.Column([
                ft.Text("Transaction History", size=16, color="#f8d7da"),
                ft.Container(
                    content=ft.ListView(
                        [data_table],
                        expand=True
                    ),
                    expand=True,
                    border=ft.border.all(1, "#5c2e2e"),
                    border_radius=3
                )
            ], expand=True),
            padding=10
        )
        
    def create_wallets_tab(self):
        """Create wallets management tab"""
        # Create data table
        data_table = ft.DataTable(
            ref=self.refs['wallets_table'],
            columns=[
                ft.DataColumn(ft.Text("Name", color="#f8d7da")),
                ft.DataColumn(ft.Text("Address", color="#f8d7da")),
                ft.DataColumn(ft.Text("Balance", color="#f8d7da")),
                ft.DataColumn(ft.Text("Transactions", color="#f8d7da")),
                ft.DataColumn(ft.Text("Actions", color="#f8d7da")),
            ],
            rows=[],
            vertical_lines=ft.BorderSide(1, "#5c2e2e"),
            horizontal_lines=ft.BorderSide(1, "#5c2e2e"),
            bgcolor="#1a0f0f",
        )
        
        # Action buttons - full width with reduced corners
        action_button_style = ft.ButtonStyle(
            color="#ffffff",
            bgcolor="#dc3545",
            padding=ft.padding.symmetric(horizontal=16, vertical=6),
            shape=ft.RoundedRectangleBorder(radius=3)
        )
        
        action_buttons = ft.Row([
            ft.ElevatedButton(
                "🔑 Export Private Key",
                on_click=lambda _: self.export_private_key(),
                style=action_button_style,
                height=32
            ),
            ft.ElevatedButton(
                "🔄 Refresh",
                on_click=lambda _: self.refresh_wallets(),
                style=action_button_style,
                height=32
            ),
            ft.ElevatedButton(
                "🔒 Lock Wallet",
                on_click=lambda _: self.lock_wallet(),
                style=ft.ButtonStyle(
                    color="#ffffff",
                    bgcolor="#6c757d",
                    padding=ft.padding.symmetric(horizontal=16, vertical=10),
                    shape=ft.RoundedRectangleBorder(radius=3)
                ),
                height=32
            ),
        ])
        
        return ft.Container(
            content=ft.Column([
                ft.Text("Wallet Management", size=16, color="#f8d7da"),
                action_buttons,
                ft.Container(
                    content=ft.ListView(
                        [data_table],
                        expand=True
                    ),
                    expand=True,
                    border=ft.border.all(1, "#5c2e2e"),
                    border_radius=3
                )
            ], expand=True),
            padding=10
        )
        
    def create_log_tab(self):
        """Create log tab"""
        self.refs['log_output'] = ft.Ref[ft.Column]()
        
        # Clear log button - full width with reduced corners
        clear_button = ft.ElevatedButton(
            "Clear Log",
            on_click=lambda _: self.clear_log(),
            style=ft.ButtonStyle(
                color="#ffffff",
                bgcolor="#dc3545",
                padding=ft.padding.symmetric(horizontal=16, vertical=10),
                shape=ft.RoundedRectangleBorder(radius=3)
            ),
            height=38
        )
        
        # Log content
        log_content = ft.Container(
            content=ft.Column([], ref=self.refs['log_output']),
            expand=True,
            border=ft.border.all(1, "#5c2e2e"),
            border_radius=3,
            padding=10,
            bgcolor="#1a0f0f"
        )
        
        return ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Text("Application Log", size=16, color="#f8d7da"),
                    clear_button
                ]),
                ft.Container(
                    content=ft.ListView([log_content], expand=True),
                    expand=True
                )
            ], expand=True),
            padding=10
        )
        
    def on_tab_change(self, e):
        """Handle tab changes"""
        self.current_tab_index = e.control.selected_index
        if self.current_tab_index == 0:  # Transactions
            self.update_transaction_history()
        elif self.current_tab_index == 1:  # Wallets
            self.update_wallets_list()
            
    def on_window_event(self, e):
        """Handle window events"""
        if e.data == "close":
            self.minimize_to_tray()
            return False
        elif e.data == "resize":
            self.on_window_resize(e)
        return True
        
    def minimize_to_tray(self):
        """Minimize to system tray"""
        self.minimized_to_tray = True
        self.page.window.minimized = True
        self.page.window.visible = False
        self.page.update()
        self.show_snack_bar("Luna Wallet minimized to system tray")
        
    def restore_from_tray(self):
        """Restore from system tray"""
        self.minimized_to_tray = False
        self.page.window.visible = True
        self.page.window.minimized = False
        self.page.update()
        
    def show_snack_bar(self, message: str):
        """Show snack bar message"""
        snack_bar = ft.SnackBar(
            content=ft.Text(message),
            shape=ft.RoundedRectangleBorder(radius=3)
        )
        self.page.overlay.append(snack_bar)
        snack_bar.open = True
        self.page.update()
        # Remove after delay
        def remove_snack():
            time.sleep(3)
            self.page.overlay.remove(snack_bar)
            self.page.update()
        threading.Thread(target=remove_snack, daemon=True).start()
        
    def update_balance_display(self):
        """Update balance display in sidebar"""
        if not self.wallet_core.is_unlocked or not self.wallet_core.wallets:
            # No wallet loaded
            self.refs['lbl_wallet_name'].current.value = "Name: No wallet loaded"
            self.refs['lbl_address'].current.value = "Address: --"
            self.refs['lbl_balance'].current.value = "Balance: 0.000000 LUN"
            self.refs['lbl_available'].current.value = "Available: 0.000000 LUN"
            self.refs['lbl_pending'].current.value = "Pending: 0.000000 LUN"
            self.refs['lbl_transactions'].current.value = "Transactions: 0"
        else:
            # Show selected wallet info
            if self.selected_wallet_index < len(self.wallet_core.wallets):
                wallet = self.wallet_core.wallets[self.selected_wallet_index]
                self.refs['lbl_wallet_name'].current.value = f"Name: {wallet['label']}"
                self.refs['lbl_address'].current.value = f"Address: {wallet['address'][:20]}..."
                self.refs['lbl_balance'].current.value = f"Balance: {wallet['balance']:.6f} LUN"
                self.refs['lbl_available'].current.value = f"Available: {wallet['balance'] - wallet['pending_send']:.6f} LUN"
                self.refs['lbl_pending'].current.value = f"Pending: {wallet['pending_send']:.6f} LUN"
                self.refs['lbl_transactions'].current.value = f"Transactions: {len(wallet['transactions'])}"
                
                # Update window title with balance
                self.page.title = f"🔴 Luna Wallet - {wallet['balance']:.2f} LUN"
        
        # Update UI
        for ref in [self.refs['lbl_wallet_name'], self.refs['lbl_address'], self.refs['lbl_balance'],
                   self.refs['lbl_available'], self.refs['lbl_pending'], self.refs['lbl_transactions']]:
            if ref.current:
                ref.current.update()
                
        self.page.update()
        
    def update_transaction_history(self):
        """Update transaction history table"""
        if not self.wallet_core.is_unlocked:
            return
            
        transactions = self.wallet_core.get_transaction_history()
        table = self.refs['transactions_table'].current
        if not table:
            return
            
        table.rows = []
        
        for tx in transactions[:50]:  # Show last 50 transactions
            # Date
            date_str = datetime.fromtimestamp(tx.get('timestamp', 0)).strftime("%Y-%m-%d %H:%M")
            
            # Type
            tx_type = tx.get('type', 'transfer')
            type_icon = "💰" if tx_type == "reward" else "🔄"
            
            # From/To
            from_addr = tx.get('from', 'Network')
            to_addr = tx.get('to', 'Unknown')
            direction = f"← {to_addr}" if from_addr == "network" else f"{from_addr} → {to_addr}"
            
            # Amount
            amount = tx.get('amount', 0)
            amount_color = "#00ff00" if from_addr == "network" or to_addr in [w['address'] for w in self.wallet_core.wallets] else "#ff0000"
            
            # Status
            status = tx.get('status', 'unknown')
            status_icon = "✅" if status == "confirmed" else "⏳" if status == "pending" else "❌"
            
            # Memo
            memo = tx.get('memo', '')
            
            table.rows.append(
                ft.DataRow(cells=[
                    ft.DataCell(ft.Text(date_str, size=11, color="#f8d7da")),
                    ft.DataCell(ft.Text(f"{type_icon} {tx_type}", size=11, color="#f8d7da")),
                    ft.DataCell(ft.Text(direction, size=11, color="#f8d7da")),
                    ft.DataCell(ft.Text(f"{amount:.6f} LUN", size=11, color=amount_color)),
                    ft.DataCell(ft.Text(f"{status_icon} {status}", size=11, color="#f8d7da")),
                    ft.DataCell(ft.Text(memo, size=11, color="#f8d7da")),
                ])
            )
            
        table.update()
        
    def update_wallets_list(self):
        """Update wallets table"""
        if not self.wallet_core.is_unlocked:
            return
            
        table = self.refs['wallets_table'].current
        if not table:
            return
            
        table.rows = []
        
        for i, wallet in enumerate(self.wallet_core.wallets):
            select_button = ft.ElevatedButton(
                "Select",
                on_click=lambda e, idx=i: self.select_wallet(idx),
                style=ft.ButtonStyle(
                    color="#ffffff",
                    bgcolor="#28a745" if i == self.selected_wallet_index else "#dc3545",
                    padding=ft.padding.symmetric(horizontal=8, vertical=4),
                    shape=ft.RoundedRectangleBorder(radius=3)
                ),
                height=30
            )
            
            table.rows.append(
                ft.DataRow(cells=[
                    ft.DataCell(ft.Text(wallet['label'], size=11, color="#f8d7da")),
                    ft.DataCell(ft.Text(wallet['address'], size=11, color="#f8d7da")),
                    ft.DataCell(ft.Text(f"{wallet['balance']:.6f} LUN", size=11, color="#f8d7da")),
                    ft.DataCell(ft.Text(str(len(wallet['transactions'])), size=11, color="#f8d7da")),
                    ft.DataCell(select_button),
                ])
            )
            
        table.update()
        
    def select_wallet(self, wallet_index):
        """Select a specific wallet for operations"""
        if wallet_index < len(self.wallet_core.wallets):
            self.selected_wallet_index = wallet_index
            self.update_balance_display()
            self.update_wallets_list()
            self.show_snack_bar(f"Selected wallet: {self.wallet_core.wallets[wallet_index]['label']}")
            self.auto_save_wallet()
        
    def add_log_message(self, message, msg_type="info"):
        """Add message to log"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        color = {
            "error": "#dc3545",
            "success": "#28a745",
            "warning": "#ffc107",
            "info": "#17a2b8"
        }.get(msg_type, "#f8d7da")
        
        log_entry = ft.Text(f"[{timestamp}] {message}", color=color, size=11)
        
        log_column = self.refs['log_output'].current
        if log_column:
            log_column.controls.append(log_entry)
            # Keep only last 100 messages
            if len(log_column.controls) > 100:
                log_column.controls.pop(0)
            log_column.update()
            
    def clear_log(self):
        """Clear log output"""
        log_column = self.refs['log_output'].current
        if log_column:
            log_column.controls.clear()
            log_column.update()
            
    def show_receive_dialog(self):
        """Show receive dialog with wallet selection and QR code"""
        if self.is_locked or not self.wallet_core.is_unlocked or not self.wallet_core.wallets:
            self.show_snack_bar("Please unlock your wallet first")
            return
        
        # Create a sliding overlay container
        overlay_container = ft.Container(
            width=self.page.width - 280,  # Full width minus sidebar
            height=self.page.height,
            left=280,  # Start from sidebar edge
            top=0,
            bgcolor="#1a0f0f",
            border=ft.border.only(left=ft.BorderSide(4, "#8B4513")),
            animate_position=ft.Animation(300, "easeOut"),
            padding=20,
        )
        
        # Header with red icon and text
        header = ft.Row([
            ft.Container(
                content=ft.Image(
                    src="./wallet_icon.png",
                    width=32,
                    height=32,
                    fit=ft.ImageFit.CONTAIN,
                    color="#dc3545",
                    color_blend_mode=ft.BlendMode.SRC_IN,
                    error_content=ft.Text("🔴", size=20)
                ),
                margin=ft.margin.only(right=12),
            ),
            ft.Text("📥 Receive Luna", size=24, color="#dc3545", weight="bold"),
        ], alignment=ft.MainAxisAlignment.START)
        
        # Wallet selection dropdown
        wallet_options = []
        for i, wallet in enumerate(self.wallet_core.wallets):
            wallet_options.append(
                ft.dropdown.Option(
                    key=str(i),
                    text=f"{wallet['label']} ({wallet['address'][:16]}...)"
                )
            )
        
        wallet_dropdown = ft.Dropdown(
            label="Select Wallet to Receive",
            options=wallet_options,
            value=str(self.selected_wallet_index),
            width=400,
            color="#f8d7da",
            border_color="#5c2e2e"
        )
        
        # Create controls that will be updated
        address_display = ft.Text("", size=12, color="#f8d7da", selectable=True)
        qr_content = ft.Container()
        
        def update_qr_code(e):
            selected_index = int(wallet_dropdown.value)
            if selected_index < len(self.wallet_core.wallets):
                address = self.wallet_core.wallets[selected_index]['address']
                address_display.value = address
                
                # Generate QR code
                try:
                    import qrcode
                    qr = qrcode.QRCode(version=1, box_size=8, border=4)
                    qr.add_data(address)
                    qr.make(fit=True)
                    
                    qr_img = qr.make_image(fill_color="red", back_color="white")
                    
                    # Convert to bytes
                    buffer = io.BytesIO()
                    qr_img.save(buffer, format="PNG")
                    buffer.seek(0)
                    
                    qr_content.content = ft.Image(
                        src_base64=base64.b64encode(buffer.read()).decode(),
                        width=200,
                        height=200
                    )
                except ImportError:
                    qr_content.content = ft.Container(
                        content=ft.Column([
                            ft.Text("QR Code requires:", size=12, color="#f8d7da"),
                            ft.Text("pip install qrcode", size=10, color="#f8d7da"),
                            ft.Text("pip install pillow", size=10, color="#f8d7da"),
                        ]),
                        padding=20,
                        alignment=ft.alignment.center
                    )
                
                # Update the page to reflect changes
                self.page.update()
        
        # Initial update
        wallet_dropdown.on_change = update_qr_code
        
        def close_dialog(e):
            # Animate out
            overlay_container.left = self.page.width
            self.page.update()
            time.sleep(0.3)  # Wait for animation
            self.page.overlay.remove(overlay_container)
            self.page.update()
        
        # Create dialog content - make sure address_display and qr_content are added to the layout
        dialog_content = ft.Column([
            header,
            ft.Container(height=20),
            wallet_dropdown,
            ft.Container(height=15),
            ft.Text("Wallet Address:", size=16, color="#f8d7da"),
            ft.Container(
                content=address_display,  # Add address_display to the container
                padding=15,
                bgcolor="#2c1a1a",
                border_radius=8,
                width=500
            ),
            ft.Container(height=20),
            ft.Container(
                content=qr_content,  # Add qr_content to the container
                padding=20,
                alignment=ft.alignment.center
            ),
            ft.Container(height=20),
            ft.Row([
                ft.ElevatedButton(
                    "📋 Copy Address",
                    on_click=lambda _: self.copy_to_clipboard(address_display.value),
                    style=ft.ButtonStyle(
                        color="#ffffff",
                        bgcolor="#dc3545",
                        padding=ft.padding.symmetric(horizontal=20, vertical=12),
                        shape=ft.RoundedRectangleBorder(radius=4)
                    )
                ),
                ft.ElevatedButton(
                    "Close",
                    on_click=close_dialog,
                    style=ft.ButtonStyle(
                        color="#ffffff",
                        bgcolor="#6c757d",
                        padding=ft.padding.symmetric(horizontal=20, vertical=12),
                        shape=ft.RoundedRectangleBorder(radius=4)
                    )
                )
            ], alignment=ft.MainAxisAlignment.END)
        ], scroll=ft.ScrollMode.ADAPTIVE)
        
        # Add dialog to overlay container
        overlay_container.content = dialog_content
        
        # Add to page overlay and animate in
        self.page.overlay.append(overlay_container)
        self.page.update()
        
        # Do initial QR code update after everything is added to the page
        update_qr_code(None)
        
    def show_send_dialog(self):
        """Show send transaction dialog with wallet selection"""
        if self.is_locked or not self.wallet_core.is_unlocked or not self.wallet_core.wallets:
            self.show_snack_bar("Please unlock your wallet first")
            return
            
        # Create a sliding overlay container
        overlay_container = ft.Container(
            width=self.page.width - 280,
            height=self.page.height,
            left=280,
            top=0,
            bgcolor="#1a0f0f",
            border=ft.border.only(left=ft.BorderSide(4, "#8B4513")),
            animate_position=ft.Animation(300, "easeOut"),
            padding=20,
        )
        
        # Header with red icon and text
        header = ft.Row([
            ft.Container(
                content=ft.Image(
                    src="./wallet_icon.png",
                    width=32,
                    height=32,
                    fit=ft.ImageFit.CONTAIN,
                    color="#dc3545",
                    color_blend_mode=ft.BlendMode.SRC_IN,
                    error_content=ft.Text("🔴", size=20)
                ),
                margin=ft.margin.only(right=12),
            ),
            ft.Text("📤 Send Luna", size=24, color="#dc3545", weight="bold"),
        ], alignment=ft.MainAxisAlignment.START)
        
        # Wallet selection dropdown
        wallet_options = []
        for i, wallet in enumerate(self.wallet_core.wallets):
            balance = wallet['balance'] - wallet['pending_send']
            wallet_options.append(
                ft.dropdown.Option(
                    key=str(i),
                    text=f"{wallet['label']} ({balance:.6f} LUN)"
                )
            )
        
        wallet_dropdown = ft.Dropdown(
            label="Select Wallet to Send From",
            options=wallet_options,
            value=str(self.selected_wallet_index),
            width=500,
            color="#f8d7da",
            border_color="#5c2e2e"
        )
        
        # Form fields
        to_address_field = ft.TextField(
            label="To Address",
            hint_text="LUN_... or Luna address",
            width=500,
            color="#f8d7da",
            border_color="#5c2e2e"
        )
        
        amount_field = ft.TextField(
            label="Amount (LUN)",
            hint_text="0.000000",
            width=500,
            color="#f8d7da",
            border_color="#5c2e2e"
        )
        
        memo_field = ft.TextField(
            label="Memo (Optional)",
            hint_text="Message for recipient",
            width=500,
            color="#f8d7da",
            border_color="#5c2e2e"
        )
        
        password_field = ft.TextField(
            label="Wallet Password (Optional)",
            hint_text="For transaction signing",
            password=True,
            can_reveal_password=True,
            width=500,
            color="#f8d7da",
            border_color="#5c2e2e"
        )
        
        def send_transaction(e):
            to_address = to_address_field.value
            amount_text = amount_field.value
            memo = memo_field.value
            password = password_field.value
            
            if not to_address:
                self.show_snack_bar("Please enter a recipient address")
                return
                
            try:
                amount = float(amount_text)
                if amount <= 0:
                    raise ValueError("Amount must be positive")
            except ValueError:
                self.show_snack_bar("Please enter a valid amount")
                return
            
            # Close dialog
            close_dialog(None)
            
            # Get selected wallet
            selected_index = int(wallet_dropdown.value)
            
            # Show confirmation
            def confirm_send():
                # Perform send in background thread
                def send_thread():
                    # Temporarily set the selected wallet as active for sending
                    original_index = self.selected_wallet_index
                    self.selected_wallet_index = selected_index
                    
                    success = self.wallet_core.send_transaction(to_address, amount, memo, password)
                    
                    # Restore original selection
                    self.selected_wallet_index = original_index
                    
                    if success:
                        self.add_log_message(f"Sent {amount} LUN to {to_address}", "success")
                        self.update_balance_display()
                        self.update_transaction_history()
                        self.update_wallets_list()
                        self.auto_save_wallet()
                    else:
                        self.add_log_message("Failed to send transaction", "error")
                        
                threading.Thread(target=send_thread, daemon=True).start()
                
            # Show confirmation dialog
            selected_wallet = self.wallet_core.wallets[selected_index]
            self.show_confirmation_dialog(
                f"Send {amount:.6f} LUN from {selected_wallet['label']} to:\n{to_address}\n\nMemo: {memo}",
                confirm_send
            )
        
        def close_dialog(e):
            # Animate out
            overlay_container.left = self.page.width
            self.page.update()
            time.sleep(0.3)
            self.page.overlay.remove(overlay_container)
            self.page.update()
        
        # Create dialog content
        dialog_content = ft.Column([
            header,
            ft.Container(height=20),
            wallet_dropdown,
            ft.Container(height=15),
            to_address_field,
            ft.Container(height=10),
            amount_field,
            ft.Container(height=10),
            memo_field,
            ft.Container(height=10),
            password_field,
            ft.Container(height=30),
            ft.Row([
                ft.ElevatedButton(
                    "Send",
                    on_click=send_transaction,
                    style=ft.ButtonStyle(
                        color="#ffffff",
                        bgcolor="#dc3545",
                        padding=ft.padding.symmetric(horizontal=20, vertical=12),
                        shape=ft.RoundedRectangleBorder(radius=4)
                    )
                ),
                ft.ElevatedButton(
                    "Close",
                    on_click=close_dialog,
                    style=ft.ButtonStyle(
                        color="#ffffff",
                        bgcolor="#6c757d",
                        padding=ft.padding.symmetric(horizontal=20, vertical=12),
                        shape=ft.RoundedRectangleBorder(radius=4)
                    )
                )
            ], alignment=ft.MainAxisAlignment.END)
        ], scroll=ft.ScrollMode.ADAPTIVE)
        
        # Add dialog to overlay container
        overlay_container.content = dialog_content
        
        # Add to page overlay and animate in
        self.page.overlay.append(overlay_container)
        self.page.update()
        
    def show_confirmation_dialog(self, message, confirm_callback):
        """Show confirmation dialog using sliding overlay"""
        overlay_container = ft.Container(
            width=self.page.width - 280,
            height=self.page.height,
            left=280,
            top=0,
            bgcolor="#1a0f0f",
            border=ft.border.only(left=ft.BorderSide(4, "#8B4513")),
            animate_position=ft.Animation(300, "easeOut"),
            padding=20,
        )
        
        def confirm(e):
            close_dialog(None)
            confirm_callback()
        
        def close_dialog(e):
            overlay_container.left = self.page.width
            self.page.update()
            time.sleep(0.3)
            self.page.overlay.remove(overlay_container)
            self.page.update()
        
        dialog_content = ft.Column([
            ft.Row([
                ft.Container(
                    content=ft.Image(
                        src="./wallet_icon.png",
                        width=32,
                        height=32,
                        fit=ft.ImageFit.CONTAIN,
                        color="#dc3545",
                        color_blend_mode=ft.BlendMode.SRC_IN,
                        error_content=ft.Text("🔴", size=20)
                    ),
                    margin=ft.margin.only(right=12),
                ),
                ft.Text("Confirm Send", size=24, color="#dc3545", weight="bold"),
            ], alignment=ft.MainAxisAlignment.START),
            ft.Container(height=30),
            ft.Text(message, size=14, color="#f8d7da"),
            ft.Container(height=40),
            ft.Row([
                ft.ElevatedButton(
                    "Yes",
                    on_click=confirm,
                    style=ft.ButtonStyle(
                        color="#ffffff",
                        bgcolor="#dc3545",
                        padding=ft.padding.symmetric(horizontal=20, vertical=12),
                        shape=ft.RoundedRectangleBorder(radius=4)
                    )
                ),
                ft.ElevatedButton(
                    "No",
                    on_click=close_dialog,
                    style=ft.ButtonStyle(
                        color="#ffffff",
                        bgcolor="#6c757d",
                        padding=ft.padding.symmetric(horizontal=20, vertical=12),
                        shape=ft.RoundedRectangleBorder(radius=4)
                    )
                )
            ], alignment=ft.MainAxisAlignment.END)
        ], scroll=ft.ScrollMode.ADAPTIVE)
        
        overlay_container.content = dialog_content
        self.page.overlay.append(overlay_container)
        self.page.update()
            
    def show_create_wallet_dialog(self):
        """Show create wallet dialog using sliding overlay"""
        # Create a sliding overlay container
        overlay_container = ft.Container(
            width=self.page.width - 280,
            height=self.page.height,
            left=280,
            top=0,
            bgcolor="#1a0f0f",
            border=ft.border.only(left=ft.BorderSide(4, "#8B4513")),
            animate_position=ft.Animation(300, "easeOut"),
            padding=20,
        )
        
        # Header with red icon and text
        header = ft.Row([
            ft.Container(
                content=ft.Image(
                    src="./wallet_icon.png",
                    width=32,
                    height=32,
                    fit=ft.ImageFit.CONTAIN,
                    color="#dc3545",
                    color_blend_mode=ft.BlendMode.SRC_IN,
                    error_content=ft.Text("🔴", size=20)
                ),
                margin=ft.margin.only(right=12),
            ),
            ft.Text("🆕 Create New Wallet", size=24, color="#dc3545", weight="bold"),
        ], alignment=ft.MainAxisAlignment.START)
        
        # Create the dialog content
        label_field = ft.TextField(
            label="Wallet Name",
            hint_text="My Wallet", 
            value="My Wallet",
            width=500,
            color="#f8d7da",
            border_color="#5c2e2e"
        )
        
        password_field = ft.TextField(
            label="Password",
            hint_text="Encrypt wallet with password",
            password=True,
            can_reveal_password=True,
            width=500,
            color="#f8d7da",
            border_color="#5c2e2e"
        )
        
        confirm_field = ft.TextField(
            label="Confirm Password", 
            hint_text="Repeat password",
            password=True,
            can_reveal_password=True,
            width=500,
            color="#f8d7da",
            border_color="#5c2e2e"
        )
        
        def create_wallet(e):
            label = label_field.value
            password = password_field.value
            confirm_password = confirm_field.value
            
            if password != confirm_password:
                self.show_snack_bar("Passwords do not match")
                return
                
            if not label or not label.strip():
                label = "My Wallet"
            
            # Close dialog
            close_dialog(None)
            
            # Create wallet in background thread
            def create_thread():
                try:
                    self.debug_dialog(f"Creating wallet with label: {label}")
                    
                    # Check if this is the first wallet or additional wallet
                    if not self.wallet_core.is_unlocked and not self.wallet_core.wallets:
                        self.debug_dialog("Creating first wallet with direct method")
                        
                        # Create wallet directly first
                        address = self.wallet_core.create_wallet(label)
                        if address:
                            self.debug_dialog(f"Wallet created: {address}")
                            
                            # Manually set the wallet as unlocked and save it
                            self.wallet_core.is_unlocked = True
                            self.wallet_core.wallet_password = password
                            
                            # Try to save the wallet
                            save_success = self.wallet_core.save_wallet(password)
                            self.debug_dialog(f"Direct save result: {save_success}")
                            
                            if save_success:
                                # Now try to unlock to verify everything works
                                unlock_success = self.wallet_core.unlock_wallet(password)
                                self.debug_dialog(f"Verify unlock: {unlock_success}")
                                
                                if unlock_success:
                                    success = True
                                    self.debug_dialog("Wallet creation and unlock successful!")
                                else:
                                    # Even if unlock fails, if we have wallets loaded, consider it success
                                    if self.wallet_core.wallets:
                                        success = True
                                        self.debug_dialog("Wallet created but unlock verification failed - wallets are loaded")
                                    else:
                                        success = False
                            else:
                                success = False
                                self.debug_dialog("Failed to save wallet")
                        else:
                            success = False
                            self.debug_dialog("Failed to create wallet structure")
                    else:
                        self.debug_dialog("Creating additional wallet")
                        address = self.wallet_core.create_wallet(label)
                        success = address is not None
                        self.debug_dialog(f"Create additional wallet result: {success}")
                        
                        if success:
                            # Save the updated wallet list
                            save_success = self.wallet_core.save_wallet()
                            self.debug_dialog(f"Save additional wallet: {save_success}")
                    
                    # Update UI in main thread
                    def update_ui():
                        if success and self.wallet_core.wallets:
                            self.debug_dialog("Wallet created successfully")
                            self.add_log_message(f"Created wallet '{label}'", "success")
                            self.update_balance_display()
                            self.update_wallets_list()
                            self.auto_save_wallet()
                            self.show_snack_bar("Wallet created successfully!")
                            
                            # Show wallet info
                            if self.wallet_core.wallets:
                                wallet_address = self.wallet_core.wallets[-1]['address']  # Get the new wallet
                                self.add_log_message(f"Wallet address: {wallet_address}", "info")
                                
                            # Start auto-scan now that we have a wallet
                            self.wallet_core.start_auto_scan()
                        else:
                            self.debug_dialog(f"Wallet creation failed - wallets: {len(self.wallet_core.wallets) if self.wallet_core.wallets else 0}")
                            self.add_log_message("Failed to create wallet", "error")
                            self.show_snack_bar("Wallet creation failed")
                            
                    self.page.run_thread(update_ui)
                    
                except Exception as ex:
                    self.debug_dialog(f"Wallet creation error: {str(ex)}")
                    import traceback
                    self.debug_dialog(f"Traceback: {traceback.format_exc()}")
                    def show_error():
                        self.add_log_message(f"Creation error: {str(ex)}", "error")
                        self.show_snack_bar(f"Error: {str(ex)}")
                    self.page.run_thread(show_error)
            
            threading.Thread(target=create_thread, daemon=True).start()
        
        def close_dialog(e):
            # Animate out
            overlay_container.left = self.page.width
            self.page.update()
            time.sleep(0.3)
            self.page.overlay.remove(overlay_container)
            self.page.update()
        
        # Create dialog content
        dialog_content = ft.Column([
            header,
            ft.Container(height=20),
            label_field,
            ft.Container(height=10),
            password_field, 
            ft.Container(height=10),
            confirm_field,
            ft.Container(height=30),
            ft.Row([
                ft.ElevatedButton(
                    "Create",
                    on_click=create_wallet,
                    style=ft.ButtonStyle(
                        color="#ffffff",
                        bgcolor="#dc3545", 
                        padding=ft.padding.symmetric(horizontal=20, vertical=12),
                        shape=ft.RoundedRectangleBorder(radius=4)
                    )
                ),
                ft.ElevatedButton(
                    "Cancel",
                    on_click=close_dialog,
                    style=ft.ButtonStyle(
                        color="#ffffff",
                        bgcolor="#6c757d",
                        padding=ft.padding.symmetric(horizontal=20, vertical=12),
                        shape=ft.RoundedRectangleBorder(radius=4)
                    )
                )
            ], alignment=ft.MainAxisAlignment.END)
        ], scroll=ft.ScrollMode.ADAPTIVE)
        
        # Add dialog to overlay container
        overlay_container.content = dialog_content
        
        # Add to page overlay and animate in
        self.page.overlay.append(overlay_container)
        self.page.update()
        
    def show_import_dialog(self):
        """Show import wallet dialog using sliding overlay"""
        # Create a sliding overlay container
        overlay_container = ft.Container(
            width=self.page.width - 280,
            height=self.page.height,
            left=280,
            top=0,
            bgcolor="#1a0f0f",
            border=ft.border.only(left=ft.BorderSide(4, "#8B4513")),
            animate_position=ft.Animation(300, "easeOut"),
            padding=20,
        )
        
        # Header with red icon and text
        header = ft.Row([
            ft.Container(
                content=ft.Image(
                    src="./wallet_icon.png",
                    width=32,
                    height=32,
                    fit=ft.ImageFit.CONTAIN,
                    color="#dc3545",
                    color_blend_mode=ft.BlendMode.SRC_IN,
                    error_content=ft.Text("🔴", size=20)
                ),
                margin=ft.margin.only(right=12),
            ),
            ft.Text("📁 Import Wallet", size=24, color="#dc3545", weight="bold"),
        ], alignment=ft.MainAxisAlignment.START)
        
        # Form fields
        private_key_field = ft.TextField(
            label="Private Key (64 hex characters)",
            hint_text="Enter your 64-character private key",
            width=500,
            color="#f8d7da",
            border_color="#5c2e2e",
            multiline=True,
            min_lines=2,
            max_lines=3
        )
        
        label_field = ft.TextField(
            label="Wallet Name",
            hint_text="Imported Wallet",
            value="Imported Wallet",
            width=500,
            color="#f8d7da",
            border_color="#5c2e2e"
        )
        
        password_field = ft.TextField(
            label="Wallet Password (for encryption)",
            hint_text="Password to encrypt imported wallet",
            password=True,
            can_reveal_password=True,
            width=500,
            color="#f8d7da",
            border_color="#5c2e2e"
        )
        
        def import_wallet(e):
            private_key = private_key_field.value.strip()
            label = label_field.value
            password = password_field.value
            
            if not private_key:
                self.show_snack_bar("Please enter a private key")
                return
                
            # Validate private key format
            if len(private_key) != 64 or not all(c in '0123456789abcdefABCDEF' for c in private_key):
                self.show_snack_bar("Invalid private key format. Must be 64 hexadecimal characters.")
                return
                
            if not password:
                self.show_snack_bar("Please enter a password to encrypt the wallet")
                return
            
            # Close dialog
            close_dialog(None)
            
            # Import wallet in background thread
            def import_thread():
                try:
                    # If no wallet exists yet, we need to initialize first
                    if not self.wallet_core.is_unlocked:
                        # Create a temporary wallet structure
                        self.wallet_core.wallets = []
                        self.wallet_core.is_unlocked = True
                    
                    success = self.wallet_core.import_wallet(private_key, label)
                    
                    if success:
                        # Save the wallet with encryption
                        save_success = self.wallet_core.save_wallet(password)
                        
                        # Update UI in main thread
                        def update_ui():
                            if save_success:
                                self.is_locked = False
                                self.last_activity_time = time.time()
                                self.add_log_message(f"Imported wallet '{label}'", "success")
                                self.update_balance_display()
                                self.update_wallets_list()
                                self.update_transaction_history()
                                self.auto_save_wallet()
                                self.show_snack_bar("Wallet imported successfully!")
                                
                                # Start auto-scan now that we have a wallet
                                self.wallet_core.start_auto_scan()
                            else:
                                self.add_log_message("Wallet imported but failed to save", "warning")
                                self.show_snack_bar("Wallet imported but save failed - use Save Wallet from menu")
                                
                        self.page.run_thread(update_ui)
                    else:
                        def update_ui_fail():
                            self.add_log_message("Failed to import wallet - invalid private key or duplicate", "error")
                            self.show_snack_bar("Failed to import wallet - check private key")
                            
                        self.page.run_thread(update_ui_fail)
                        
                except Exception as ex:
                    def update_ui_error():
                        self.add_log_message(f"Import error: {str(ex)}", "error")
                        self.show_snack_bar(f"Import error: {str(ex)}")
                        
                    self.page.run_thread(update_ui_error)
            
            threading.Thread(target=import_thread, daemon=True).start()
        
        def close_dialog(e):
            # Animate out
            overlay_container.left = self.page.width
            self.page.update()
            time.sleep(0.3)
            self.page.overlay.remove(overlay_container)
            self.page.update()
        
        # Create dialog content
        dialog_content = ft.Column([
            header,
            ft.Container(height=20),
            ft.Text("Enter your 64-character private key:", size=14, color="#f8d7da"),
            private_key_field,
            ft.Container(height=10),
            label_field,
            ft.Container(height=10),
            password_field,
            ft.Container(height=30),
            ft.Row([
                ft.ElevatedButton(
                    "Import",
                    on_click=import_wallet,
                    style=ft.ButtonStyle(
                        color="#ffffff",
                        bgcolor="#dc3545",
                        padding=ft.padding.symmetric(horizontal=20, vertical=12),
                        shape=ft.RoundedRectangleBorder(radius=4)
                    )
                ),
                ft.ElevatedButton(
                    "Cancel",
                    on_click=close_dialog,
                    style=ft.ButtonStyle(
                        color="#ffffff",
                        bgcolor="#6c757d",
                        padding=ft.padding.symmetric(horizontal=20, vertical=12),
                        shape=ft.RoundedRectangleBorder(radius=4)
                    )
                )
            ], alignment=ft.MainAxisAlignment.END)
        ], scroll=ft.ScrollMode.ADAPTIVE)
        
        # Add dialog to overlay container
        overlay_container.content = dialog_content
        
        # Add to page overlay and animate in
        self.page.overlay.append(overlay_container)
        self.page.update()
        
    def show_unlock_dialog(self):
        """Show unlock wallet dialog using sliding overlay"""
        # Create a sliding overlay container
        overlay_container = ft.Container(
            width=self.page.width - 280,
            height=self.page.height,
            left=280,
            top=0,
            bgcolor="#1a0f0f",
            border=ft.border.only(left=ft.BorderSide(4, "#8B4513")),
            animate_position=ft.Animation(300, "easeOut"),
            padding=20,
        )
        
        # Header with red icon and text
        header = ft.Row([
            ft.Container(
                content=ft.Image(
                    src="./wallet_icon.png",
                    width=32,
                    height=32,
                    fit=ft.ImageFit.CONTAIN,
                    color="#dc3545",
                    color_blend_mode=ft.BlendMode.SRC_IN,
                    error_content=ft.Text("🔴", size=20)
                ),
                margin=ft.margin.only(right=12),
            ),
            ft.Text("🔓 Unlock Wallet", size=24, color="#dc3545", weight="bold"),
        ], alignment=ft.MainAxisAlignment.START)
        
        password_field = ft.TextField(
            label="Wallet Password",
            hint_text="Enter your wallet password",
            password=True,
            can_reveal_password=True,
            width=500,
            color="#f8d7da",
            border_color="#5c2e2e"
        )
        
        def unlock_wallet(e):
            password = password_field.value
            
            if not password:
                self.show_snack_bar("Please enter a password")
                return
            
            # Close dialog
            close_dialog(None)
            
            # Unlock in background thread
            def unlock_thread():
                success = self.wallet_core.unlock_wallet(password)
                
                def update_ui():
                    if success:
                        self.is_locked = False
                        self.last_activity_time = time.time()
                        self.add_log_message("Wallet unlocked successfully", "success")
                        self.update_balance_display()
                        self.update_wallets_list()
                        self.update_transaction_history()
                        self.show_snack_bar("Wallet unlocked!")
                        
                        # Start auto-scan now that we're unlocked
                        self.wallet_core.start_auto_scan()
                    else:
                        self.add_log_message("Failed to unlock wallet", "error")
                        self.show_snack_bar("Failed to unlock wallet - wrong password or no wallet file")
                        
                self.page.run_thread(update_ui)
            
            threading.Thread(target=unlock_thread, daemon=True).start()
        
        def close_dialog(e):
            # Animate out
            overlay_container.left = self.page.width
            self.page.update()
            time.sleep(0.3)
            self.page.overlay.remove(overlay_container)
            self.page.update()
        
        dialog_content = ft.Column([
            header,
            ft.Container(height=30),
            password_field,
            ft.Container(height=30),
            ft.Row([
                ft.ElevatedButton(
                    "Unlock",
                    on_click=unlock_wallet,
                    style=ft.ButtonStyle(
                        color="#ffffff",
                        bgcolor="#dc3545",
                        padding=ft.padding.symmetric(horizontal=20, vertical=12),
                        shape=ft.RoundedRectangleBorder(radius=4)
                    )
                ),
                ft.ElevatedButton(
                    "Cancel",
                    on_click=close_dialog,
                    style=ft.ButtonStyle(
                        color="#ffffff",
                        bgcolor="#6c757d",
                        padding=ft.padding.symmetric(horizontal=20, vertical=12),
                        shape=ft.RoundedRectangleBorder(radius=4)
                    )
                )
            ], alignment=ft.MainAxisAlignment.END)
        ], scroll=ft.ScrollMode.ADAPTIVE)
        
        overlay_container.content = dialog_content
        self.page.overlay.append(overlay_container)
        self.page.update()
        
    def export_private_key(self):
        """Export private key for selected wallet using sliding overlay"""
        if self.is_locked or not self.wallet_core.is_unlocked or not self.wallet_core.wallets:
            self.show_snack_bar("Please unlock your wallet first")
            return
            
        # Create a sliding overlay container
        overlay_container = ft.Container(
            width=self.page.width - 280,
            height=self.page.height,
            left=280,
            top=0,
            bgcolor="#1a0f0f",
            border=ft.border.only(left=ft.BorderSide(4, "#8B4513")),
            animate_position=ft.Animation(300, "easeOut"),
            padding=20,
        )
        
        # Header with red icon and text
        header = ft.Row([
            ft.Container(
                content=ft.Image(
                    src="./wallet_icon.png",
                    width=32,
                    height=32,
                    fit=ft.ImageFit.CONTAIN,
                    color="#dc3545",
                    color_blend_mode=ft.BlendMode.SRC_IN,
                    error_content=ft.Text("🔴", size=20)
                ),
                margin=ft.margin.only(right=12),
            ),
            ft.Text("🔑 Export Private Key", size=24, color="#dc3545", weight="bold"),
        ], alignment=ft.MainAxisAlignment.START)
        
        # Wallet selection dropdown
        wallet_options = []
        for i, wallet in enumerate(self.wallet_core.wallets):
            wallet_options.append(
                ft.dropdown.Option(
                    key=str(i),
                    text=f"{wallet['label']} ({wallet['address'][:16]}...)"
                )
            )
        
        wallet_dropdown = ft.Dropdown(
            label="Select Wallet to Export",
            options=wallet_options,
            value=str(self.selected_wallet_index),
            width=500,
            color="#f8d7da",
            border_color="#5c2e2e"
        )
        
        private_key_display = ft.Text("", size=12, color="#f8d7da", selectable=True)
        
        def update_private_key(e):
            selected_index = int(wallet_dropdown.value)
            if selected_index < len(self.wallet_core.wallets):
                private_key = self.wallet_core.wallets[selected_index]['private_key']
                private_key_display.value = private_key
                private_key_display.update()
        
        # Initial update
        wallet_dropdown.on_change = update_private_key
        update_private_key(None)
        
        def close_dialog(e):
            # Animate out
            overlay_container.left = self.page.width
            self.page.update()
            time.sleep(0.3)
            self.page.overlay.remove(overlay_container)
            self.page.update()
        
        # Create dialog content
        dialog_content = ft.Column([
            header,
            ft.Container(height=20),
            ft.Text("⚠️ WARNING: Never share your private key!", color="#ff0000", size=16, weight="bold"),
            ft.Text("Anyone with this key can access your funds!", color="#ff0000", size=14),
            ft.Container(height=20),
            wallet_dropdown,
            ft.Container(height=15),
            ft.Container(
                content=private_key_display,
                padding=15,
                bgcolor="#2c1a1a",
                border_radius=8,
                width=500
            ),
            ft.Container(height=30),
            ft.Row([
                ft.ElevatedButton(
                    "📋 Copy to Clipboard",
                    on_click=lambda _: self.copy_to_clipboard(private_key_display.value),
                    style=ft.ButtonStyle(
                        color="#ffffff",
                        bgcolor="#dc3545",
                        padding=ft.padding.symmetric(horizontal=20, vertical=12),
                        shape=ft.RoundedRectangleBorder(radius=4)
                    )
                ),
                ft.ElevatedButton(
                    "Close",
                    on_click=close_dialog,
                    style=ft.ButtonStyle(
                        color="#ffffff",
                        bgcolor="#6c757d",
                        padding=ft.padding.symmetric(horizontal=20, vertical=12),
                        shape=ft.RoundedRectangleBorder(radius=4)
                    )
                )
            ], alignment=ft.MainAxisAlignment.END)
        ], scroll=ft.ScrollMode.ADAPTIVE)
        
        # Add dialog to overlay container
        overlay_container.content = dialog_content
        
        # Add to page overlay and animate in
        self.page.overlay.append(overlay_container)
        self.page.update()
        
    def manual_sync(self):
        """Manual blockchain synchronization"""
        if self.is_locked or not self.wallet_core.is_unlocked:
            self.show_snack_bar("Please unlock your wallet first")
            return
            
        self.add_log_message("Starting manual synchronization...", "info")
        
        # Show progress
        self.refs['progress_sync'].current.visible = True
        self.refs['progress_sync'].current.value = 0
        self.refs['lbl_sync_status'].current.value = "Status: Starting sync..."
        self.refs['progress_sync'].current.update()
        self.refs['lbl_sync_status'].current.update()
        
        # Perform sync in background thread
        def sync_thread():
            success = self.wallet_core.scan_blockchain()
            self.refs['progress_sync'].current.visible = False
            self.refs['lbl_sync_status'].current.value = f"Last Sync: {datetime.now().strftime('%H:%M:%S')}"
            self.refs['progress_sync'].current.update()
            self.refs['lbl_sync_status'].current.update()
            
            if success:
                self.add_log_message("Synchronization completed", "success")
                self.auto_save_wallet()
            else:
                self.add_log_message("Synchronization failed", "error")
                
        threading.Thread(target=sync_thread, daemon=True).start()
        
    def manual_save_wallet(self):
        """Manually save the wallet"""
        if self.is_locked or not self.wallet_core.is_unlocked:
            self.show_snack_bar("Wallet not unlocked")
            return False
            
        try:
            success = self.wallet_core.save_wallet()
            
            if success:
                self.add_log_message("Wallet saved successfully", "success")
                self.show_snack_bar("Wallet saved to data directory")
                return True
            else:
                self.add_log_message("Failed to save wallet", "error")
                return False
                
        except Exception as e:
            self.add_log_message(f"Save error: {str(e)}", "error")
            return False

    def auto_save_wallet(self):
        """Auto-save wallet after operations"""
        if not self.is_locked and self.wallet_core.is_unlocked and self.wallet_core.wallets:
            try:
                success = self.wallet_core.save_wallet()
                if success:
                    self.debug_dialog("Wallet auto-saved successfully")
                else:
                    self.debug_dialog("Auto-save failed")
            except Exception as e:
                self.debug_dialog(f"Auto-save error: {e}")
        
    def refresh_wallets(self):
        """Refresh wallets display"""
        self.update_balance_display()
        self.update_wallets_list()
        self.add_log_message("Wallets refreshed", "info")
        self.auto_save_wallet()
        
    def copy_to_clipboard(self, text):
        """Copy text to clipboard"""
        self.page.set_clipboard(text)
        self.show_snack_bar("Copied to clipboard")
        
    def close_dialog(self):
        """Close the current dialog"""
        if self.page.dialog:
            self.page.dialog.open = False
            self.page.update()
            
    def debug_dialog(self, message):
        """Debug method to see if dialogs are working"""
        print(f"DEBUG: {message}")
        # Also show in log
        self.add_log_message(f"DEBUG: {message}", "info")
        
    def show_about_dialog(self):
        """Show about dialog using sliding overlay"""
        overlay_container = ft.Container(
            width=self.page.width - 280,
            height=self.page.height,
            left=280,
            top=0,
            bgcolor="#1a0f0f",
            border=ft.border.only(left=ft.BorderSide(4, "#8B4513")),
            animate_position=ft.Animation(300, "easeOut"),
            padding=20,
        )
        
        def close_dialog(e):
            # Animate out
            overlay_container.left = self.page.width
            self.page.update()
            time.sleep(0.3)
            self.page.overlay.remove(overlay_container)
            self.page.update()
        
        dialog_content = ft.Column([
            ft.Row([
                ft.Container(
                    content=ft.Image(
                        src="./wallet_icon.png",
                        width=32,
                        height=32,
                        fit=ft.ImageFit.CONTAIN,
                        color="#dc3545",
                        color_blend_mode=ft.BlendMode.SRC_IN,
                        error_content=ft.Text("🔴", size=20)
                    ),
                    margin=ft.margin.only(right=12),
                ),
                ft.Text("About Luna Wallet", size=24, color="#dc3545", weight="bold"),
            ], alignment=ft.MainAxisAlignment.START),
            ft.Container(height=30),
            ft.Text("Luna Wallet", size=18, color="#f8d7da"),
            ft.Text("Version 1.0", size=14, color="#f8d7da"),
            ft.Text("A secure wallet for Luna Network", size=14, color="#f8d7da"),
            ft.Text("Built with Flet", size=12, color="#f8d7da"),
            ft.Container(height=40),
            ft.ElevatedButton(
                "Close",
                on_click=close_dialog,
                style=ft.ButtonStyle(
                    color="#ffffff",
                    bgcolor="#dc3545",
                    padding=ft.padding.symmetric(horizontal=20, vertical=12),
                    shape=ft.RoundedRectangleBorder(radius=4)
                )
            )
        ], scroll=ft.ScrollMode.ADAPTIVE, horizontal_alignment=ft.CrossAxisAlignment.CENTER)
        
        overlay_container.content = dialog_content
        self.page.overlay.append(overlay_container)
        self.page.update()
        
    def status_updater(self):
        """Background status updater"""
        while True:
            try:
                # Update network status
                if not self.is_locked and self.wallet_core.is_unlocked:
                    self.refs['lbl_connection'].current.value = "Status: 🟢 Connected"
                else:
                    self.refs['lbl_connection'].current.value = "Status: 🔴 Disconnected"
                    
                if self.refs['lbl_connection'].current:
                    self.refs['lbl_connection'].current.update()
                    
                time.sleep(5)
            except Exception as e:
                print(f"Status update error: {e}")
                time.sleep(5)

def main(page: ft.Page):
    """Main application entry point"""
    app = LunaWalletApp()
    app.create_main_ui(page)

if __name__ == "__main__":
    ft.app(target=main)
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
import requests

# Import the wallet library
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from luna_lib import LunaLib, SecureDataManager

class LunaWalletApp:
    """Luna Wallet Application with Red Theme - Responsive Mobile Support"""
    
    def __init__(self):
        self.wallet_core = LunaLib(auto_scan=False)
        self.wallet_core.on_sync_progress = self.on_sync_progress
        self.minimized_to_tray = False
        self.current_tab_index = 0
        self.snack_bar = None
        self.selected_wallet_index = 0
        self.last_activity_time = time.time()
        self.auto_lock_minutes = 30
        self.is_locked = True
        self.is_mobile = False
        self.is_landscape = False
        self.current_layout = "desktop"  # desktop, mobile_portrait, mobile_landscape

        # Set up wallet callbacks
        self.wallet_core.on_balance_changed = self.on_balance_changed
        self.wallet_core.on_transaction_received = self.on_transaction_received
        self.wallet_core.on_sync_complete = self.on_sync_complete
        self.wallet_core.on_error = self.on_error

        # Refs for UI elements
        self.refs = {}

    def on_balance_changed(self):
        self.update_balance_display()
        self.auto_save_wallet()

    def on_sync_progress(self, progress, message):
        if not self.is_locked:
            self.refs['progress_sync'].current.value = progress / 100
            self.refs['progress_sync'].current.visible = True
            self.refs['lbl_sync_status'].current.value = f"Status: {message}"
            self.refs['progress_sync'].current.update()
            self.refs['lbl_sync_status'].current.update()

    def on_transaction_received(self):
        self.update_transaction_history()
        self.add_log_message("New transaction received", "success")
        self.auto_save_wallet()
        
    def on_sync_complete(self):
        self.update_balance_display()
        self.update_transaction_history()
        self.add_log_message("Blockchain sync completed", "success")
        self.auto_save_wallet()
        
    def on_error(self, error_msg):
        self.add_log_message(f"Error: {error_msg}", "error")
        
    def create_main_ui(self, page: ft.Page):
        self.page = page
        
        # Detect if we're on mobile
        self.is_mobile = page.platform in ["ios", "android"]
        self.detect_orientation()
        
        page.title = "Luna Wallet"
        page.theme_mode = ft.ThemeMode.DARK
        page.fonts = {"Custom": "./font.ttf"}
        page.theme = ft.Theme(font_family="Custom")
        
        page.padding = 0
        if not self.is_mobile:
            page.window.width = 1024
            page.window.height = 768
            page.window.min_width = 800
            page.window.min_height = 600
            page.window.center()
            
        page.window.icon = "./wallet_icon.png"
        
        page.on_window_event = self.on_window_event
        page.on_keyboard_event = self.on_keyboard_activity
        page.on_click = self.on_mouse_activity
        page.on_resize = self.on_page_resize
        
        self.main_layout = self.create_main_layout()
        page.add(self.main_layout)
        
        wallet_file_path = os.path.join(SecureDataManager.get_data_dir(), "wallet_encrypted.dat")
        if os.path.exists(wallet_file_path):
            self.show_lock_screen("Welcome Back", "Please unlock your wallet to continue")
        else:
            self.show_lock_screen("Welcome to Luna Wallet", "Create your first wallet to get started", show_create=True)
        
        threading.Thread(target=self.activity_monitor, daemon=True).start()

    def detect_orientation(self):
        """Detect if device is in landscape mode"""
        if not self.is_mobile:
            self.is_landscape = False
            self.current_layout = "desktop"
            return
            
        # For mobile, check window dimensions to determine orientation
        if hasattr(self.page, 'window') and self.page.window:
            width = self.page.window.width
            height = self.page.window.height
            self.is_landscape = width > height if width and height else False
            self.current_layout = "mobile_landscape" if self.is_landscape else "mobile_portrait"

    def on_page_resize(self, e):
        """Handle page resize for responsive layout"""
        self.detect_orientation()
        self.update_layout()

    def update_layout(self):
        """Update the layout based on current device and orientation"""
        if not hasattr(self, 'page') or not self.page:
            return
            
        # Remove current layout
        if hasattr(self, 'main_layout'):
            self.page.controls.clear()
            
        # Create new layout for current mode
        self.main_layout = self.create_main_layout()
        self.page.add(self.main_layout)
        self.page.update()
        
        # Update UI elements if wallet is unlocked
        if not self.is_locked:
            self.update_balance_display()
            self.update_transaction_history()
            self.update_wallets_list()

    def create_main_layout(self):
        """Create main layout based on current device and orientation"""
        if self.current_layout == "desktop":
            return self.create_desktop_layout()
        elif self.current_layout == "mobile_landscape":
            return self.create_mobile_landscape_layout()
        else:  # mobile_portrait
            return self.create_mobile_portrait_layout()

    def create_desktop_layout(self):
        """Desktop layout with sidebar"""
        sidebar = self.create_sidebar()
        main_content = self.create_main_content()
        
        return ft.Row(
            [sidebar, ft.VerticalDivider(width=1, color="#5c2e2e"), main_content],
            expand=True,
            spacing=0
        )

    def create_mobile_portrait_layout(self):
        """Mobile portrait layout - bottom navigation"""
        main_content = self.create_main_content()
        bottom_nav = self.create_bottom_navigation()
        
        return ft.Column([
            main_content,
            bottom_nav
        ], expand=True, spacing=0)

    def create_mobile_landscape_layout(self):
        """Mobile landscape layout - compact sidebar"""
        sidebar = self.create_mobile_sidebar()
        main_content = self.create_main_content()
        
        return ft.Row([
            sidebar,
            ft.VerticalDivider(width=1, color="#5c2e2e"),
            main_content
        ], expand=True, spacing=0)

    def create_bottom_navigation(self):
        """Bottom navigation bar for mobile portrait"""
        return ft.Container(
            content=ft.Row([
                ft.IconButton(
                    icon=ft.Icons.RECEIPT,
                    selected_icon=ft.Icons.RECEIPT,
                    selected=self.current_tab_index == 0,
                    on_click=lambda e: self.switch_mobile_tab(0),
                    icon_color="#f8d7da",
                    selected_icon_color="#dc3545",
                    tooltip="Transactions"
                ),
                ft.IconButton(
                    icon=ft.Icons.ACCOUNT_BALANCE_WALLET,
                    selected_icon=ft.Icons.ACCOUNT_BALANCE_WALLET,
                    selected=self.current_tab_index == 1,
                    on_click=lambda e: self.switch_mobile_tab(1),
                    icon_color="#f8d7da",
                    selected_icon_color="#dc3545",
                    tooltip="Wallets"
                ),
                ft.IconButton(
                    icon=ft.Icons.DOWNLOAD,
                    selected_icon=ft.Icons.DOWNLOAD,
                    selected=False,
                    on_click=lambda _: self.show_receive_dialog(),
                    icon_color="#f8d7da",
                    selected_icon_color="#dc3545",
                    tooltip="Receive"
                ),
                ft.IconButton(
                    icon=ft.Icons.UPLOAD,
                    selected_icon=ft.Icons.UPLOAD,
                    selected=False,
                    on_click=lambda _: self.show_send_dialog(),
                    icon_color="#f8d7da",
                    selected_icon_color="#dc3545",
                    tooltip="Send"
                ),
                ft.IconButton(
                    icon=ft.Icons.MENU,
                    selected_icon=ft.Icons.MENU,
                    selected=self.current_tab_index == 2,
                    on_click=lambda e: self.switch_mobile_tab(2),
                    icon_color="#f8d7da",
                    selected_icon_color="#dc3545",
                    tooltip="Menu"
                ),
            ], alignment=ft.MainAxisAlignment.SPACE_AROUND),
            bgcolor="#1a0f0f",
            padding=10,
            border=ft.border.only(top=ft.BorderSide(1, "#5c2e2e"))
        )

    def create_mobile_sidebar(self):
        """Compact sidebar for mobile landscape"""
        sidebar_width = 80
        
        quick_actions = ft.Container(
            content=ft.Column([
                ft.IconButton(
                    icon=ft.Icons.RECEIPT,
                    on_click=lambda e: self.switch_mobile_tab(0),
                    icon_color="#dc3545" if self.current_tab_index == 0 else "#f8d7da",
                    tooltip="Transactions"
                ),
                ft.IconButton(
                    icon=ft.Icons.ACCOUNT_BALANCE_WALLET,
                    on_click=lambda e: self.switch_mobile_tab(1),
                    icon_color="#dc3545" if self.current_tab_index == 1 else "#f8d7da",
                    tooltip="Wallets"
                ),
                ft.IconButton(
                    icon=ft.Icons.DOWNLOAD,
                    on_click=lambda _: self.show_receive_dialog(),
                    icon_color="#f8d7da",
                    tooltip="Receive"
                ),
                ft.IconButton(
                    icon=ft.Icons.UPLOAD,
                    on_click=lambda _: self.show_send_dialog(),
                    icon_color="#f8d7da",
                    tooltip="Send"
                ),
                ft.IconButton(
                    icon=ft.Icons.SYNC,
                    on_click=lambda _: self.manual_sync(),
                    icon_color="#f8d7da",
                    tooltip="Sync"
                ),
                ft.IconButton(
                    icon=ft.Icons.LOCK,
                    on_click=lambda _: self.lock_wallet(),
                    icon_color="#f8d7da",
                    tooltip="Lock"
                ),
            ], spacing=15, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            padding=10,
            margin=5,
            width=sidebar_width - 10
        )
        
        return ft.Container(
            content=ft.Column([
                ft.Container(
                    content=ft.IconButton(
                        icon=ft.Icons.MENU,
                        icon_color="#f8d7da",
                        tooltip="Menu"
                    ),
                    padding=5,
                    margin=ft.margin.only(bottom=20)
                ),
                quick_actions,
                ft.Container(expand=True),
            ], spacing=10, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            width=sidebar_width,
            padding=5,
            bgcolor="#1a0f0f"
        )

    def switch_mobile_tab(self, tab_index):
        """Switch tabs in mobile view"""
        self.current_tab_index = tab_index
        self.update_mobile_content()

    def update_mobile_content(self):
        """Update main content for mobile view"""
        main_content = self.create_main_content()
        
        if self.current_layout == "mobile_portrait":
            # Replace main content in portrait mode
            self.page.controls[0].controls[0] = main_content
        else:  # mobile_landscape
            # Replace main content in landscape mode  
            self.page.controls[0].controls[2] = main_content
            
        self.page.update()

    def show_lock_screen(self, title, subtitle, show_create=False):
        self.is_locked = True

        # Adjust lock screen for mobile
        if self.is_mobile:
            content_width = min(400, self.page.width - 40)
            content_padding = 20
        else:
            content_width = 500
            content_padding = 40

        overlay_container = ft.Container(
            width=self.page.width,
            height=self.page.height,
            left=0,
            top=-self.page.height,
            bgcolor="#1a0f0f",
            padding=content_padding,
            animate_position=ft.Animation(500, "easeOut"),
        )

        def unlock_wallet(e=None):
            if not password_field:
                return
            password = password_field.value
            
            if not password:
                self.show_snack_bar("Please enter a password")
                return
            
            for control in main_content.content.controls:
                if isinstance(control, ft.Row) and control.controls:
                    if isinstance(control.controls[0], ft.ElevatedButton):
                        control.controls[0].disabled = True
                        control.controls[0].text = "Unlocking..."
                        break
            
            if password_field:
                password_field.disabled = True
            
            self.page.update()
            
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
                        
                        overlay_container.top = -self.page.height
                        self.page.update()
                        time.sleep(0.5)
                        self.page.overlay.clear()
                        self.page.update()
                        
                        self.wallet_core.start_auto_scan()
                        self.show_snack_bar("Wallet unlocked!")
                    else:
                        self.add_log_message("Failed to unlock wallet", "error")
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

        def create_wallet(e):
            overlay_container.top = -self.page.height
            self.page.update()
            time.sleep(0.5)
            self.page.overlay.clear()
            self.page.update()
            self.show_create_wallet_dialog()

        # Adjust icon size for mobile
        icon_size = 60 if self.is_mobile else 100
        title_size = 24 if self.is_mobile else 32
        subtitle_size = 14 if self.is_mobile else 18

        main_content = ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Container(
                        content=ft.Image(
                            src="./wallet_icon.png",
                            width=icon_size,
                            height=icon_size,
                            fit=ft.ImageFit.CONTAIN,
                            color="#dc3545",
                            color_blend_mode=ft.BlendMode.SRC_IN,
                            error_content=ft.Text("🔴", size=icon_size//2)
                        ),
                        margin=ft.margin.only(right=20 if self.is_mobile else 25),
                        bgcolor="#00000000",
                    ),
                    ft.Column([
                        ft.Text(title, size=title_size, color="#dc3545", weight="bold"),
                        ft.Text(subtitle, size=subtitle_size, color="#f8d7da"),
                    ])
                ], alignment=ft.MainAxisAlignment.CENTER),
                
                ft.Container(height=30 if self.is_mobile else 40),
                
                ft.Container(
                    content=ft.TextField(
                        label="Wallet Password",
                        hint_text="Enter your wallet password",
                        password=True,
                        can_reveal_password=True,
                        width=content_width,
                        color="#f8d7da",
                        border_color="#5c2e2e",
                        autofocus=True,
                        on_submit=unlock_wallet if not show_create else None
                    ) if not show_create else ft.Container(height=0),
                    alignment=ft.alignment.center
                ),
                
                ft.Container(height=15 if self.is_mobile else 20),
                
                ft.Row([
                    ft.ElevatedButton(
                        "Create New Wallet" if show_create else "Unlock Wallet",
                        on_click=create_wallet if show_create else unlock_wallet,
                        style=ft.ButtonStyle(
                            color="#ffffff",
                            bgcolor="#dc3545",
                            padding=ft.padding.symmetric(
                                horizontal=25 if self.is_mobile else 30, 
                                vertical=12 if self.is_mobile else 15
                            ),
                            shape=ft.RoundedRectangleBorder(radius=4)
                        ),
                        height=45
                    )
                ], alignment=ft.MainAxisAlignment.CENTER),
                
                ft.Container(height=15 if self.is_mobile else 20),
                
                ft.Row([
                    ft.Column([
                        ft.TextButton(
                            "Ling Country Treasury",
                            on_click=lambda e: self.page.launch_url("https://bank.linglin.art"),
                            style=ft.ButtonStyle(color="#dc3545", shape=ft.RoundedRectangleBorder(radius=2))
                        ),
                        ft.TextButton(
                            "Learn More about Luna Coin", 
                            on_click=lambda e: self.page.launch_url("https://linglin.art/luna-coin"),
                            style=ft.ButtonStyle(color="#dc3545", shape=ft.RoundedRectangleBorder(radius=2))
                        )
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=5)
                ], alignment=ft.MainAxisAlignment.CENTER) if not show_create else ft.Container()
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, scroll=ft.ScrollMode.ADAPTIVE),
            alignment=ft.alignment.center,
            width=self.page.width,
            height=self.page.height,
        )
        
        password_field = None
        if not show_create:
            for control in main_content.content.controls:
                if hasattr(control, 'content') and isinstance(control.content, ft.TextField):
                    password_field = control.content
                    break
        
        overlay_container.content = main_content
        self.page.overlay.append(overlay_container)
        self.page.update()
        
        overlay_container.top = 0
        self.page.update()

    def create_sidebar(self):
        """Desktop sidebar"""
        sidebar_width = 240
        
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
        
        button_style = ft.ButtonStyle(
            color="#ffffff",
            bgcolor="#dc3545",
            padding=ft.padding.symmetric(horizontal=16, vertical=6),
            shape=ft.RoundedRectangleBorder(radius=2)
        )
        
        self.refs['btn_receive'] = ft.Ref[ft.ElevatedButton]()
        self.refs['btn_send'] = ft.Ref[ft.ElevatedButton]()
        self.refs['btn_sync'] = ft.Ref[ft.ElevatedButton]()
        self.refs['btn_lock'] = ft.Ref[ft.ElevatedButton]()
        
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
                    "🔄 Sync",
                    ref=self.refs['btn_sync'],
                    on_click=lambda _: self.manual_sync(),
                    style=button_style,
                    height=32
                ),
                ft.ElevatedButton(
                    "🔒 Lock",
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
        
        self.refs['lbl_connection'] = ft.Ref[ft.Text]()
        self.refs['lbl_sync_status'] = ft.Ref[ft.Text]()
        self.refs['progress_sync'] = ft.Ref[ft.ProgressBar]()
        
        network_status = ft.Container(
            content=ft.Column([
                ft.Text("🌐 Network Status", size=14, color="#f8d7da"),
                ft.Text("Status: Checking...", ref=self.refs['lbl_connection'], size=12, color="#f8d7da"),
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
        
        sidebar_content = ft.Column([
            ft.Container(
                content=ft.Row([
                    ft.PopupMenuButton(
                        content=ft.Text("☰", color="#f8d7da", size=14),
                        tooltip="System Menu",
                        items=[
                            ft.PopupMenuItem(text="Lock", on_click=lambda _: self.lock_wallet()),
                            ft.PopupMenuItem(text="Save", on_click=lambda _: self.manual_save_wallet()),
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
            ft.Container(expand=True),
            app_icon
        ], spacing=10, horizontal_alignment=ft.CrossAxisAlignment.CENTER)
        
        return ft.Container(
            content=sidebar_content,
            width=sidebar_width,
            padding=15,
            bgcolor="#1a0f0f"
        )

    def create_main_content(self):
        """Main content area - adapts to current view"""
        if self.current_layout == "mobile_portrait":
            return self.create_mobile_main_content()
        else:
            return self.create_desktop_main_content()

    def create_desktop_main_content(self):
        """Desktop main content with tabs"""
        self.refs['transactions_table'] = ft.Ref[ft.DataTable]()
        transactions_tab = self.create_transactions_tab()
        
        self.refs['wallets_table'] = ft.Ref[ft.DataTable]()
        wallets_tab = self.create_wallets_tab()
        
        self.refs['log_output'] = ft.Ref[ft.Column]()
        log_tab = self.create_log_tab()
        
        tabs = ft.Tabs(
            selected_index=self.current_tab_index,
            on_change=self.on_tab_change,
            tabs=[
                ft.Tab(text="📊 Transactions", content=transactions_tab),
                ft.Tab(text="👛 Wallets", content=wallets_tab),
                ft.Tab(text="📋 Log", content=log_tab),
            ],
            expand=True
        )
        
        return ft.Container(content=tabs, expand=True, padding=10, bgcolor="#2c1a1a")

    def create_mobile_main_content(self):
        """Mobile main content - single view at a time"""
        if self.current_tab_index == 0:
            return self.create_transactions_tab(mobile=True)
        elif self.current_tab_index == 1:
            return self.create_wallets_tab(mobile=True)
        else:  # tab 2 is menu in mobile
            return self.create_mobile_menu_tab()

    def create_mobile_menu_tab(self):
        """Mobile menu tab with quick actions and info"""
        menu_items = ft.Column([
            ft.ListTile(
                leading=ft.Icon(ft.Icons.RECEIPT, color="#dc3545"),
                title=ft.Text("Transactions", color="#f8d7da"),
                subtitle=ft.Text("View transaction history", color="#f8d7da"),
                on_click=lambda e: self.switch_mobile_tab(0)
            ),
            ft.ListTile(
                leading=ft.Icon(ft.Icons.ACCOUNT_BALANCE_WALLET, color="#dc3545"),
                title=ft.Text("Wallets", color="#f8d7da"),
                subtitle=ft.Text("Manage your wallets", color="#f8d7da"),
                on_click=lambda e: self.switch_mobile_tab(1)
            ),
            ft.ListTile(
                leading=ft.Icon(ft.Icons.SYNC, color="#dc3545"),
                title=ft.Text("Sync Wallet", color="#f8d7da"),
                subtitle=ft.Text("Synchronize with blockchain", color="#f8d7da"),
                on_click=lambda _: self.manual_sync()
            ),
            ft.ListTile(
                leading=ft.Icon(ft.Icons.LOCK, color="#dc3545"),
                title=ft.Text("Lock Wallet", color="#f8d7da"),
                subtitle=ft.Text("Lock your wallet for security", color="#f8d7da"),
                on_click=lambda _: self.lock_wallet()
            ),
            ft.ListTile(
                leading=ft.Icon(ft.Icons.INFO, color="#dc3545"),
                title=ft.Text("About", color="#f8d7da"),
                subtitle=ft.Text("About Luna Wallet", color="#f8d7da"),
                on_click=lambda _: self.show_about_dialog()
            ),
        ])
        
        return ft.Container(
            content=ft.Column([
                ft.Text("Menu", size=20, color="#f8d7da", weight="bold"),
                ft.Divider(color="#5c2e2e"),
                menu_items,
                ft.Container(expand=True),
            ], scroll=ft.ScrollMode.ADAPTIVE),
            expand=True,
            padding=15,
            bgcolor="#2c1a1a"
        )
        
    def create_transactions_tab(self, mobile=False):
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
        
        # For mobile, use a simpler list view
        if mobile:
            self.refs['mobile_transactions_list'] = ft.Ref[ft.Column]()
            transactions_list = ft.Column([], ref=self.refs['mobile_transactions_list'])
            
            return ft.Container(
                content=ft.Column([
                    ft.Row([
                        ft.Text("Transactions", size=18, color="#f8d7da", weight="bold"),
                        ft.IconButton(
                            icon=ft.Icons.REFRESH,
                            on_click=lambda _: self.update_transaction_history(),
                            icon_color="#dc3545"
                        )
                    ]),
                    ft.Container(
                        content=ft.ListView([transactions_list], expand=True),
                        expand=True,
                        border=ft.border.all(1, "#5c2e2e"),
                        border_radius=3
                    )
                ], expand=True),
                padding=10
            )
        
        return ft.Container(
            content=ft.Column([
                ft.Text("Transaction History", size=16, color="#f8d7da"),
                ft.Container(
                    content=ft.ListView([data_table], expand=True),
                    expand=True,
                    border=ft.border.all(1, "#5c2e2e"),
                    border_radius=3
                )
            ], expand=True),
            padding=10
        )
        
    def create_wallets_tab(self, mobile=False):
        data_table = ft.DataTable(
            ref=self.refs['wallets_table'],
            columns=[
                ft.DataColumn(ft.Text("Name", color="#f8d7da")),
                ft.DataColumn(ft.Text("Address", color="#f8d7da")),
                ft.DataColumn(ft.Text("Balance", color="#f8d7da")),
                ft.DataColumn(ft.Text("Tx(s)", color="#f8d7da")),
                ft.DataColumn(ft.Text("Select", color="#f8d7da")),
            ],
            rows=[],
            vertical_lines=ft.BorderSide(1, "#5c2e2e"),
            horizontal_lines=ft.BorderSide(1, "#5c2e2e"),
            bgcolor="#1a0f0f",
        )
        
        action_button_style = ft.ButtonStyle(
            color="#ffffff",
            bgcolor="#dc3545",
            padding=ft.padding.symmetric(horizontal=16, vertical=6),
            shape=ft.RoundedRectangleBorder(radius=3)
        )
        
        self.refs['btn_new_wallet'] = ft.Ref[ft.ElevatedButton]()
        self.refs['btn_import'] = ft.Ref[ft.ElevatedButton]()
        
        action_buttons = ft.Row([
            ft.ElevatedButton(
                "🆕 Create",
                ref=self.refs['btn_new_wallet'],
                on_click=lambda _: self.show_create_wallet_dialog(),
                style=action_button_style,
                height=32
            ),
            ft.ElevatedButton(
                "📁 Import",
                ref=self.refs['btn_import'],
                on_click=lambda _: self.show_import_dialog(),
                style=action_button_style,
                height=32
            ),
            ft.ElevatedButton(
                "🔑 Private Key",
                on_click=lambda _: self.show_export_private_key_dialog(),
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
                "🔒 Lock",
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
        
        # For mobile, use a vertical layout
        if mobile:
            action_buttons = ft.Column([
                ft.ElevatedButton(
                    "🆕 Create New Wallet",
                    on_click=lambda _: self.show_create_wallet_dialog(),
                    style=action_button_style,
                    height=40
                ),
                ft.ElevatedButton(
                    "📁 Import Wallet",
                    on_click=lambda _: self.show_import_dialog(),
                    style=action_button_style,
                    height=40
                ),
                ft.Row([
                    ft.ElevatedButton(
                        "🔑 Export Key",
                        on_click=lambda _: self.show_export_private_key_dialog(),
                        style=action_button_style,
                        height=35,
                        expand=True
                    ),
                    ft.ElevatedButton(
                        "🔄 Refresh",
                        on_click=lambda _: self.refresh_wallets(),
                        style=action_button_style,
                        height=35,
                        expand=True
                    ),
                ])
            ], spacing=10)
            
            self.refs['mobile_wallets_list'] = ft.Ref[ft.Column]()
            wallets_list = ft.Column([], ref=self.refs['mobile_wallets_list'])
            
            return ft.Container(
                content=ft.Column([
                    ft.Text("Wallets", size=18, color="#f8d7da", weight="bold"),
                    action_buttons,
                    ft.Container(
                        content=ft.ListView([wallets_list], expand=True),
                        expand=True,
                        border=ft.border.all(1, "#5c2e2e"),
                        border_radius=3,
                        padding=5
                    )
                ], expand=True),
                padding=10
            )
        
        return ft.Container(
            content=ft.Column([
                ft.Text("Wallet Management", size=16, color="#f8d7da"),
                action_buttons,
                ft.Container(
                    content=ft.ListView([data_table], expand=True),
                    expand=True,
                    border=ft.border.all(1, "#5c2e2e"),
                    border_radius=3
                )
            ], expand=True),
            padding=10
        )
        
    def create_log_tab(self):
        self.refs['log_output'] = ft.Ref[ft.Column]()
        
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
                ft.Container(content=ft.ListView([log_content], expand=True), expand=True)
            ], expand=True),
            padding=10
        )
        
    def on_tab_change(self, e):
        self.current_tab_index = e.control.selected_index
        if self.current_tab_index == 0:
            self.update_transaction_history()
        elif self.current_tab_index == 1:
            self.update_wallets_list()
        
    def update_transaction_history(self):
        if not self.wallet_core.is_unlocked:
            return
            
        transactions = self.wallet_core.get_transaction_history()
        
        # Update desktop table
        table = self.refs['transactions_table'].current
        if table:
            table.rows = []
            
            for tx in transactions[:50]:
                date_str = datetime.fromtimestamp(tx.get('timestamp', 0)).strftime("%Y-%m-%d %H:%M")
                tx_type = tx.get('type', 'transfer')
                type_icon = "💰" if tx_type == "reward" else "🔄"
                from_addr = tx.get('from', 'Network')
                to_addr = tx.get('to', 'Unknown')
                
                is_incoming = False
                if tx_type == "reward":
                    is_incoming = True
                    direction = f"← Mining Reward"
                else:
                    our_addresses = [w['address'].lower() for w in self.wallet_core.wallets]
                    if to_addr and to_addr.lower() in our_addresses:
                        is_incoming = True
                        direction = f"← From: {from_addr}"
                    else:
                        direction = f"→ To: {to_addr}"
                
                amount = tx.get('amount', 0)
                amount_color = "#00ff00" if is_incoming else "#ff0000"
                status = tx.get('status', 'unknown')
                status_icon = "✅" if status == "confirmed" else "⏳" if status == "pending" else "❌"
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
        
        # Update mobile list
        mobile_list = self.refs.get('mobile_transactions_list')
        if mobile_list and mobile_list.current:
            mobile_list.current.controls.clear()
            
            for tx in transactions[:20]:  # Show fewer on mobile
                date_str = datetime.fromtimestamp(tx.get('timestamp', 0)).strftime("%m/%d %H:%M")
                tx_type = tx.get('type', 'transfer')
                type_icon = "💰" if tx_type == "reward" else "🔄"
                
                is_incoming = tx_type == "reward" or any(
                    w['address'].lower() == tx.get('to', '').lower() 
                    for w in self.wallet_core.wallets
                )
                
                amount = tx.get('amount', 0)
                amount_color = "#00ff00" if is_incoming else "#ff0000"
                status = tx.get('status', 'unknown')
                status_icon = "✅" if status == "confirmed" else "⏳" if status == "pending" else "❌"
                
                mobile_list.current.controls.append(
                    ft.ListTile(
                        leading=ft.Icon(
                            ft.Icons.ARROW_UPWARD if not is_incoming else ft.Icons.ARROW_DOWNWARD,
                            color=amount_color
                        ),
                        title=ft.Text(f"{amount:.6f} LUN", color=amount_color),
                        subtitle=ft.Text(f"{date_str} • {status_icon} {status}", color="#f8d7da", size=12),
                        trailing=ft.Text(type_icon, size=16),
                    )
                )
            
            mobile_list.current.update()
        
    def update_wallets_list(self):
        if not self.wallet_core.is_unlocked:
            return
            
        # Update desktop table
        table = self.refs['wallets_table'].current
        if table:
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
        
        # Update mobile list
        mobile_list = self.refs.get('mobile_wallets_list')
        if mobile_list and mobile_list.current:
            mobile_list.current.controls.clear()
            
            for i, wallet in enumerate(self.wallet_core.wallets):
                is_selected = i == self.selected_wallet_index
                
                mobile_list.current.controls.append(
                    ft.Card(
                        content=ft.Container(
                            content=ft.Column([
                                ft.Row([
                                    ft.Text(wallet['label'], color="#f8d7da", weight="bold", size=16),
                                    ft.Container(
                                        content=ft.Text("SELECTED", color="#28a745", size=10) if is_selected else ft.Text("", size=10),
                                        bgcolor="#1a3a1a" if is_selected else "transparent",
                                        padding=ft.padding.symmetric(horizontal=8, vertical=2),
                                        border_radius=10
                                    )
                                ]),
                                ft.Text(f"Balance: {wallet['balance']:.6f} LUN", color="#f8d7da", size=14),
                                ft.Text(f"Address: {wallet['address'][:16]}...", color="#f8d7da", size=12),
                                ft.Text(f"Transactions: {len(wallet['transactions'])}", color="#f8d7da", size=12),
                                ft.ElevatedButton(
                                    "Select Wallet" if not is_selected else "Selected",
                                    on_click=lambda e, idx=i: self.select_wallet(idx),
                                    style=ft.ButtonStyle(
                                        color="#ffffff",
                                        bgcolor="#28a745" if is_selected else "#dc3545",
                                        padding=ft.padding.symmetric(horizontal=16, vertical=8)
                                    ),
                                    width=200
                                ) if not is_selected else ft.Container(height=0)
                            ]),
                            padding=15
                        ),
                        color="#2c1a1a",
                        margin=ft.margin.symmetric(vertical=5)
                    )
                )
            
            mobile_list.current.update()

    def select_wallet(self, wallet_index):
        if wallet_index < len(self.wallet_core.wallets):
            self.selected_wallet_index = wallet_index
            self.update_balance_display()
            self.update_wallets_list()
            self.show_snack_bar(f"Selected wallet: {self.wallet_core.wallets[wallet_index]['label']}")
            self.auto_save_wallet()
        
    def add_log_message(self, message, msg_type="info"):
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
            if len(log_column.controls) > 100:
                log_column.controls.pop(0)
            log_column.update()
            
    def clear_log(self):
        log_column = self.refs['log_output'].current
        if log_column:
            log_column.controls.clear()
            log_column.update()

    def show_receive_dialog(self):
        if self.is_locked or not self.wallet_core.is_unlocked or not self.wallet_core.wallets:
            self.show_snack_bar("Please unlock your wallet first")
            return
        
        # Adjust dialog for mobile
        if self.is_mobile:
            dialog_width = self.page.width - 40
            dialog_height = self.page.height - 100
            left = 20
            top = 50
        else:
            dialog_width = self.page.width - 280
            dialog_height = self.page.height
            left = 280
            top = 0

        overlay_container = ft.Container(
            width=dialog_width,
            height=dialog_height,
            left=left,
            top=top,
            bgcolor="#1a0f0f",
            border=ft.border.only(left=ft.BorderSide(4, "#8B4513")) if not self.is_mobile else ft.border.all(2, "#8B4513"),
            animate_position=ft.Animation(300, "easeOut"),
            padding=20,
        )
        
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
        
        wallet_options = []
        for i, wallet in enumerate(self.wallet_core.wallets):
            wallet_options.append(ft.dropdown.Option(key=str(i), text=f"{wallet['label']} ({wallet['address'][:16]}...)"))
        
        wallet_dropdown = ft.Dropdown(
            label="Select Wallet to Receive",
            options=wallet_options,
            value=str(self.selected_wallet_index),
            width=min(400, dialog_width - 40),
            color="#f8d7da",
            border_color="#5c2e2e"
        )
        
        address_display = ft.Text("", size=12, color="#f8d7da", selectable=True)
        qr_content = ft.Container()
        
        def update_qr_code(e):
            selected_index = int(wallet_dropdown.value)
            if selected_index < len(self.wallet_core.wallets):
                address = self.wallet_core.wallets[selected_index]['address']
                address_display.value = address
                
                try:
                    import qrcode
                    qr = qrcode.QRCode(version=1, box_size=8, border=4)
                    qr.add_data(address)
                    qr.make(fit=True)
                    qr_img = qr.make_image(fill_color="red", back_color="white")
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
                self.page.update()
        
        wallet_dropdown.on_change = update_qr_code
        
        def close_dialog(e):
            overlay_container.left = self.page.width
            self.page.update()
            time.sleep(0.3)
            self.page.overlay.remove(overlay_container)
            self.page.update()
        
        dialog_content = ft.Column([
            header,
            ft.Container(height=20),
            wallet_dropdown,
            ft.Container(height=15),
            ft.Text("Wallet Address:", size=16, color="#f8d7da"),
            ft.Container(content=address_display, padding=15, bgcolor="#2c1a1a", border_radius=8, width=min(500, dialog_width - 40)),
            ft.Container(height=20),
            ft.Container(content=qr_content, padding=20, alignment=ft.alignment.center),
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
        
        overlay_container.content = dialog_content
        self.page.overlay.append(overlay_container)
        self.page.update()
        update_qr_code(None)
        
    def show_send_dialog(self):
        if self.is_locked or not self.wallet_core.is_unlocked or not self.wallet_core.wallets:
            self.show_snack_bar("Please unlock your wallet first")
            return
            
        # Adjust dialog for mobile
        if self.is_mobile:
            dialog_width = self.page.width - 40
            dialog_height = self.page.height - 100
            left = 20
            top = 50
        else:
            dialog_width = self.page.width - 280
            dialog_height = self.page.height
            left = 280
            top = 0

        overlay_container = ft.Container(
            width=dialog_width,
            height=dialog_height,
            left=left,
            top=top,
            bgcolor="#1a0f0f",
            border=ft.border.only(left=ft.BorderSide(4, "#8B4513")) if not self.is_mobile else ft.border.all(2, "#8B4513"),
            animate_position=ft.Animation(300, "easeOut"),
            padding=20,
        )
        
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
        
        wallet_options = []
        for i, wallet in enumerate(self.wallet_core.wallets):
            balance = wallet['balance'] - wallet['pending_send']
            wallet_options.append(ft.dropdown.Option(key=str(i), text=f"{wallet['label']} ({balance:.6f} LUN)"))
        
        wallet_dropdown = ft.Dropdown(
            label="Select Wallet to Send From",
            options=wallet_options,
            value=str(self.selected_wallet_index),
            width=min(500, dialog_width - 40),
            color="#f8d7da",
            border_color="#5c2e2e"
        )
        
        to_address_field = ft.TextField(
            label="To Address",
            hint_text="LUN_... or Luna address",
            width=min(500, dialog_width - 40),
            color="#f8d7da",
            border_color="#5c2e2e"
        )
        
        amount_field = ft.TextField(
            label="Amount (LUN)",
            hint_text="0.000000",
            width=min(500, dialog_width - 40),
            color="#f8d7da",
            border_color="#5c2e2e"
        )
        
        memo_field = ft.TextField(
            label="Memo (Optional)",
            hint_text="Message for recipient",
            width=min(500, dialog_width - 40),
            color="#f8d7da",
            border_color="#5c2e2e"
        )
        
        password_field = ft.TextField(
            label="Wallet Password (Optional)",
            hint_text="For transaction signing",
            password=True,
            can_reveal_password=True,
            width=min(500, dialog_width - 40),
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
            
            close_dialog(None)
            selected_index = int(wallet_dropdown.value)
            
            def confirm_send():
                def send_thread():
                    original_index = self.selected_wallet_index
                    self.selected_wallet_index = selected_index
                    success = self.wallet_core.send_transaction(to_address, amount, memo, password)
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
                
            selected_wallet = self.wallet_core.wallets[selected_index]
            self.show_confirmation_dialog(
                f"Send {amount:.6f} LUN from {selected_wallet['label']} to:\n{to_address}\n\nMemo: {memo}",
                confirm_send
            )
        
        def close_dialog(e):
            overlay_container.left = self.page.width
            self.page.update()
            time.sleep(0.3)
            self.page.overlay.remove(overlay_container)
            self.page.update()
        
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
        
        overlay_container.content = dialog_content
        self.page.overlay.append(overlay_container)
        self.page.update()
        
    def show_confirmation_dialog(self, message, confirm_callback):
        # Adjust dialog for mobile
        if self.is_mobile:
            dialog_width = self.page.width - 40
            dialog_height = self.page.height - 100
            left = 20
            top = 50
        else:
            dialog_width = self.page.width - 280
            dialog_height = self.page.height
            left = 280
            top = 0

        overlay_container = ft.Container(
            width=dialog_width,
            height=dialog_height,
            left=left,
            top=top,
            bgcolor="#1a0f0f",
            border=ft.border.only(left=ft.BorderSide(4, "#8B4513")) if not self.is_mobile else ft.border.all(2, "#8B4513"),
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
        # Adjust dialog for mobile
        if self.is_mobile:
            dialog_width = self.page.width - 40
            dialog_height = self.page.height - 100
            left = 20
            top = 50
        else:
            dialog_width = self.page.width - 280
            dialog_height = self.page.height
            left = 280
            top = 0

        overlay_container = ft.Container(
            width=dialog_width,
            height=dialog_height,
            left=left,
            top=top,
            bgcolor="#1a0f0f",
            border=ft.border.only(left=ft.BorderSide(4, "#8B4513")) if not self.is_mobile else ft.border.all(2, "#8B4513"),
            animate_position=ft.Animation(300, "easeOut"),
            padding=20,
        )
        
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
            ft.Text("🆕 Create", size=24, color="#dc3545", weight="bold"),
        ], alignment=ft.MainAxisAlignment.START)
        
        label_field = ft.TextField(
            label="Wallet Name",
            hint_text="My Wallet", 
            value="My Wallet",
            width=min(500, dialog_width - 40),
            color="#f8d7da",
            border_color="#5c2e2e"
        )
        
        password_field = ft.TextField(
            label="Password",
            hint_text="Encrypt wallet with password",
            password=True,
            can_reveal_password=True,
            width=min(500, dialog_width - 40),
            color="#f8d7da",
            border_color="#5c2e2e"
        )
        
        confirm_field = ft.TextField(
            label="Confirm Password", 
            hint_text="Repeat password",
            password=True,
            can_reveal_password=True,
            width=min(500, dialog_width - 40),
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
            
            close_dialog(None)
            
            def create_thread():
                try:
                    if not self.wallet_core.is_unlocked and not self.wallet_core.wallets:
                        address = self.wallet_core.create_wallet(label)
                        if address:
                            self.wallet_core.is_unlocked = True
                            self.wallet_core.wallet_password = password
                            save_success = self.wallet_core.save_wallet(password)
                            
                            if save_success:
                                unlock_success = self.wallet_core.unlock_wallet(password)
                                if unlock_success:
                                    success = True
                                else:
                                    success = bool(self.wallet_core.wallets)
                            else:
                                success = False
                        else:
                            success = False
                    else:
                        address = self.wallet_core.create_wallet(label)
                        success = address is not None
                        if success:
                            self.wallet_core.save_wallet()
                    
                    def update_ui():
                        if success and self.wallet_core.wallets:
                            self.add_log_message(f"Created wallet '{label}'", "success")
                            self.update_balance_display()
                            self.update_wallets_list()
                            self.auto_save_wallet()
                            self.show_snack_bar("Wallet created successfully!")
                            
                            if self.wallet_core.wallets:
                                wallet_address = self.wallet_core.wallets[-1]['address']
                                self.add_log_message(f"Wallet address: {wallet_address}", "info")
                                
                            self.wallet_core.start_auto_scan()
                        else:
                            self.add_log_message("Failed to create wallet", "error")
                            self.show_snack_bar("Wallet creation failed")
                            
                    self.page.run_thread(update_ui)
                    
                except Exception as ex:
                    def show_error():
                        self.add_log_message(f"Creation error: {str(ex)}", "error")
                        self.show_snack_bar(f"Error: {str(ex)}")
                    self.page.run_thread(show_error)
            
            threading.Thread(target=create_thread, daemon=True).start()
        
        def close_dialog(e):
            overlay_container.left = self.page.width
            self.page.update()
            time.sleep(0.3)
            self.page.overlay.remove(overlay_container)
            self.page.update()
        
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
        
        overlay_container.content = dialog_content
        self.page.overlay.append(overlay_container)
        self.page.update()
        
    def show_import_dialog(self):
        # Adjust dialog for mobile
        if self.is_mobile:
            dialog_width = self.page.width - 40
            dialog_height = self.page.height - 100
            left = 20
            top = 50
        else:
            dialog_width = self.page.width - 280
            dialog_height = self.page.height
            left = 280
            top = 0

        overlay_container = ft.Container(
            width=dialog_width,
            height=dialog_height,
            left=left,
            top=top,
            bgcolor="#1a0f0f",
            border=ft.border.only(left=ft.BorderSide(4, "#8B4513")) if not self.is_mobile else ft.border.all(2, "#8B4513"),
            animate_position=ft.Animation(300, "easeOut"),
            padding=20,
        )
        
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
        
        private_key_field = ft.TextField(
            label="Private Key (64 hex characters)",
            hint_text="Enter your 64-character private key",
            width=min(500, dialog_width - 40),
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
            width=min(500, dialog_width - 40),
            color="#f8d7da",
            border_color="#5c2e2e"
        )
        
        password_field = ft.TextField(
            label="Wallet Password (for encryption)",
            hint_text="Password to encrypt imported wallet",
            password=True,
            can_reveal_password=True,
            width=min(500, dialog_width - 40),
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
                
            if len(private_key) != 64 or not all(c in '0123456789abcdefABCDEF' for c in private_key):
                self.show_snack_bar("Invalid private key format. Must be 64 hexadecimal characters.")
                return
                
            if not password:
                self.show_snack_bar("Please enter a password to encrypt the wallet")
                return
            
            close_dialog(None)
            
            def import_thread():
                try:
                    if not self.wallet_core.is_unlocked:
                        self.wallet_core.wallets = []
                        self.wallet_core.is_unlocked = True
                    
                    success = self.wallet_core.import_wallet(private_key, label)
                    
                    if success:
                        save_success = self.wallet_core.save_wallet(password)
                        
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
            overlay_container.left = self.page.width
            self.page.update()
            time.sleep(0.3)
            self.page.overlay.remove(overlay_container)
            self.page.update()
        
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
        
        overlay_container.content = dialog_content
        self.page.overlay.append(overlay_container)
        self.page.update()
        
    def show_export_private_key_dialog(self):
        if self.is_locked or not self.wallet_core.is_unlocked or not self.wallet_core.wallets:
            self.show_snack_bar("Please unlock your wallet first")
            return
            
        # Adjust dialog for mobile
        if self.is_mobile:
            dialog_width = self.page.width - 40
            dialog_height = self.page.height - 100
            left = 20
            top = 50
        else:
            dialog_width = self.page.width - 280
            dialog_height = self.page.height
            left = 280
            top = 0

        overlay_container = ft.Container(
            width=dialog_width,
            height=dialog_height,
            left=left,
            top=top,
            bgcolor="#1a0f0f",
            border=ft.border.only(left=ft.BorderSide(4, "#8B4513")) if not self.is_mobile else ft.border.all(2, "#8B4513"),
            animate_position=ft.Animation(300, "easeOut"),
            padding=20,
        )
        
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
        
        wallet_options = []
        for i, wallet in enumerate(self.wallet_core.wallets):
            wallet_options.append(ft.dropdown.Option(key=str(i), text=f"{wallet['label']} ({wallet['address'][:16]}...)"))
        
        wallet_dropdown = ft.Dropdown(
            label="Select Wallet to Export",
            options=wallet_options,
            value=str(self.selected_wallet_index),
            width=min(500, dialog_width - 40),
            color="#f8d7da",
            border_color="#5c2e2e"
        )
        
        private_key_display = ft.Text("", size=12, color="#f8d7da", selectable=True)
        
        def update_private_key(e):
            selected_index = int(wallet_dropdown.value)
            if selected_index < len(self.wallet_core.wallets):
                wallet_data = self.wallet_core.export_wallet(self.wallet_core.wallets[selected_index]['address'])
                if wallet_data and 'private_key' in wallet_data:
                    private_key_display.value = wallet_data['private_key']
                else:
                    private_key_display.value = "Error: Could not retrieve private key"
                private_key_display.update()
        
        wallet_dropdown.on_change = update_private_key
        
        def close_dialog(e):
            overlay_container.left = self.page.width
            self.page.update()
            time.sleep(0.3)
            self.page.overlay.remove(overlay_container)
            self.page.update()
        
        dialog_content = ft.Column([
            header,
            ft.Container(height=20),
            ft.Text("⚠️ WARNING: Never share your private key!", color="#ff0000", size=16, weight="bold"),
            ft.Text("Anyone with this key can access your funds!", color="#ff0000", size=14),
            ft.Container(height=20),
            wallet_dropdown,
            ft.Container(height=15),
            ft.Container(content=private_key_display, padding=15, bgcolor="#2c1a1a", border_radius=8, width=min(500, dialog_width - 40)),
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
        
        overlay_container.content = dialog_content
        self.page.overlay.append(overlay_container)
        self.page.update()
        update_private_key(None)
        
    def manual_sync(self):
        if self.is_locked or not self.wallet_core.is_unlocked:
            self.show_snack_bar("Please unlock your wallet first")
            return
            
        self.add_log_message("Starting manual synchronization...", "info")
        
        self.refs['progress_sync'].current.visible = True
        self.refs['progress_sync'].current.value = 0
        self.refs['lbl_sync_status'].current.value = "Status: Starting sync..."
        self.refs['progress_sync'].current.update()
        self.refs['lbl_sync_status'].current.update()

        def sync_thread():
            try:
                success = self.wallet_core.scan_blockchain(force_full_scan=True)
                
                def update_ui():
                    if success:
                        self.add_log_message("Synchronization completed successfully", "success")
                        self.auto_save_wallet()
                        self.update_balance_display()
                        self.update_transaction_history()
                        self.update_wallets_list()
                    else:
                        self.add_log_message("Synchronization failed", "error")
                        
                    def hide_progress():
                        time.sleep(2)
                        self.refs['progress_sync'].current.visible = False
                        self.refs['lbl_sync_status'].current.value = f"Last Sync: {datetime.now().strftime('%H:%M:%S')}"
                        self.refs['progress_sync'].current.update()
                        self.refs['lbl_sync_status'].current.update()
                        
                    threading.Thread(target=hide_progress, daemon=True).start()
                    
                self.page.run_thread(update_ui)
                
            except Exception as e:
                def update_error():
                    self.refs['progress_sync'].current.visible = False
                    self.refs['lbl_sync_status'].current.value = f"Sync error: {str(e)}"
                    self.refs['progress_sync'].current.update()
                    self.refs['lbl_sync_status'].current.update()
                    self.add_log_message(f"Sync error: {str(e)}", "error")
                    
                self.page.run_thread(update_error)
            
        threading.Thread(target=sync_thread, daemon=True).start()

    def manual_save_wallet(self):
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
        if not self.is_locked and self.wallet_core.is_unlocked and self.wallet_core.wallets:
            try:
                self.wallet_core.save_wallet()
            except Exception as e:
                pass
        
    def refresh_wallets(self):
        self.update_balance_display()
        self.update_wallets_list()
        self.add_log_message("Wallets refreshed", "info")
        self.auto_save_wallet()
        
    def copy_to_clipboard(self, text):
        self.page.set_clipboard(text)
        self.show_snack_bar("Copied to clipboard")
        
    def show_about_dialog(self):
        # Adjust dialog for mobile
        if self.is_mobile:
            dialog_width = self.page.width - 40
            dialog_height = self.page.height - 100
            left = 20
            top = 50
        else:
            dialog_width = self.page.width - 280
            dialog_height = self.page.height
            left = 280
            top = 0

        overlay_container = ft.Container(
            width=dialog_width,
            height=dialog_height,
            left=left,
            top=top,
            bgcolor="#1a0f0f",
            border=ft.border.only(left=ft.BorderSide(4, "#8B4513")) if not self.is_mobile else ft.border.all(2, "#8B4513"),
            animate_position=ft.Animation(300, "easeOut"),
            padding=20,
        )
        
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

    def update_balance_display(self):
        if not self.wallet_core.is_unlocked or not self.wallet_core.wallets:
            self.refs['lbl_wallet_name'].current.value = "Name: No wallet loaded"
            self.refs['lbl_address'].current.value = "Address: --"
            self.refs['lbl_balance'].current.value = "Balance: 0.000000 LUN"
            self.refs['lbl_available'].current.value = "Available: 0.000000 LUN"
            self.refs['lbl_pending'].current.value = "Pending: 0.000000 LUN"
            self.refs['lbl_transactions'].current.value = "Transactions: 0"
        else:
            if self.selected_wallet_index < len(self.wallet_core.wallets):
                wallet = self.wallet_core.wallets[self.selected_wallet_index]
                self.refs['lbl_wallet_name'].current.value = f"Name: {wallet['label']}"
                self.refs['lbl_address'].current.value = f"Address: {wallet['address'][:20]}..."
                self.refs['lbl_balance'].current.value = f"Balance: {wallet['balance']:.6f} LUN"
                self.refs['lbl_available'].current.value = f"Available: {wallet['balance'] - wallet['pending_send']:.6f} LUN"
                self.refs['lbl_pending'].current.value = f"Pending: {wallet['pending_send']:.6f} LUN"
                self.refs['lbl_transactions'].current.value = f"Transactions: {len(wallet['transactions'])}"
                self.page.title = f"🔴 Luna Wallet - {wallet['balance']:.2f} LUN"
        
        for ref in [self.refs['lbl_wallet_name'], self.refs['lbl_address'], self.refs['lbl_balance'],
                   self.refs['lbl_available'], self.refs['lbl_pending'], self.refs['lbl_transactions']]:
            if ref.current:
                ref.current.update()
                
        self.page.update()

    def lock_wallet(self):
        self.is_locked = True
        self.wallet_core.lock_wallet()
        self.show_lock_screen("Wallet Locked", "Please unlock to continue")
        self.add_log_message("Wallet locked", "info")
        
    def activity_monitor(self):
        while True:
            try:
                current_time = time.time()
                inactive_time = current_time - self.last_activity_time
                
                if (not self.is_locked and 
                    inactive_time > self.auto_lock_minutes * 60 and 
                    self.wallet_core.is_unlocked):
                    self.add_log_message(f"Auto-locking wallet after {self.auto_lock_minutes} minutes of inactivity", "info")
                    self.lock_wallet()
                
                time.sleep(10)
            except Exception as e:
                print(f"Activity monitor error: {e}")
                time.sleep(10)
    
    def on_keyboard_activity(self, e):
        if not self.is_locked:
            self.last_activity_time = time.time()

    def on_mouse_activity(self, e):
        if not self.is_locked:
            self.last_activity_time = time.time()

    def on_window_resize(self, e):
        self.add_log_message(f"Window resized to {e.width}x{e.height}", "info")

    def on_window_event(self, e):
        if e.data == "close":
            return True
        elif e.data == "resize":
            self.on_window_resize(e)
        return True

    def show_snack_bar(self, message: str):
        snack_bar = ft.SnackBar(content=ft.Text(message), shape=ft.RoundedRectangleBorder(radius=3))
        self.page.overlay.append(snack_bar)
        snack_bar.open = True
        self.page.update()
        def remove_snack():
            time.sleep(3)
            self.page.overlay.remove(snack_bar)
            self.page.update()
        threading.Thread(target=remove_snack, daemon=True).start()

def main(page: ft.Page):
    app = LunaWalletApp()
    app.create_main_ui(page)

if __name__ == "__main__":
    ft.app(target=main)
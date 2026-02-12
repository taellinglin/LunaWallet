import flet as ft
from gui.icon_utils import icon_label
import threading
import time
import json
from datetime import datetime

class SettingsPage:
    def __init__(self, app, on_back=None):
        self.app = app
        self.on_back = on_back
        self.is_mobile = bool(getattr(app, "is_mobile", False))

        # Settings state
        self.cache_settings = {
            'max_cache_age_days': 30,
            'max_cache_size_mb': 100,
            'auto_cleanup_enabled': True,
            'background_sync_enabled': True,
            'mempool_cleanup_hours': 2,
            'batch_transaction_updates': True,
            'blockchain_pruning_enabled': True
        }

        self.runtime_settings = {
            'luna_big_decimals': 8,
            'luna_small_decimals': 4,
            'luna_tiny_decimals': 2,
            'sync_url': "",
            'enable_big_decimals': True,
            'enable_small_decimals': True,
            'enable_tiny_decimals': True,
            'flat_lkc_display': False
        }

        self.security_settings = {
            'biometric_enabled': False
        }

        self.initial_wallet_address = None

        # UI elements
        self.cache_size_text = ft.Text("Calculating...", color="#f8d7da")
        self.cache_age_text = ft.Text("Calculating...", color="#f8d7da")
        self.last_cleanup_text = ft.Text("Never", color="#f8d7da")

        # Load current settings
        self.load_settings()

    def load_settings(self):
        """Load current settings from app/database"""
        try:
            # Load from database if available
            if hasattr(self.app, 'database') and self.app.database:
                settings = self.app.database.get_settings()
                if settings:
                    self.cache_settings.update(settings)
            # Load from Storage if available (fallback)
            if hasattr(self.app, 'storage') and self.app.storage:
                raw = self.app.storage.get("settings")
                if raw:
                    payload = json.loads(raw)
                    self.cache_settings.update(payload.get("cache", {}))
                    self.runtime_settings.update(payload.get("runtime", {}))
                try:
                    if hasattr(self.app, "get_initial_wallet_address"):
                        self.initial_wallet_address = self.app.get_initial_wallet_address()
                    if not self.initial_wallet_address:
                        self.initial_wallet_address = self.app.storage.get("initial_wallet_address")
                except Exception:
                    self.initial_wallet_address = None
                raw_security = self.app.storage.get("security")
                if raw_security:
                    payload = json.loads(raw_security)
                    self.security_settings.update({
                        'biometric_enabled': bool(payload.get('biometric_enabled', False))
                    })
        except Exception as e:
            print(f"Error loading settings: {e}")

    def save_settings(self):
        """Save settings to database"""
        try:
            if hasattr(self.app, 'database') and self.app.database:
                self.app.database.save_settings(self.cache_settings)
                self.app.show_snackbar("Settings saved successfully", "success")
            else:
                self.app.show_snackbar("Saved settings locally", "success")

            # Save to Storage for runtime settings and cross-sessions
            if hasattr(self.app, 'storage') and self.app.storage:
                payload = {
                    "cache": self.cache_settings,
                    "runtime": self.runtime_settings,
                }
                self.app.storage.set("settings", json.dumps(payload))

                security_payload = {
                    "biometric_enabled": bool(self.security_settings.get("biometric_enabled", False))
                }
                self.app.storage.set("security", json.dumps(security_payload))

                if hasattr(self.app, "set_biometric_enabled"):
                    self.app.set_biometric_enabled(self.security_settings.get("biometric_enabled", False))

            # Apply environment variables for lunalib/runtime
            self.apply_runtime_settings()
        except Exception as e:
            print(f"Error saving settings: {e}")
            self.app.show_snackbar(f"Error saving settings: {e}", "error")

    def apply_runtime_settings(self):
        try:
            import os
            if self.runtime_settings.get("enable_big_decimals", True):
                os.environ["LUNALIB_AMOUNT_DECIMALS"] = str(self.runtime_settings.get("luna_big_decimals", 8))
            else:
                os.environ["LUNALIB_AMOUNT_DECIMALS"] = "0"

            if self.runtime_settings.get("enable_small_decimals", True):
                os.environ["LUNALIB_AMOUNT_SMALL_DECIMALS"] = str(self.runtime_settings.get("luna_small_decimals", 4))
            else:
                os.environ["LUNALIB_AMOUNT_SMALL_DECIMALS"] = "0"

            if self.runtime_settings.get("enable_tiny_decimals", True):
                os.environ["LUNALIB_AMOUNT_TINY_DECIMALS"] = str(self.runtime_settings.get("luna_tiny_decimals", 2))
            else:
                os.environ["LUNALIB_AMOUNT_TINY_DECIMALS"] = "0"
            sync_url = (self.runtime_settings.get("sync_url") or "").strip()
            if sync_url:
                os.environ["LUNALIB_ENDPOINT_URL"] = sync_url
                os.environ["LUNA_NODE_URL"] = sync_url
            os.environ["LUNAWALLET_FLAT_LKC"] = "1" if self.runtime_settings.get("flat_lkc_display") else "0"
        except Exception as e:
            print(f"Error applying runtime settings: {e}")

    def create(self):
        section_gap = 12 if self.is_mobile else 20
        outer_padding = 12 if self.is_mobile else 20
        return ft.Container(
            content=ft.Column([
                self.create_header(),
                ft.Container(height=section_gap),
                self.create_blockchain_section(),
                ft.Container(height=section_gap),
                self.create_runtime_section(),
                ft.Container(height=section_gap),
                self.create_security_section(),
                ft.Container(height=section_gap),
                self.create_wallet_section(),
                ft.Container(height=section_gap),
                self.create_ui_section(),
                ft.Container(height=section_gap),
                self.create_transaction_section(),
                ft.Container(height=section_gap),
                self.create_actions_section(),
            ], scroll=ft.ScrollMode.ADAPTIVE),
            expand=True,
            padding=outer_padding,
            bgcolor="#2c1a1a"
        )

    def create_header(self):
        title_size = 20 if self.is_mobile else 24
        icon_size = 18 if self.is_mobile else 20
        return ft.Container(
            content=ft.Row([
                ft.IconButton(
                    icon=ft.Icons.ARROW_BACK,
                    icon_color="#f8d7da",
                    icon_size=icon_size,
                    on_click=lambda e: self.on_back() if self.on_back else self._fallback_back(),
                    tooltip="Back to Wallet"
                ),
                icon_label(
                    "settings",
                    "Wallet Settings",
                    size=20,
                    color="#f8d7da",
                    text_size=title_size,
                    text_weight=ft.FontWeight.BOLD,
                ),
                ft.IconButton(
                    icon=ft.Icons.SAVE,
                    icon_color="#28a745",
                    icon_size=icon_size,
                    on_click=self.save_settings_click,
                    tooltip="Save Settings"
                ),
                ft.Container(expand=True),
            ]),
            padding=ft.padding.only(bottom=10)
        )

    def _fallback_back(self):
        try:
            if hasattr(self.app, "show_wallet_page"):
                self.app.show_wallet_page(reuse=True)
                return
        except Exception:
            pass

    def create_blockchain_section(self):
        card_padding = 10 if self.is_mobile else 15
        title_size = 14 if self.is_mobile else 16
        return ft.Container(
            content=ft.Column([
                icon_label(
                    "database",
                    "Blockchain Management",
                    size=16,
                    color="#f8d7da",
                    text_size=title_size + 2,
                    text_weight=ft.FontWeight.BOLD,
                ),
                ft.Divider(color="#5c2e2e", height=20),

                # Cache statistics
                ft.Container(
                    content=ft.Column([
                        ft.Text("Cache Statistics", size=title_size, color="#f8d7da", weight="bold"),
                        ft.Row([
                            ft.Text("Cache Size:", color="#f8d7da"),
                            self.cache_size_text
                        ]),
                        ft.Row([
                            ft.Text("Oldest Cache Entry:", color="#f8d7da"),
                            self.cache_age_text
                        ]),
                        ft.Row([
                            ft.Text("Last Cleanup:", color="#f8d7da"),
                            self.last_cleanup_text
                        ]),
                        ft.ElevatedButton(
                            content=icon_label("refresh-cw", "Refresh Stats", size=16, color="#ffffff", text_size=14),
                            on_click=self.refresh_cache_stats,
                            style=ft.ButtonStyle(
                                color="#ffffff",
                                bgcolor="#dc3545",
                                padding=10
                            )
                        )
                    ]),
                    padding=card_padding,
                    bgcolor="#1a0f0f",
                    border_radius=10,
                    margin=ft.margin.only(bottom=15)
                ),

                # Pruning settings
                ft.Container(
                    content=ft.Column([
                        ft.Text("Blockchain Pruning", size=title_size, color="#f8d7da", weight="bold"),
                        ft.Row([
                            ft.Switch(
                                value=self.cache_settings['blockchain_pruning_enabled'],
                                on_change=lambda e: self.update_setting('blockchain_pruning_enabled', e.control.value)
                            ),
                            ft.Text("Enable Pruning", color="#f8d7da")
                        ], spacing=8),
                        ft.Row([
                            ft.Text("Max Cache Age (days):", color="#f8d7da"),
                            ft.TextField(
                                value=str(self.cache_settings['max_cache_age_days']),
                                width=100,
                                on_change=lambda e: self.update_setting('max_cache_age_days', int(e.control.value) if e.control.value.isdigit() else 30)
                            )
                        ]),
                        ft.Row([
                            ft.Text("Max Cache Size (MB):", color="#f8d7da"),
                            ft.TextField(
                                value=str(self.cache_settings['max_cache_size_mb']),
                                width=100,
                                on_change=lambda e: self.update_setting('max_cache_size_mb', int(e.control.value) if e.control.value.isdigit() else 100)
                            )
                        ]),
                        ft.Row([
                            ft.Switch(
                                value=self.cache_settings['auto_cleanup_enabled'],
                                on_change=lambda e: self.update_setting('auto_cleanup_enabled', e.control.value)
                            ),
                            ft.Text("Auto Cleanup Enabled", color="#f8d7da")
                        ], spacing=8),
                        ft.ElevatedButton(
                            content=icon_label("trash-2", "Clean Old Cache", size=16, color="#ffffff", text_size=14),
                            on_click=self.clean_cache_click,
                            style=ft.ButtonStyle(
                                color="#ffffff",
                                bgcolor="#dc3545",
                                padding=10
                            )
                        ),
                        ft.ElevatedButton(
                            content=icon_label("refresh-cw", "Full Rescan", size=16, color="#ffffff", text_size=14),
                            on_click=self.force_rescan_click,
                            style=ft.ButtonStyle(
                                color="#ffffff",
                                bgcolor="#b33a3a",
                                padding=10
                            )
                        )
                    ]),
                    padding=card_padding,
                    bgcolor="#1a0f0f",
                    border_radius=10
                )
            ]),
            padding=5
        )

    def create_runtime_section(self):
        card_padding = 10 if self.is_mobile else 15
        title_size = 14 if self.is_mobile else 16
        field_width = 320 if self.is_mobile else 420
        return ft.Container(
            content=ft.Column([
                icon_label(
                    "settings",
                    "Runtime & Formatting",
                    size=16,
                    color="#f8d7da",
                    text_size=title_size + 2,
                    text_weight=ft.FontWeight.BOLD,
                ),
                ft.Divider(color="#5c2e2e", height=20),
                ft.Container(
                    content=ft.Column([
                        ft.Text("Luna Display Decimals", size=title_size, color="#f8d7da", weight="bold"),
                        ft.Row([
                            ft.Switch(
                                value=self.runtime_settings['flat_lkc_display'],
                                on_change=lambda e: self.update_runtime_setting('flat_lkc_display', e.control.value)
                            ),
                            ft.Text("Flat LKC Display", color="#f8d7da")
                        ], spacing=8),
                        ft.Row([
                            ft.Switch(
                                value=self.runtime_settings['enable_big_decimals'],
                                on_change=lambda e: self.update_runtime_setting('enable_big_decimals', e.control.value)
                            ),
                            ft.Text("Enable Big Decimals", color="#f8d7da")
                        ], spacing=8),
                        ft.Row([
                            ft.Text("Luna Big Decimals:", color="#f8d7da"),
                            ft.TextField(
                                value=str(self.runtime_settings['luna_big_decimals']),
                                width=100,
                                on_change=lambda e: self.update_runtime_setting('luna_big_decimals', self._safe_int(e.control.value, 8))
                            )
                        ]),
                        ft.Row([
                            ft.Switch(
                                value=self.runtime_settings['enable_small_decimals'],
                                on_change=lambda e: self.update_runtime_setting('enable_small_decimals', e.control.value)
                            ),
                            ft.Text("Enable Small Decimals", color="#f8d7da")
                        ], spacing=8),
                        ft.Row([
                            ft.Text("Luna Small Decimals:", color="#f8d7da"),
                            ft.TextField(
                                value=str(self.runtime_settings['luna_small_decimals']),
                                width=100,
                                on_change=lambda e: self.update_runtime_setting('luna_small_decimals', self._safe_int(e.control.value, 4))
                            )
                        ]),
                        ft.Row([
                            ft.Switch(
                                value=self.runtime_settings['enable_tiny_decimals'],
                                on_change=lambda e: self.update_runtime_setting('enable_tiny_decimals', e.control.value)
                            ),
                            ft.Text("Enable Tiny Decimals", color="#f8d7da")
                        ], spacing=8),
                        ft.Row([
                            ft.Text("Luna Tiny Decimals:", color="#f8d7da"),
                            ft.TextField(
                                value=str(self.runtime_settings['luna_tiny_decimals']),
                                width=100,
                                on_change=lambda e: self.update_runtime_setting('luna_tiny_decimals', self._safe_int(e.control.value, 2))
                            )
                        ]),
                        ft.Text("Sync URL", size=title_size, color="#f8d7da", weight="bold"),
                        ft.TextField(
                            value=str(self.runtime_settings['sync_url']),
                            width=field_width,
                            on_change=lambda e: self.update_runtime_setting('sync_url', e.control.value.strip()),
                            hint_text="https://bank.linglin.art"
                        ),
                    ]),
                    padding=card_padding,
                    bgcolor="#1a0f0f",
                    border_radius=10
                )
            ]),
            padding=5
        )

    def create_security_section(self):
        card_padding = 10 if self.is_mobile else 15
        biometric_supported = bool(getattr(self.app, "is_biometric_available", lambda: False)())
        biometric_ready = bool(getattr(self.app, "is_biometric_ready", lambda: False)())

        controls = [
            icon_label(
                "shield",
                "Security",
                size=16,
                color="#f8d7da",
                text_size=18,
                text_weight=ft.FontWeight.BOLD,
            ),
            ft.Divider(color="#5c2e2e", height=20),
        ]

        if biometric_ready:
            controls.extend([
                ft.Row([
                    ft.Switch(
                        value=self.security_settings['biometric_enabled'],
                        on_change=lambda e: self.update_security_setting('biometric_enabled', e.control.value),
                    ),
                    ft.Text("Enable biometric unlock", color="#f8d7da"),
                ], spacing=8),
                ft.Text(
                    "Biometric unlock uses device authentication and secure storage.",
                    size=12,
                    color="#a89a9a",
                ),
            ])
        else:
            status_text = "Biometric storage not available on this build."
            if biometric_supported:
                status_text = "Biometric storage needs verification on this device."
            controls.append(ft.Text(status_text, size=12, color="#a89a9a"))
            if biometric_supported:
                controls.append(
                    ft.ElevatedButton(
                        content=icon_label("check", "Check biometrics", size=16, color="#ffffff", text_size=14),
                        on_click=self.check_biometrics_click,
                        style=ft.ButtonStyle(
                            color="#ffffff",
                            bgcolor="#dc3545",
                            padding=10
                        )
                    )
                )

        return ft.Container(
            content=ft.Column(controls),
            padding=card_padding
        )

    def _build_wallet_options(self):
        options = []
        wallets = getattr(self.app, "wallet_core", None)
        wallets_dict = getattr(wallets, "wallets", {}) if wallets else {}
        if isinstance(wallets_dict, dict):
            for address, data in wallets_dict.items():
                label = None
                if isinstance(data, dict):
                    label = data.get("label")
                display_label = label.strip() if isinstance(label, str) and label.strip() else address
                if address and len(address) > 12:
                    display_label = f"{display_label} ({address[:12]}...)"
                options.append(ft.dropdown.Option(key=address, text=display_label))
        return options

    def _resolve_initial_wallet_value(self):
        if self.initial_wallet_address:
            return self.initial_wallet_address
        try:
            wallet_core = getattr(self.app, "wallet_core", None)
            current_addr = getattr(wallet_core, "current_wallet_address", None) if wallet_core else None
            if current_addr:
                return current_addr
        except Exception:
            pass
        return None

    def create_wallet_section(self):
        card_padding = 10 if self.is_mobile else 15
        title_size = 14 if self.is_mobile else 16
        field_width = 320 if self.is_mobile else 420

        options = self._build_wallet_options()
        self.initial_wallet_dropdown = ft.Dropdown(
            label="Initial Wallet",
            options=options,
            value=self._resolve_initial_wallet_value(),
            width=field_width,
            bgcolor="#1a0f0f",
            border_color="#5c2e2e",
            focused_border_color="#dc3545",
            color="#f8d7da",
            label_style=ft.TextStyle(color="#f8d7da"),
            text_style=ft.TextStyle(color="#f8d7da"),
        )

        return ft.Container(
            content=ft.Column([
                icon_label(
                    "key",
                    "Initial Wallet",
                    size=16,
                    color="#f8d7da",
                    text_size=title_size + 2,
                    text_weight=ft.FontWeight.BOLD,
                ),
                ft.Divider(color="#5c2e2e", height=20),
                ft.Container(
                    content=ft.Column([
                        ft.Text(
                            "Select the wallet used to unlock all wallets on startup.",
                            size=12,
                            color="#a89a9a",
                        ),
                        self.initial_wallet_dropdown,
                        ft.ElevatedButton(
                            content=icon_label("check", "Set Initial Wallet", size=16, color="#ffffff", text_size=14),
                            on_click=self.set_initial_wallet_click,
                            style=ft.ButtonStyle(
                                color="#ffffff",
                                bgcolor="#dc3545",
                                padding=10
                            )
                        )
                    ]),
                    padding=card_padding,
                    bgcolor="#1a0f0f",
                    border_radius=10
                )
            ]),
            padding=5
        )

    def set_initial_wallet_click(self, e):
        address = None
        if hasattr(self, "initial_wallet_dropdown") and self.initial_wallet_dropdown:
            address = self.initial_wallet_dropdown.value
        if not address:
            self.app.show_snackbar("Please select a wallet", "error")
            return

        updated = False
        if hasattr(self.app, "set_initial_wallet_address"):
            updated = bool(self.app.set_initial_wallet_address(address))
        elif hasattr(self.app, "storage") and self.app.storage:
            try:
                self.app.storage.set("initial_wallet_address", address)
                updated = True
            except Exception:
                updated = False

        if updated:
            self.initial_wallet_address = address
            self.app.show_snackbar("Initial wallet updated", "success")
        else:
            self.app.show_snackbar("Failed to update initial wallet", "error")

    def check_biometrics_click(self, e):
        ready = False
        if hasattr(self.app, "ensure_biometric_ready"):
            ready = bool(self.app.ensure_biometric_ready())
        if ready:
            self.app.show_snackbar("Biometrics ready", "success")
        else:
            self.app.show_snackbar("Biometric storage not supported", "error")
        try:
            if hasattr(self.app, "on_settings"):
                self.app.on_settings()
        except Exception:
            pass

    def create_ui_section(self):
        card_padding = 10 if self.is_mobile else 15
        title_size = 14 if self.is_mobile else 16
        return ft.Container(
            content=ft.Column([
                icon_label(
                    "sliders",
                    "UI Optimizations",
                    size=16,
                    color="#f8d7da",
                    text_size=title_size + 2,
                    text_weight=ft.FontWeight.BOLD,
                ),
                ft.Divider(color="#5c2e2e", height=20),

                ft.Container(
                    content=ft.Column([
                        ft.Row([
                            ft.Switch(
                                value=self.cache_settings['background_sync_enabled'],
                                on_change=lambda e: self.update_setting('background_sync_enabled', e.control.value)
                            ),
                            ft.Text("Background Sync Enabled", color="#f8d7da")
                        ], spacing=8),
                        ft.Text("Enable background blockchain synchronization", size=12, color="#888"),

                        ft.Row([
                            ft.Switch(
                                value=self.cache_settings['batch_transaction_updates'],
                                on_change=lambda e: self.update_setting('batch_transaction_updates', e.control.value)
                            ),
                            ft.Text("Batch Transaction Updates", color="#f8d7da")
                        ], spacing=8),
                        ft.Text("Update multiple transactions at once for better performance", size=12, color="#888"),
                    ]),
                    padding=card_padding,
                    bgcolor="#1a0f0f",
                    border_radius=10
                )
            ]),
            padding=5
        )

    def create_transaction_section(self):
        card_padding = 10 if self.is_mobile else 15
        title_size = 14 if self.is_mobile else 16
        return ft.Container(
            content=ft.Column([
                icon_label(
                    "dollar-sign",
                    "Transaction Management",
                    size=16,
                    color="#f8d7da",
                    text_size=title_size + 2,
                    text_weight=ft.FontWeight.BOLD,
                ),
                ft.Divider(color="#5c2e2e", height=20),

                ft.Container(
                    content=ft.Column([
                        ft.Text("Mempool Management", size=title_size, color="#f8d7da", weight="bold"),
                        ft.Row([
                            ft.Text("Mempool Cleanup (hours):", color="#f8d7da"),
                            ft.TextField(
                                value=str(self.cache_settings['mempool_cleanup_hours']),
                                width=100,
                                on_change=lambda e: self.update_setting('mempool_cleanup_hours', int(e.control.value) if e.control.value.isdigit() else 2)
                            )
                        ]),
                        ft.ElevatedButton(
                            content=icon_label("trash", "Clean Mempool", size=16, color="#ffffff", text_size=14),
                            on_click=self.clean_mempool_click,
                            style=ft.ButtonStyle(
                                color="#ffffff",
                                bgcolor="#dc3545",
                                padding=10
                            )
                        ),
                        ft.ElevatedButton(
                            content=icon_label("refresh-cw", "Force Transaction Sync", size=16, color="#ffffff", text_size=14),
                            on_click=self.force_sync_click,
                            style=ft.ButtonStyle(
                                color="#ffffff",
                                bgcolor="#28a745",
                                padding=10
                            )
                        )
                    ]),
                    padding=card_padding,
                    bgcolor="#1a0f0f",
                    border_radius=10
                )
            ]),
            padding=5
        )

    def create_actions_section(self):
        return ft.Container(
            content=ft.Row([
                ft.ElevatedButton(
                    content=icon_label("save", "Save Settings", size=16, color="#ffffff", text_size=14),
                    on_click=self.save_settings_click,
                    style=ft.ButtonStyle(
                        color="#ffffff",
                        bgcolor="#28a745",
                        padding=ft.padding.symmetric(horizontal=20, vertical=12)
                    )
                ),
                ft.Container(width=10),
                ft.ElevatedButton(
                    content=icon_label("rotate-ccw", "Reset to Defaults", size=16, color="#ffffff", text_size=14),
                    on_click=self.reset_defaults_click,
                    style=ft.ButtonStyle(
                        color="#ffffff",
                        bgcolor="#6c757d",
                        padding=ft.padding.symmetric(horizontal=20, vertical=12)
                    )
                )
            ], alignment=ft.MainAxisAlignment.CENTER),
            padding=20
        )

    def update_setting(self, key, value):
        """Update a setting value"""
        self.cache_settings[key] = value

    def update_runtime_setting(self, key, value):
        self.runtime_settings[key] = value

    def update_security_setting(self, key, value):
        self.security_settings[key] = value

    def _safe_int(self, value, default):
        try:
            return int(value)
        except Exception:
            return default

    def refresh_cache_stats(self, e):
        """Refresh cache statistics display"""
        try:
            if hasattr(self.app, 'blockchain_manager') and self.app.blockchain_manager:
                cache = self.app.blockchain_manager.cache

                # Get cache size
                import os
                if os.path.exists(cache.cache_file):
                    size_mb = os.path.getsize(cache.cache_file) / (1024 * 1024)
                    self.cache_size_text.value = ".1f"
                else:
                    self.cache_size_text.value = "0 MB"

                # Get oldest cache entry
                try:
                    import sqlite3
                    conn = sqlite3.connect(cache.cache_file)
                    cursor = conn.cursor()
                    cursor.execute('SELECT MIN(timestamp) FROM blocks')
                    result = cursor.fetchone()
                    conn.close()

                    if result and result[0]:
                        age_days = (time.time() - result[0]) / (24 * 3600)
                        self.cache_age_text.value = ".1f"
                    else:
                        self.cache_age_text.value = "No cached blocks"
                except:
                    self.cache_age_text.value = "Unknown"

                # Get last cleanup time
                try:
                    conn = sqlite3.connect(cache.cache_file)
                    cursor = conn.cursor()
                    cursor.execute('SELECT value FROM cache_meta WHERE key = ?', ('last_cleanup',))
                    result = cursor.fetchone()
                    conn.close()

                    if result and result[0]:
                        cleanup_time = datetime.fromtimestamp(float(result[0]))
                        self.last_cleanup_text.value = cleanup_time.strftime("%Y-%m-%d %H:%M")
                    else:
                        self.last_cleanup_text.value = "Never"
                except:
                    self.last_cleanup_text.value = "Unknown"

            self.app.page.update()

        except Exception as ex:
            print(f"Error refreshing cache stats: {ex}")
            self.app.show_snackbar("Error refreshing cache statistics", "error")

    def clean_cache_click(self, e):
        """Clean old cache entries"""
        def clean_task():
            try:
                if hasattr(self.app, 'blockchain_manager') and self.app.blockchain_manager:
                    cache = self.app.blockchain_manager.cache

                    # Clean old blocks
                    cutoff_days = self.cache_settings['max_cache_age_days']
                    cutoff_time = time.time() - (cutoff_days * 24 * 3600)

                    import sqlite3
                    conn = sqlite3.connect(cache.cache_file)
                    cursor = conn.cursor()
                    cursor.execute('DELETE FROM blocks WHERE timestamp < ?', (cutoff_time,))
                    deleted_count = cursor.rowcount

                    # Update last cleanup time
                    cursor.execute('INSERT OR REPLACE INTO cache_meta (key, value) VALUES (?, ?)',
                                 ('last_cleanup', str(time.time())))

                    conn.commit()
                    conn.close()

                    self.app.page.snack_bar = ft.SnackBar(
                        content=ft.Text(f"Cleaned {deleted_count} old cache entries"),
                        bgcolor="#28a745"
                    )
                    self.app.page.snack_bar.open = True
                    self.app.page.update()

                    # Refresh stats
                    self.refresh_cache_stats(None)

            except Exception as ex:
                print(f"Error cleaning cache: {ex}")
                self.app.show_snackbar("Error cleaning cache", "error")

        threading.Thread(target=clean_task, daemon=True).start()
        self.app.show_snackbar("Cache cleanup started...", "info")

    def force_rescan_click(self, e):
        """Force a full blockchain rescan"""
        def rescan_task():
            try:
                if hasattr(self.app, 'force_rescan_blockchain'):
                    self.app.force_rescan_blockchain()
                elif hasattr(self.app, 'scan_all_wallets_for_changes'):
                    self.app.scan_all_wallets_for_changes(force_full_scan=True)
            except Exception as ex:
                print(f"Error forcing rescan: {ex}")
                self.app.show_snackbar("Full rescan failed", "error")

        threading.Thread(target=rescan_task, daemon=True).start()
        self.app.show_snackbar("Full rescan started...", "info")

    def clean_mempool_click(self, e):
        """Clean old mempool transactions"""
        try:
            if hasattr(self.app, 'blockchain_manager') and self.app.blockchain_manager:
                cache = getattr(self.app.blockchain_manager, 'cache', None)
                if cache and hasattr(cache, 'clear_old_mempool'):
                    cache.clear_old_mempool(self.cache_settings['mempool_cleanup_hours'])
                    self.app.show_snackbar("Mempool cleaned successfully", "success")
                else:
                    self.app.show_snackbar("Mempool cleanup not supported", "info")
            else:
                self.app.show_snackbar("Blockchain manager not available", "error")
        except Exception as ex:
            print(f"Error cleaning mempool: {ex}")
            self.app.show_snackbar("Error cleaning mempool", "error")

    def force_sync_click(self, e):
        """Force transaction synchronization"""
        try:
            if hasattr(self.app, 'update_wallet_data'):
                self.app.update_wallet_data()
                self.app.show_snackbar("Transaction sync initiated", "success")
                return
            if hasattr(self.app, 'scan_all_wallets_for_changes'):
                self.app.scan_all_wallets_for_changes()
                self.app.show_snackbar("Transaction sync initiated", "success")
                return
            if hasattr(self.app, 'start_blockchain_sync'):
                self.app.start_blockchain_sync()
                self.app.show_snackbar("Blockchain sync started", "success")
                return
            self.app.show_snackbar("Sync method not available", "error")
        except Exception as ex:
            print(f"Error forcing sync: {ex}")
            self.app.show_snackbar("Error initiating sync", "error")

    def save_settings_click(self, e):
        """Save settings"""
        self.save_settings()

    def reset_defaults_click(self, e):
        """Reset settings to defaults"""
        self.cache_settings = {
            'max_cache_age_days': 30,
            'max_cache_size_mb': 100,
            'auto_cleanup_enabled': True,
            'background_sync_enabled': True,
            'mempool_cleanup_hours': 2,
            'batch_transaction_updates': True,
            'blockchain_pruning_enabled': True
        }
        self.runtime_settings = {
            'luna_big_decimals': 8,
            'luna_small_decimals': 4,
            'luna_tiny_decimals': 2,
            'sync_url': "",
            'enable_big_decimals': True,
            'enable_small_decimals': True,
            'enable_tiny_decimals': True,
            'flat_lkc_display': False
        }
        self.app.show_snackbar("Settings reset to defaults", "info")
        # Would need to refresh UI to show default values
        self.app.page.update()
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
        return ft.Container(
            content=ft.Column([
                self.create_header(),
                ft.Container(height=20),
                self.create_blockchain_section(),
                ft.Container(height=20),
                self.create_runtime_section(),
                ft.Container(height=20),
                self.create_ui_section(),
                ft.Container(height=20),
                self.create_transaction_section(),
                ft.Container(height=20),
                self.create_actions_section(),
            ], scroll=ft.ScrollMode.ADAPTIVE),
            expand=True,
            padding=20,
            bgcolor="#2c1a1a"
        )

    def create_header(self):
        return ft.Container(
            content=ft.Row([
                ft.IconButton(
                    icon=ft.Icons.ARROW_BACK,
                    icon_color="#f8d7da",
                    on_click=lambda e: self.on_back() if self.on_back else self._fallback_back(),
                    tooltip="Back to Wallet"
                ),
                icon_label(
                    "settings",
                    "Wallet Settings",
                    size=20,
                    color="#f8d7da",
                    text_size=24,
                    text_weight=ft.FontWeight.BOLD,
                ),
                ft.IconButton(
                    icon=ft.Icons.SAVE,
                    icon_color="#28a745",
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
        return ft.Container(
            content=ft.Column([
                icon_label(
                    "database",
                    "Blockchain Management",
                    size=16,
                    color="#f8d7da",
                    text_size=18,
                    text_weight=ft.FontWeight.BOLD,
                ),
                ft.Divider(color="#5c2e2e", height=20),

                # Cache statistics
                ft.Container(
                    content=ft.Column([
                        ft.Text("Cache Statistics", size=16, color="#f8d7da", weight="bold"),
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
                    padding=15,
                    bgcolor="#1a0f0f",
                    border_radius=10,
                    margin=ft.margin.only(bottom=15)
                ),

                # Pruning settings
                ft.Container(
                    content=ft.Column([
                        ft.Text("Blockchain Pruning", size=16, color="#f8d7da", weight="bold"),
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
                        )
                    ]),
                    padding=15,
                    bgcolor="#1a0f0f",
                    border_radius=10
                )
            ]),
            padding=5
        )

    def create_runtime_section(self):
        return ft.Container(
            content=ft.Column([
                icon_label(
                    "settings",
                    "Runtime & Formatting",
                    size=16,
                    color="#f8d7da",
                    text_size=18,
                    text_weight=ft.FontWeight.BOLD,
                ),
                ft.Divider(color="#5c2e2e", height=20),
                ft.Container(
                    content=ft.Column([
                        ft.Text("Luna Display Decimals", size=16, color="#f8d7da", weight="bold"),
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
                        ft.Text("Sync URL", size=16, color="#f8d7da", weight="bold"),
                        ft.TextField(
                            value=str(self.runtime_settings['sync_url']),
                            width=420,
                            on_change=lambda e: self.update_runtime_setting('sync_url', e.control.value.strip()),
                            hint_text="https://bank.linglin.art"
                        ),
                    ]),
                    padding=15,
                    bgcolor="#1a0f0f",
                    border_radius=10
                )
            ]),
            padding=5
        )

    def create_ui_section(self):
        return ft.Container(
            content=ft.Column([
                icon_label(
                    "sliders",
                    "UI Optimizations",
                    size=16,
                    color="#f8d7da",
                    text_size=18,
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
                    padding=15,
                    bgcolor="#1a0f0f",
                    border_radius=10
                )
            ]),
            padding=5
        )

    def create_transaction_section(self):
        return ft.Container(
            content=ft.Column([
                icon_label(
                    "dollar-sign",
                    "Transaction Management",
                    size=16,
                    color="#f8d7da",
                    text_size=18,
                    text_weight=ft.FontWeight.BOLD,
                ),
                ft.Divider(color="#5c2e2e", height=20),

                ft.Container(
                    content=ft.Column([
                        ft.Text("Mempool Management", size=16, color="#f8d7da", weight="bold"),
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
                    padding=15,
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
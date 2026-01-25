import flet as ft
from gui.icon_utils import icon_label
import threading
import time
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
            'batch_transaction_updates': True
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
        except Exception as e:
            print(f"Error loading settings: {e}")

    def save_settings(self):
        """Save settings to database"""
        try:
            if hasattr(self.app, 'database') and self.app.database:
                self.app.database.save_settings(self.cache_settings)
                self.app.show_snackbar("Settings saved successfully", "success")
            else:
                self.app.show_snackbar("Unable to save settings - no database available", "error")
        except Exception as e:
            print(f"Error saving settings: {e}")
            self.app.show_snackbar(f"Error saving settings: {e}", "error")

    def create(self):
        return ft.Container(
            content=ft.Column([
                self.create_header(),
                ft.Container(height=20),
                self.create_blockchain_section(),
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
                    on_click=lambda e: self.on_back() if self.on_back else None,
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
                ft.Container(expand=True),
                ft.IconButton(
                    icon=ft.Icons.SAVE,
                    icon_color="#28a745",
                    on_click=self.save_settings_click,
                    tooltip="Save Settings"
                ),
            ]),
            padding=ft.padding.only(bottom=10)
        )

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
                        ft.Switch(
                            label="Auto Cleanup Enabled",
                            value=self.cache_settings['auto_cleanup_enabled'],
                            on_change=lambda e: self.update_setting('auto_cleanup_enabled', e.control.value),
                            label_style=ft.TextStyle(color="#f8d7da")
                        ),
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
                        ft.Switch(
                            label="Background Sync Enabled",
                            value=self.cache_settings['background_sync_enabled'],
                            on_change=lambda e: self.update_setting('background_sync_enabled', e.control.value),
                            label_style=ft.TextStyle(color="#f8d7da")
                        ),
                        ft.Text("Enable background blockchain synchronization", size=12, color="#888"),

                        ft.Switch(
                            label="Batch Transaction Updates",
                            value=self.cache_settings['batch_transaction_updates'],
                            on_change=lambda e: self.update_setting('batch_transaction_updates', e.control.value),
                            label_style=ft.TextStyle(color="#f8d7da")
                        ),
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
                cache = self.app.blockchain_manager.cache
                cache.clear_old_mempool(self.cache_settings['mempool_cleanup_hours'])
                self.app.show_snackbar("Mempool cleaned successfully", "success")
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
            else:
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
            'batch_transaction_updates': True
        }
        self.app.show_snackbar("Settings reset to defaults", "info")
        # Would need to refresh UI to show default values
        self.app.page.update()
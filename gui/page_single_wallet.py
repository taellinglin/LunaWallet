import flet as ft
from gui.page_wallet import WalletPage


class SingleWalletPage:
    def __init__(self, app, on_back=None):
        self.app = app
        self.on_back = on_back

    def create(self):
        wallet_page = WalletPage(
            app=self.app,
            on_send=self.app.on_send_transaction,
            on_receive=self.app.on_receive,
            on_export_key=self.app.on_export_key,
            on_lock=self.app.on_lock,
            on_create_wallet=self.app.on_create_wallet,
            on_import_wallet=self.app.on_import_wallet,
            on_settings=self.app.on_settings,
            show_back=True,
            on_back=self.on_back,
            show_sidebar_button=False,
        )
        return wallet_page.create()

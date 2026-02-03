import flet as ft


class WalletIndexPage:
    def __init__(self, app, on_select_wallet, on_create_wallet, on_import_wallet):
        self.app = app
        self.on_select_wallet = on_select_wallet
        self.on_create_wallet = on_create_wallet
        self.on_import_wallet = on_import_wallet

    def create(self):
        wallets = []
        if hasattr(self.app, "wallet_core") and getattr(self.app.wallet_core, "wallets", None):
            if isinstance(self.app.wallet_core.wallets, dict):
                for address, wdata in self.app.wallet_core.wallets.items():
                    label = wdata.get("label") if isinstance(wdata, dict) else None
                    wallets.append({"address": address, "label": label or address})

        wallet_list = ft.ListView(spacing=8, expand=True)
        for w in wallets:
            display = w["label"]
            if len(display) > 20:
                display = f"{display[:10]}...{display[-6:]}"
            wallet_list.controls.append(
                ft.Container(
                    content=ft.Row(
                        [
                            ft.Container(
                                content=ft.Text(display[:1].upper(), color="#ffffff", weight="bold"),
                                width=36,
                                height=36,
                                bgcolor="#dc3545",
                                border_radius=18,
                                alignment=ft.Alignment(0, 0),
                            ),
                            ft.Column(
                                [
                                    ft.Text(display, color="#f8d7da", size=14, weight="bold"),
                                    ft.Text(w["address"], color="#a8a8a8", size=10),
                                ],
                                spacing=2,
                                expand=True,
                            ),
                            ft.Icon(ft.Icons.CHEVRON_RIGHT, color="#f8d7da"),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    padding=12,
                    bgcolor="#1a0f0f",
                    border_radius=10,
                    border=ft.border.all(1, "#5c2e2e"),
                    on_click=lambda e, addr=w["address"]: self.on_select_wallet(addr),
                )
            )

        if not wallets:
            wallet_list.controls.append(
                ft.Container(
                    content=ft.Text("No wallets yet", color="#a8a8a8", size=12),
                    alignment=ft.Alignment(0, 0),
                    padding=20,
                )
            )

        actions = ft.Row(
            [
                ft.ElevatedButton(
                    "Create Wallet",
                    icon=ft.Icons.ADD_CIRCLE_OUTLINE,
                    on_click=lambda e: self.on_create_wallet(),
                    style=ft.ButtonStyle(
                        color="#ffffff",
                        bgcolor="#dc3545",
                        padding=ft.padding.symmetric(horizontal=16, vertical=12),
                        shape=ft.RoundedRectangleBorder(radius=8),
                    ),
                ),
                ft.OutlinedButton(
                    "Import",
                    icon=ft.Icons.IMPORT_EXPORT,
                    on_click=lambda e: self.on_import_wallet(),
                    style=ft.ButtonStyle(
                        color="#dc3545",
                        side=ft.BorderSide(color="#dc3545", width=2),
                        padding=ft.padding.symmetric(horizontal=16, vertical=12),
                        shape=ft.RoundedRectangleBorder(radius=8),
                    ),
                ),
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=12,
        )

        return ft.Container(
            content=ft.Column(
                [
                    ft.Text("Wallets", size=20, weight="bold", color="#f8d7da"),
                    ft.Text("Select a wallet", size=12, color="#a8a8a8"),
                    ft.Container(height=10),
                    wallet_list,
                    ft.Container(height=10),
                    actions,
                ],
                expand=True,
                spacing=12,
                scroll=ft.ScrollMode.ADAPTIVE,
            ),
            expand=True,
            padding=16,
            bgcolor="#2c1a1a",
        )

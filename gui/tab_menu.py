import flet as ft

class MenuTab:
    def __init__(self, is_mobile=False, on_sync=None, on_lock=None, on_about=None, on_export_key=None, on_receive=None, on_send=None):
        self.is_mobile = is_mobile
        self.on_sync = on_sync
        self.on_lock = on_lock
        self.on_about = on_about
        self.on_export_key = on_export_key
        self.on_receive = on_receive
        self.on_send = on_send
        
    def create_tab_content(self):
        if self.is_mobile:
            return self.create_mobile_content()
        else:
            return self.create_desktop_content()
    
    def create_mobile_content(self):
        menu_items = ft.Column([
            ft.ListTile(
                leading=ft.Icon(ft.Icons.DOWNLOAD, color="#dc3545", size=30),
                title=ft.Text("Receive", color="#f8d7da", size=18),
                subtitle=ft.Text("Receive Luna coins", color="#f8d7da", size=14),
                on_click=lambda e: self.on_receive() if self.on_receive else None
            ),
            ft.ListTile(
                leading=ft.Icon(ft.Icons.UPLOAD, color="#dc3545", size=30),
                title=ft.Text("Send", color="#f8d7da", size=18),
                subtitle=ft.Text("Send Luna coins", color="#f8d7da", size=14),
                on_click=lambda e: self.on_send() if self.on_send else None
            ),
            ft.ListTile(
                leading=ft.Icon(ft.Icons.SYNC, color="#dc3545", size=30),
                title=ft.Text("Sync Wallet", color="#f8d7da", size=18),
                subtitle=ft.Text("Synchronize with blockchain", color="#f8d7da", size=14),
                on_click=lambda e: self.on_sync() if self.on_sync else None
            ),
            ft.ListTile(
                leading=ft.Icon(ft.Icons.KEY, color="#dc3545", size=30),
                title=ft.Text("Export Private Key", color="#f8d7da", size=18),
                subtitle=ft.Text("Export wallet private key", color="#f8d7da", size=14),
                on_click=lambda e: self.on_export_key() if self.on_export_key else None
            ),
            ft.ListTile(
                leading=ft.Icon(ft.Icons.LOCK, color="#dc3545", size=30),
                title=ft.Text("Lock Wallet", color="#f8d7da", size=18),
                subtitle=ft.Text("Lock your wallet for security", color="#f8d7da", size=14),
                on_click=lambda e: self.on_lock() if self.on_lock else None
            ),
            ft.ListTile(
                leading=ft.Icon(ft.Icons.INFO, color="#dc3545", size=30),
                title=ft.Text("About", color="#f8d7da", size=18),
                subtitle=ft.Text("About Luna Wallet", color="#f8d7da", size=14),
                on_click=lambda e: self.on_about() if self.on_about else None
            ),
        ], spacing=5)
        
        return ft.Container(
            content=ft.Column([
                ft.Text("Menu", size=24, color="#f8d7da", weight="bold"),
                ft.Divider(color="#5c2e2e", height=20),
                menu_items,
                ft.Container(expand=True),
            ], scroll=ft.ScrollMode.ADAPTIVE),
            expand=True,
            padding=20,
            bgcolor="#2c1a1a"
        )
    
    def create_desktop_content(self):
        quick_actions = ft.Column([
            ft.Text("Quick Actions", size=18, color="#f8d7da", weight="bold"),
            ft.ElevatedButton(
                "📥 Receive",
                on_click=lambda _: self.on_receive() if self.on_receive else None,
                style=ft.ButtonStyle(
                    color="#ffffff",
                    bgcolor="#dc3545",
                    padding=ft.padding.symmetric(horizontal=20, vertical=12),
                    shape=ft.RoundedRectangleBorder(radius=6)
                ),
                height=45
            ),
            ft.ElevatedButton(
                "📤 Send",
                on_click=lambda _: self.on_send() if self.on_send else None,
                style=ft.ButtonStyle(
                    color="#ffffff",
                    bgcolor="#dc3545",
                    padding=ft.padding.symmetric(horizontal=20, vertical=12),
                    shape=ft.RoundedRectangleBorder(radius=6)
                ),
                height=45
            ),
            ft.ElevatedButton(
                "🔄 Sync",
                on_click=lambda _: self.on_sync() if self.on_sync else None,
                style=ft.ButtonStyle(
                    color="#ffffff",
                    bgcolor="#dc3545",
                    padding=ft.padding.symmetric(horizontal=20, vertical=12),
                    shape=ft.RoundedRectangleBorder(radius=6)
                ),
                height=45
            ),
            ft.ElevatedButton(
                "🔑 Export Key",
                on_click=lambda _: self.on_export_key() if self.on_export_key else None,
                style=ft.ButtonStyle(
                    color="#ffffff",
                    bgcolor="#dc3545",
                    padding=ft.padding.symmetric(horizontal=20, vertical=12),
                    shape=ft.RoundedRectangleBorder(radius=6)
                ),
                height=45
            ),
            ft.ElevatedButton(
                "🔒 Lock",
                on_click=lambda _: self.on_lock() if self.on_lock else None,
                style=ft.ButtonStyle(
                    color="#ffffff",
                    bgcolor="#6c757d",
                    padding=ft.padding.symmetric(horizontal=20, vertical=12),
                    shape=ft.RoundedRectangleBorder(radius=6)
                ),
                height=45
            ),
        ], spacing=12)
        
        return ft.Container(
            content=ft.Column([
                ft.Text("Menu & Actions", size=20, color="#f8d7da"),
                quick_actions,
                ft.Container(expand=True),
            ], expand=True),
            padding=15,
            bgcolor="#2c1a1a"
        )
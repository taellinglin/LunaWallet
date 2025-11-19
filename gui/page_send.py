import flet as ft

class SendPage:
    def __init__(self, app, on_back, on_send_complete, from_address=None):
        self.app = app
        self.on_back = on_back
        self.on_send_complete = on_send_complete
        self.from_address = from_address
        
        # Form fields
        field_width = 400 if not app.is_mobile else 300
        self.recipient = ft.TextField(
            label="👤 Recipient Address", hint_text="Enter Luna address", width=field_width
        )
        self.amount = ft.TextField(
            label="💰 Amount (LUNA)", hint_text="0.00", width=field_width
        )
        self.memo = ft.TextField(
            label="📝 Memo (Optional)", hint_text="Add a note", width=field_width
        )
        self.password = ft.TextField(
            label="🔒 Confirm Password", password=True, can_reveal_password=True,
            hint_text="Enter your password", width=field_width
        )
        
    def create(self):
        balance = self.get_current_balance()
        
        return ft.Container(
            content=ft.Column([
                # Header
                ft.Row([
                    ft.IconButton(ft.Icons.ARROW_BACK, icon_color="#f8d7da", on_click=lambda e: self.on_back()),
                    ft.Text("📤 Send Luna", size=24, weight="bold", color="#f8d7da"),
                    ft.Container(expand=True)
                ]),
                ft.Divider(color="#5c2e2e"),
                
                # Centered form container
                ft.Container(
                    content=ft.Column([
                        ft.Text(f"💰 Available: {balance:.6f} LUNA", size=16, color="#90EE90"),
                        ft.Container(height=20),
                        self.recipient,
                        self.amount,
                        self.memo,
                        self.password,
                        ft.Container(height=20),
                        ft.ElevatedButton(
                            "🚀 Send Transaction", on_click=self.send_transaction,
                            style=ft.ButtonStyle(color="#ffffff", bgcolor="#dc3545", padding=20),
                            width=200
                        )
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                    padding=20,
                    margin=15,
                    bgcolor="#1a0f0f",
                    border_radius=15,
                    alignment=ft.alignment.center,
                    expand=True
                )
            ]),
            expand=True,
            padding=10,
            bgcolor="#2c1a1a",
            alignment=ft.alignment.center
        )
    
    def get_current_balance(self):
        try:
            if self.from_address and hasattr(self.app.wallet_core, 'wallets'):
                if isinstance(self.app.wallet_core.wallets, dict) and self.from_address in self.app.wallet_core.wallets:
                    return self.app.wallet_core.wallets[self.from_address].get('balance', 0)
                elif isinstance(self.app.wallet_core.wallets, list):
                    for wallet in self.app.wallet_core.wallets:
                        if isinstance(wallet, dict) and wallet.get('address') == self.from_address:
                            return wallet.get('balance', 0)
            if hasattr(self.app.wallet_core, 'get_wallet_info'):
                wallet_info = self.app.wallet_core.get_wallet_info()
                return wallet_info.get('balance', 0) if wallet_info else 0
            return 0
        except:
            return 0
    
    def send_transaction(self, e):
        recipient = self.recipient.value.strip()
        amount_str = self.amount.value.strip()
        memo = self.memo.value.strip()
        password = self.password.value
        
        if not recipient:
            self.app.show_snackbar("Please enter recipient address", "error")
            return
        if not amount_str:
            self.app.show_snackbar("Please enter amount", "error")
            return
        if not password:
            self.app.show_snackbar("Please enter password", "error")
            return
        
        try:
            amount = float(amount_str)
            if amount <= 0:
                self.app.show_snackbar("Amount must be positive", "error")
                return
        except ValueError:
            self.app.show_snackbar("Invalid amount format", "error")
            return
        
        try:
            if self.from_address and hasattr(self.app.wallet_core, 'send_transaction_from'):
                success = self.app.wallet_core.send_transaction_from(self.from_address, recipient, amount, memo, password)
            elif hasattr(self.app.wallet_core, 'send_transaction'):
                success = self.app.wallet_core.send_transaction(recipient, amount, memo, password)
            else:
                success = False
            
            if success:
                self.on_send_complete()
            else:
                self.app.show_snackbar("Failed to send transaction", "error")
        except Exception as ex:
            self.app.show_snackbar(f"Error sending transaction: {str(ex)}", "error")
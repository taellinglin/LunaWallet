import flet as ft

class SendPage:
    def __init__(self, app, on_back, on_send_complete, from_address=None):
        self.app = app
        self.on_back = on_back
        self.on_send_complete = on_send_complete
        self.from_address = from_address
        
        # Form fields
        self.recipient = ft.TextField(
            label="👤 Recipient Address",
            hint_text="Enter Luna address",
            width=400 if not app.is_mobile else 300
        )
        self.amount = ft.TextField(
            label="💰 Amount (LUNA)",
            hint_text="0.00",
            width=400 if not app.is_mobile else 300
        )
        self.memo = ft.TextField(
            label="📝 Memo (Optional)",
            hint_text="Add a note",
            width=400 if not app.is_mobile else 300
        )
        self.password = ft.TextField(
            label="🔒 Confirm Password",
            password=True,
            can_reveal_password=True,
            hint_text="Enter your password",
            width=400 if not app.is_mobile else 300
        )
        
    def create(self):
        # Get current balance from the specific wallet
        balance = self.get_current_balance()
        
        return ft.Container(
            content=ft.Column([
                # Header
                ft.Row([
                    ft.IconButton(
                        icon=ft.Icons.ARROW_BACK,
                        icon_color="#f8d7da",
                        on_click=lambda e: self.on_back()
                    ),
                    ft.Text("📤 Send Luna", size=24, weight="bold", color="#f8d7da"),
                    ft.Container(expand=True)
                ]),
                
                ft.Divider(color="#5c2e2e"),
                
                # Form
                ft.Container(
                    content=ft.Column([
                        ft.Text(f"💰 Available: {balance:.6f} LUNA", size=16, color="#90EE90"),
                        ft.Container(height=20),
                        
                        self.recipient,
                        self.amount,
                        self.memo,
                        self.password,
                        
                        ft.Container(height=30),
                        
                        ft.ElevatedButton(
                            "🚀 Send Transaction",
                            on_click=self.send_transaction,
                            style=ft.ButtonStyle(
                                color="#ffffff",
                                bgcolor="#dc3545",
                                padding=20
                            ),
                            width=200
                        )
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                    padding=20,
                    margin=10,
                    bgcolor="#1a0f0f",
                    border_radius=15,
                    width=500 if not self.app.is_mobile else 350
                )
            ]),
            expand=True,
            padding=20,
            bgcolor="#2c1a1a"
        )
    
    def get_current_balance(self):
        """Get balance for the current wallet"""
        try:
            if self.from_address and hasattr(self.app.wallet_core, 'wallets'):
                # Get balance from specific wallet address
                if isinstance(self.app.wallet_core.wallets, dict) and self.from_address in self.app.wallet_core.wallets:
                    return self.app.wallet_core.wallets[self.from_address].get('balance', 0)
                elif isinstance(self.app.wallet_core.wallets, list):
                    for wallet in self.app.wallet_core.wallets:
                        if isinstance(wallet, dict) and wallet.get('address') == self.from_address:
                            return wallet.get('balance', 0)
            
            # Fallback to general balance check
            if hasattr(self.app.wallet_core, 'get_wallet_info'):
                wallet_info = self.app.wallet_core.get_wallet_info()
                if wallet_info:
                    return wallet_info.get('balance', 0)
            
            return 0
        except:
            return 0
    
    def send_transaction(self, e):
        # Validate form
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
        
        # Send transaction
        try:
            # Use the specific from_address if available
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
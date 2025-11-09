import flet as ft

class SendPage:
    def __init__(self, app, on_back, on_send_complete):
        self.app = app
        self.on_back = on_back
        self.on_send_complete = on_send_complete
        
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
        # Get current balance
        wallet_info = self.app.wallet_core.get_wallet_info()
        balance = wallet_info.get('balance', 0) if wallet_info else 0
        
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
            if self.app.wallet_core.send_transaction(recipient, amount, memo, password):
                self.on_send_complete()
            else:
                self.app.show_snackbar("Failed to send transaction", "error")
        except Exception as ex:
            self.app.show_snackbar(f"Error sending transaction: {str(ex)}", "error")
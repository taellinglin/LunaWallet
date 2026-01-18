import sqlite3
import os

db_path = os.path.join(os.path.expanduser('~'), '.luna_wallet', 'wallet.db')
print(f'Checking database: {db_path}')
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute('SELECT name FROM sqlite_master WHERE type="table"')
    tables = cursor.fetchall()
    print('Tables:', tables)

    if ('transactions',) in tables:
        cursor.execute('SELECT COUNT(*) FROM transactions')
        count = cursor.fetchone()[0]
        print(f'Transactions: {count} records')

        # Look for 5000 amount transactions
        cursor.execute('SELECT * FROM transactions WHERE amount = 5000')
        tx_5000 = cursor.fetchall()
        print(f'5000 amount transactions: {len(tx_5000)}')
        if tx_5000:
            columns = [desc[0] for desc in cursor.description]
            for tx in tx_5000:
                tx_dict = dict(zip(columns, tx))
                print('5000 TX:', tx_dict)
                # Check if it's for the first wallet
                wallets_table = cursor.execute('SELECT address FROM wallets').fetchall()
                if wallets_table:
                    first_wallet = wallets_table[0][0]
                    print(f'First wallet: {first_wallet[:12]}...')
                    tx_to = tx_dict.get('to', '')
                    tx_from = tx_dict.get('from', '')
                    print(f'TX to: {tx_to}, from: {tx_from}')
                    print(f'Matches first wallet? to={tx_to==first_wallet}, from={tx_from==first_wallet}')

    conn.close()
else:
    print('Database not found')
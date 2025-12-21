import ast
import sys

try:
    with open('gui/page_lock.py', encoding='utf-8') as f:
        code = f.read()
    ast.parse(code)
    print('page_lock.py: Syntax OK')
except SyntaxError as e:
    print(f'Syntax error in page_lock.py: {e}')
    sys.exit(1)

try:
    with open('main.py', encoding='utf-8') as f:
        code = f.read()
    ast.parse(code)
    print('main.py: Syntax OK')
except SyntaxError as e:
    print(f'Syntax error in main.py: {e}')
    sys.exit(1)

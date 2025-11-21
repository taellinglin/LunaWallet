# build.spec
block_cipher = None

a = Analysis(
    ['main.py'],  # Your main application file
    pathex=[],
    binaries=[],
    datadesc=[],
    hiddenimports=[
        'flet', 
        'lunalib',
        'pygame',  # Add pygame for sound support
        'PIL',     # Add PIL for image processing
        'PIL._imaging',  # Required for PIL
        'datetime', # Already standard but explicit
        'json',
        'threading',
        'time',
        'os',
        'shutil',
        'base64',
        'typing'
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'pystray', 
        '_ctypes', 
        'ctypes', 
        'infi.systray',
        'sqlite3',  # Explicitly exclude sqlite3
        'tkinter',  # Exclude tkinter if not needed
        'test',     # Exclude test modules
        'unittest'  # Exclude unittest
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# Force remove any unwanted modules
for module in list(a.scripts):
    if any(x in str(module).lower() for x in ['pystray', 'systray', 'tkinter']):
        a.scripts.remove(module)

# Add data files if you have any (icons, sounds, etc.)
datas = []

# If you have sound files, include them
try:
    # Add sounds directory if it exists
    if os.path.exists('./sounds'):
        for sound_file in os.listdir('./sounds'):
            if sound_file.endswith('.wav'):
                datas.append((f'./sounds/{sound_file}', 'sounds'))
except:
    pass

# Add icon files if they exist
try:
    if os.path.exists('./wallet_icon.png'):
        datas.append(('./wallet_icon.png', '.'))
    if os.path.exists('./node_icon.png'):
        datas.append(('./node_icon.png', '.'))
except:
    pass

# Add GUI modules
a.datas += datas

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,  # Keep this for any required binaries
    a.zipfiles,
    a.datas,
    [],  # No additional binaries
    name='LunaWallet',  # Changed to match your app name
    debug=False,
    bootloader_ignore_signals=False,
    strip=True,
    upx=True,
    console=False,  # Set to True if you need to see console output for debugging
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='wallet_icon.png'  # Use your wallet icon
)
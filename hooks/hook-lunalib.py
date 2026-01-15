from PyInstaller.utils.hooks import collect_submodules, collect_data_files

# Include all lunalib submodules and package data
hiddenimports = collect_submodules("lunalib")
datas = collect_data_files("lunalib")

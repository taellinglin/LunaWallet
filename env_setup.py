"""
Environment loader for LunaWallet
Loads variables from .env file and configures the virtual environment
"""

import os
import sys
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:
    print("Installing python-dotenv...")
    os.system(f"{sys.executable} -m pip install python-dotenv")
    from dotenv import load_dotenv

# Load .env file
env_path = Path(__file__).parent / ".env"
if env_path.exists():
    load_dotenv(env_path)
    print(f"✓ Loaded environment from {env_path}")
else:
    print(f"⚠ .env file not found at {env_path}")

# Get environment variables
venv_path = os.getenv("VIRTUAL_ENV", ".venv")
python_path = os.getenv("PYTHON_PATH", os.path.join(venv_path, "Scripts", "python.exe"))
cmake_generator = os.getenv("CMAKE_GENERATOR", "Visual Studio 17 2022")
cmake_platform = os.getenv("CMAKE_GENERATOR_PLATFORM", "x64")
lunalib_cache = os.getenv("LUNALIB_CACHE_DIR", ".lunalib_cache")

# Set environment variables for current process
os.environ["VIRTUAL_ENV"] = venv_path
os.environ["CMAKE_GENERATOR"] = cmake_generator
os.environ["CMAKE_GENERATOR_PLATFORM"] = cmake_platform
os.environ["LUNALIB_CACHE_DIR"] = lunalib_cache
os.environ["PYTHONPATH"] = os.getcwd()

# Print configuration
print("\n" + "="*50)
print("LunaWallet Environment Configuration")
print("="*50)
print(f"Virtual Environment: {venv_path}")
print(f"Python Path: {python_path}")
print(f"CMake Generator: {cmake_generator}")
print(f"CMake Platform: {cmake_platform}")
print(f"LunaLib Cache: {lunalib_cache}")
print(f"Working Directory: {os.getcwd()}")
print("="*50 + "\n")

if __name__ == "__main__":
    print("Environment configured successfully!")
    print(f"Use python_path: {python_path}")

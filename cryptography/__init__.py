"""Local cryptography shim.

Prefer the real `cryptography` package if available so legacy Fernet tokens
can be decrypted on platforms where it is installed (e.g., Windows).
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import os
import sys
from types import ModuleType


def _load_real_cryptography() -> ModuleType | None:
	try:
		current_pkg_dir = os.path.abspath(os.path.dirname(__file__))
		project_root = os.path.abspath(os.path.dirname(current_pkg_dir))

		search_paths = [
			p
			for p in sys.path
			if p
			and os.path.abspath(p) not in (project_root, current_pkg_dir)
		]

		spec = importlib.machinery.PathFinder.find_spec("cryptography", search_paths)
		if spec and spec.loader:
			module = importlib.util.module_from_spec(spec)
			spec.loader.exec_module(module)  # type: ignore[arg-type]
			return module
	except Exception:
		return None
	return None


_real = _load_real_cryptography()
if _real:
	sys.modules[__name__] = _real
	globals().update(_real.__dict__)
else:
	__all__ = ["fernet", "exceptions", "hazmat"]
	__version__ = "0.0.0-local"

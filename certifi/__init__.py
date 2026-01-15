"""Minimal certifi shim for bundled environments."""

from __future__ import annotations

__all__ = ["where", "contents"]
__version__ = "0.0.0-shim"


def where() -> str:
	"""Return a CA bundle path using requests or SSL defaults."""
	try:
		from requests import certs as _certs  # type: ignore

		return _certs.where()
	except Exception:
		try:
			import ssl

			return ssl.get_default_verify_paths().cafile or ""
		except Exception:
			return ""


def contents() -> str:
	"""Return CA bundle contents if available, else empty string."""
	path = where()
	if not path:
		return ""
	try:
		with open(path, "r", encoding="utf-8") as f:
			return f.read()
	except Exception:
		return ""

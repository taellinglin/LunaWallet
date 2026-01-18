"""Minimal certifi shim for bundled environments."""

from __future__ import annotations

import os

__all__ = ["where", "contents"]
__version__ = "0.0.0-shim"


def where() -> str:
	"""Return a CA bundle path using requests or SSL defaults."""
	env_path = os.environ.get("REQUESTS_CA_BUNDLE")
	if env_path and os.path.exists(env_path):
		return env_path
	try:
		import requests

		requests_dir = os.path.dirname(getattr(requests, "__file__", ""))
		bundled = os.path.join(requests_dir, "cacert.pem")
		if bundled and os.path.exists(bundled):
			return bundled
	except Exception:
		pass

	local_bundle = os.path.join(os.path.dirname(__file__), "cacert.pem")
	if local_bundle and os.path.exists(local_bundle):
		try:
			if os.path.getsize(local_bundle) > 0:
				return local_bundle
		except Exception:
			pass

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

"""Minimal certifi shim for bundled environments."""

from __future__ import annotations

import os
import tempfile

try:
	import importlib.resources as importlib_resources
except Exception:
	importlib_resources = None

__all__ = ["where", "contents"]
__version__ = "0.0.0-shim"


def _resource_cacert_bytes() -> bytes:
	if not importlib_resources:
		return b""
	try:
		return (
			importlib_resources.files(__package__).joinpath("cacert.pem").read_bytes()
		)
	except Exception:
		return b""


def _write_temp_cacert(data: bytes) -> str:
	if not data:
		return ""
	try:
		path = os.path.join(tempfile.gettempdir(), "lunawallet_cacert.pem")
		if not os.path.exists(path) or os.path.getsize(path) != len(data):
			with open(path, "wb") as handle:
				handle.write(data)
		return path
	except Exception:
		return ""


def where() -> str:
	"""Return a CA bundle path using requests or SSL defaults."""
	env_path = os.environ.get("REQUESTS_CA_BUNDLE") or os.environ.get("SSL_CERT_FILE")
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

	resource_bytes = _resource_cacert_bytes()
	resource_path = _write_temp_cacert(resource_bytes)
	if resource_path:
		return resource_path

	try:
		import ssl

		return ssl.get_default_verify_paths().cafile or ""
	except Exception:
		return ""


def contents() -> str:
	"""Return CA bundle contents if available, else empty string."""
	path = where()
	if path and os.path.exists(path):
		try:
			with open(path, "r", encoding="utf-8") as f:
				return f.read()
		except Exception:
			return ""

	resource_bytes = _resource_cacert_bytes()
	if not resource_bytes:
		return ""
	try:
		return resource_bytes.decode("ascii")
	except Exception:
		return resource_bytes.decode("utf-8", errors="ignore")

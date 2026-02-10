import os
import ssl
import tempfile

try:
    import importlib.resources as importlib_resources
except Exception:
    importlib_resources = None


def _resource_cacert_bytes() -> bytes:
    if not importlib_resources:
        return b""
    try:
        return importlib_resources.files(__package__).joinpath("cacert.pem").read_bytes()
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
    """Return path to CA bundle. Falls back to system default if available."""
    paths = ssl.get_default_verify_paths()
    for candidate in (paths.cafile, paths.openssl_cafile):
        if candidate and os.path.exists(candidate):
            return candidate

    local_bundle = os.path.join(os.path.dirname(__file__), "cacert.pem")
    if local_bundle and os.path.exists(local_bundle):
        return local_bundle

    resource_bytes = _resource_cacert_bytes()
    resource_path = _write_temp_cacert(resource_bytes)
    if resource_path:
        return resource_path

    return local_bundle


def contents() -> bytes:
    """Return CA bundle contents if available."""
    path = where()
    if path and os.path.exists(path):
        try:
            with open(path, "rb") as handle:
                return handle.read()
        except Exception:
            return b""

    return _resource_cacert_bytes()

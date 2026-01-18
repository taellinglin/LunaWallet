import os
import ssl


def where() -> str:
    """Return path to CA bundle. Falls back to system default if available."""
    paths = ssl.get_default_verify_paths()
    for candidate in (paths.cafile, paths.openssl_cafile):
        if candidate and os.path.exists(candidate):
            return candidate

    local_bundle = os.path.join(os.path.dirname(__file__), "cacert.pem")
    return local_bundle


def contents() -> bytes:
    """Return CA bundle contents if available."""
    path = where()
    try:
        with open(path, "rb") as handle:
            return handle.read()
    except Exception:
        return b""

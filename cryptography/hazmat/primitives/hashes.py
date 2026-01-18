import hashlib


class HashAlgorithm:
    name: str = ""
    digest_size: int = 0


class SHA256(HashAlgorithm):
    name = "sha256"
    digest_size = hashlib.sha256().digest_size


def _get_hash_constructor(algorithm: HashAlgorithm):
    name = getattr(algorithm, "name", None)
    if not name:
        raise ValueError("Unsupported hash algorithm")
    return getattr(hashlib, name)

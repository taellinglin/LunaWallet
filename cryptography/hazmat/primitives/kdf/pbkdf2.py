import hashlib

from .. import hashes


class PBKDF2HMAC:
    def __init__(self, algorithm, length: int, salt: bytes, iterations: int, backend=None):
        self.algorithm = algorithm
        self.length = length
        self.salt = salt
        self.iterations = iterations
        self.backend = backend

    def derive(self, key_material: bytes) -> bytes:
        if isinstance(key_material, str):
            key_material = key_material.encode("utf-8")
        hash_ctor = hashes._get_hash_constructor(self.algorithm)
        return hashlib.pbkdf2_hmac(hash_ctor().name, key_material, self.salt, self.iterations, dklen=self.length)

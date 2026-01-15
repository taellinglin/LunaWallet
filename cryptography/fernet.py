import base64
import hashlib
import hmac
import os
import struct
import time

from .exceptions import InvalidSignature


class Fernet:
    """Minimal pure-Python Fernet implementation (AES-CBC + HMAC-SHA256)."""

    def __init__(self, key: bytes):
        if isinstance(key, str):
            key = key.encode("utf-8")
        key = _urlsafe_b64decode(key)
        if len(key) != 32:
            raise ValueError("Fernet key must be 32 urlsafe base64-encoded bytes")
        self._signing_key = key[:16]
        self._encryption_key = key[16:]

    @staticmethod
    def generate_key() -> bytes:
        return base64.urlsafe_b64encode(os.urandom(32))

    def encrypt(self, data: bytes) -> bytes:
        if isinstance(data, str):
            data = data.encode("utf-8")
        iv = os.urandom(16)
        padded = _pkcs7_pad(data, 16)
        ciphertext = _aes_cbc_encrypt(self._encryption_key, iv, padded)
        token = b"\x80" + _pack_time(int(time.time())) + iv + ciphertext
        sig = hmac.new(self._signing_key, token, hashlib.sha256).digest()
        return base64.urlsafe_b64encode(token + sig)

    def decrypt(self, token: bytes, ttl: int = None) -> bytes:
        if isinstance(token, str):
            token = token.encode("utf-8")
        data = _urlsafe_b64decode(token)
        if len(data) < 1 + 8 + 16 + 32:
            raise InvalidSignature("Token is too short")
        if data[0:1] != b"\x80":
            raise InvalidSignature("Invalid token version")
        ts = _unpack_time(data[1:9])
        iv = data[9:25]
        ciphertext = data[25:-32]
        sig = data[-32:]
        expected = hmac.new(self._signing_key, data[:-32], hashlib.sha256).digest()
        if not hmac.compare_digest(sig, expected):
            raise InvalidSignature("Signature mismatch")
        if ttl is not None and int(time.time()) - ts > ttl:
            raise InvalidSignature("Token has expired")
        padded = _aes_cbc_decrypt(self._encryption_key, iv, ciphertext)
        return _pkcs7_unpad(padded, 16)


def _urlsafe_b64decode(data: bytes) -> bytes:
    if isinstance(data, str):
        data = data.encode("utf-8")
    padding = b"=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def _pack_time(ts: int) -> bytes:
    return struct.pack(">Q", ts)


def _unpack_time(data: bytes) -> int:
    return struct.unpack(">Q", data)[0]


def _pkcs7_pad(data: bytes, block_size: int) -> bytes:
    pad_len = block_size - (len(data) % block_size)
    return data + bytes([pad_len]) * pad_len


def _pkcs7_unpad(data: bytes, block_size: int) -> bytes:
    if not data or len(data) % block_size != 0:
        raise InvalidSignature("Invalid padding")
    pad_len = data[-1]
    if pad_len < 1 or pad_len > block_size:
        raise InvalidSignature("Invalid padding")
    if data[-pad_len:] != bytes([pad_len]) * pad_len:
        raise InvalidSignature("Invalid padding")
    return data[:-pad_len]


def _aes_cbc_encrypt(key: bytes, iv: bytes, data: bytes) -> bytes:
    out = bytearray()
    prev = iv
    for i in range(0, len(data), 16):
        block = data[i : i + 16]
        xored = bytes(a ^ b for a, b in zip(block, prev))
        enc = _aes_encrypt_block(key, xored)
        out.extend(enc)
        prev = enc
    return bytes(out)


def _aes_cbc_decrypt(key: bytes, iv: bytes, data: bytes) -> bytes:
    out = bytearray()
    prev = iv
    for i in range(0, len(data), 16):
        block = data[i : i + 16]
        dec = _aes_decrypt_block(key, block)
        out.extend(bytes(a ^ b for a, b in zip(dec, prev)))
        prev = block
    return bytes(out)


_SBOX = [
    0x63, 0x7C, 0x77, 0x7B, 0xF2, 0x6B, 0x6F, 0xC5, 0x30, 0x01, 0x67, 0x2B, 0xFE, 0xD7, 0xAB, 0x76,
    0xCA, 0x82, 0xC9, 0x7D, 0xFA, 0x59, 0x47, 0xF0, 0xAD, 0xD4, 0xA2, 0xAF, 0x9C, 0xA4, 0x72, 0xC0,
    0xB7, 0xFD, 0x93, 0x26, 0x36, 0x3F, 0xF7, 0xCC, 0x34, 0xA5, 0xE5, 0xF1, 0x71, 0xD8, 0x31, 0x15,
    0x04, 0xC7, 0x23, 0xC3, 0x18, 0x96, 0x05, 0x9A, 0x07, 0x12, 0x80, 0xE2, 0xEB, 0x27, 0xB2, 0x75,
    0x09, 0x83, 0x2C, 0x1A, 0x1B, 0x6E, 0x5A, 0xA0, 0x52, 0x3B, 0xD6, 0xB3, 0x29, 0xE3, 0x2F, 0x84,
    0x53, 0xD1, 0x00, 0xED, 0x20, 0xFC, 0xB1, 0x5B, 0x6A, 0xCB, 0xBE, 0x39, 0x4A, 0x4C, 0x58, 0xCF,
    0xD0, 0xEF, 0xAA, 0xFB, 0x43, 0x4D, 0x33, 0x85, 0x45, 0xF9, 0x02, 0x7F, 0x50, 0x3C, 0x9F, 0xA8,
    0x51, 0xA3, 0x40, 0x8F, 0x92, 0x9D, 0x38, 0xF5, 0xBC, 0xB6, 0xDA, 0x21, 0x10, 0xFF, 0xF3, 0xD2,
    0xCD, 0x0C, 0x13, 0xEC, 0x5F, 0x97, 0x44, 0x17, 0xC4, 0xA7, 0x7E, 0x3D, 0x64, 0x5D, 0x19, 0x73,
    0x60, 0x81, 0x4F, 0xDC, 0x22, 0x2A, 0x90, 0x88, 0x46, 0xEE, 0xB8, 0x14, 0xDE, 0x5E, 0x0B, 0xDB,
    0xE0, 0x32, 0x3A, 0x0A, 0x49, 0x06, 0x24, 0x5C, 0xC2, 0xD3, 0xAC, 0x62, 0x91, 0x95, 0xE4, 0x79,
    0xE7, 0xC8, 0x37, 0x6D, 0x8D, 0xD5, 0x4E, 0xA9, 0x6C, 0x56, 0xF4, 0xEA, 0x65, 0x7A, 0xAE, 0x08,
    0xBA, 0x78, 0x25, 0x2E, 0x1C, 0xA6, 0xB4, 0xC6, 0xE8, 0xDD, 0x74, 0x1F, 0x4B, 0xBD, 0x8B, 0x8A,
    0x70, 0x3E, 0xB5, 0x66, 0x48, 0x03, 0xF6, 0x0E, 0x61, 0x35, 0x57, 0xB9, 0x86, 0xC1, 0x1D, 0x9E,
    0xE1, 0xF8, 0x98, 0x11, 0x69, 0xD9, 0x8E, 0x94, 0x9B, 0x1E, 0x87, 0xE9, 0xCE, 0x55, 0x28, 0xDF,
    0x8C, 0xA1, 0x89, 0x0D, 0xBF, 0xE6, 0x42, 0x68, 0x41, 0x99, 0x2D, 0x0F, 0xB0, 0x54, 0xBB, 0x16,
]

_INV_SBOX = [
    0x52, 0x09, 0x6A, 0xD5, 0x30, 0x36, 0xA5, 0x38, 0xBF, 0x40, 0xA3, 0x9E, 0x81, 0xF3, 0xD7, 0xFB,
    0x7C, 0xE3, 0x39, 0x82, 0x9B, 0x2F, 0xFF, 0x87, 0x34, 0x8E, 0x43, 0x44, 0xC4, 0xDE, 0xE9, 0xCB,
    0x54, 0x7B, 0x94, 0x32, 0xA6, 0xC2, 0x23, 0x3D, 0xEE, 0x4C, 0x95, 0x0B, 0x42, 0xFA, 0xC3, 0x4E,
    0x08, 0x2E, 0xA1, 0x66, 0x28, 0xD9, 0x24, 0xB2, 0x76, 0x5B, 0xA2, 0x49, 0x6D, 0x8B, 0xD1, 0x25,
    0x72, 0xF8, 0xF6, 0x64, 0x86, 0x68, 0x98, 0x16, 0xD4, 0xA4, 0x5C, 0xCC, 0x5D, 0x65, 0xB6, 0x92,
    0x6C, 0x70, 0x48, 0x50, 0xFD, 0xED, 0xB9, 0xDA, 0x5E, 0x15, 0x46, 0x57, 0xA7, 0x8D, 0x9D, 0x84,
    0x90, 0xD8, 0xAB, 0x00, 0x8C, 0xBC, 0xD3, 0x0A, 0xF7, 0xE4, 0x58, 0x05, 0xB8, 0xB3, 0x45, 0x06,
    0xD0, 0x2C, 0x1E, 0x8F, 0xCA, 0x3F, 0x0F, 0x02, 0xC1, 0xAF, 0xBD, 0x03, 0x01, 0x13, 0x8A, 0x6B,
    0x3A, 0x91, 0x11, 0x41, 0x4F, 0x67, 0xDC, 0xEA, 0x97, 0xF2, 0xCF, 0xCE, 0xF0, 0xB4, 0xE6, 0x73,
    0x96, 0xAC, 0x74, 0x22, 0xE7, 0xAD, 0x35, 0x85, 0xE2, 0xF9, 0x37, 0xE8, 0x1C, 0x75, 0xDF, 0x6E,
    0x47, 0xF1, 0x1A, 0x71, 0x1D, 0x29, 0xC5, 0x89, 0x6F, 0xB7, 0x62, 0x0E, 0xAA, 0x18, 0xBE, 0x1B,
    0xFC, 0x56, 0x3E, 0x4B, 0xC6, 0xD2, 0x79, 0x20, 0x9A, 0xDB, 0xC0, 0xFE, 0x78, 0xCD, 0x5A, 0xF4,
    0x1F, 0xDD, 0xA8, 0x33, 0x88, 0x07, 0xC7, 0x31, 0xB1, 0x12, 0x10, 0x59, 0x27, 0x80, 0xEC, 0x5F,
    0x60, 0x51, 0x7F, 0xA9, 0x19, 0xB5, 0x4A, 0x0D, 0x2D, 0xE5, 0x7A, 0x9F, 0x93, 0xC9, 0x9C, 0xEF,
    0xA0, 0xE0, 0x3B, 0x4D, 0xAE, 0x2A, 0xF5, 0xB0, 0xC8, 0xEB, 0xBB, 0x3C, 0x83, 0x53, 0x99, 0x61,
    0x17, 0x2B, 0x04, 0x7E, 0xBA, 0x77, 0xD6, 0x26, 0xE1, 0x69, 0x14, 0x63, 0x55, 0x21, 0x0C, 0x7D,
]

_RCON = [
    0x00, 0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x80, 0x1B, 0x36,
]


def _aes_encrypt_block(key: bytes, block: bytes) -> bytes:
    state = _bytes_to_state(block)
    round_keys = _expand_key(key)

    _add_round_key(state, round_keys[0])
    for rnd in range(1, 10):
        _sub_bytes(state)
        _shift_rows(state)
        _mix_columns(state)
        _add_round_key(state, round_keys[rnd])
    _sub_bytes(state)
    _shift_rows(state)
    _add_round_key(state, round_keys[10])

    return _state_to_bytes(state)


def _aes_decrypt_block(key: bytes, block: bytes) -> bytes:
    state = _bytes_to_state(block)
    round_keys = _expand_key(key)

    _add_round_key(state, round_keys[10])
    _inv_shift_rows(state)
    _inv_sub_bytes(state)
    for rnd in range(9, 0, -1):
        _add_round_key(state, round_keys[rnd])
        _inv_mix_columns(state)
        _inv_shift_rows(state)
        _inv_sub_bytes(state)
    _add_round_key(state, round_keys[0])

    return _state_to_bytes(state)


def _expand_key(key: bytes):
    if len(key) != 16:
        raise ValueError("AES-128 key length required")
    key_words = [list(key[i : i + 4]) for i in range(0, 16, 4)]
    for i in range(4, 44):
        temp = key_words[i - 1][:]
        if i % 4 == 0:
            temp = _sub_word(_rot_word(temp))
            temp[0] ^= _RCON[i // 4]
        key_words.append([a ^ b for a, b in zip(key_words[i - 4], temp)])
    round_keys = []
    for r in range(11):
        rk = [key_words[r * 4 + c] for c in range(4)]
        round_keys.append(rk)
    return round_keys


def _bytes_to_state(block: bytes):
    state = [[0] * 4 for _ in range(4)]
    for i, b in enumerate(block):
        state[i % 4][i // 4] = b
    return state


def _state_to_bytes(state):
    out = bytearray(16)
    for i in range(16):
        out[i] = state[i % 4][i // 4]
    return bytes(out)


def _sub_word(word):
    return [_SBOX[b] for b in word]


def _rot_word(word):
    return word[1:] + word[:1]


def _add_round_key(state, round_key):
    for c in range(4):
        for r in range(4):
            state[r][c] ^= round_key[c][r]


def _sub_bytes(state):
    for r in range(4):
        for c in range(4):
            state[r][c] = _SBOX[state[r][c]]


def _inv_sub_bytes(state):
    for r in range(4):
        for c in range(4):
            state[r][c] = _INV_SBOX[state[r][c]]


def _shift_rows(state):
    state[1] = state[1][1:] + state[1][:1]
    state[2] = state[2][2:] + state[2][:2]
    state[3] = state[3][3:] + state[3][:3]


def _inv_shift_rows(state):
    state[1] = state[1][-1:] + state[1][:-1]
    state[2] = state[2][-2:] + state[2][:-2]
    state[3] = state[3][-3:] + state[3][:-3]


def _xtime(a):
    return ((a << 1) & 0xFF) ^ (0x1B if a & 0x80 else 0x00)


def _mul(a, b):
    res = 0
    for _ in range(8):
        if b & 1:
            res ^= a
        a = _xtime(a)
        b >>= 1
    return res & 0xFF


def _mix_columns(state):
    for c in range(4):
        a0, a1, a2, a3 = state[0][c], state[1][c], state[2][c], state[3][c]
        state[0][c] = _mul(a0, 2) ^ _mul(a1, 3) ^ a2 ^ a3
        state[1][c] = a0 ^ _mul(a1, 2) ^ _mul(a2, 3) ^ a3
        state[2][c] = a0 ^ a1 ^ _mul(a2, 2) ^ _mul(a3, 3)
        state[3][c] = _mul(a0, 3) ^ a1 ^ a2 ^ _mul(a3, 2)


def _inv_mix_columns(state):
    for c in range(4):
        a0, a1, a2, a3 = state[0][c], state[1][c], state[2][c], state[3][c]
        state[0][c] = _mul(a0, 14) ^ _mul(a1, 11) ^ _mul(a2, 13) ^ _mul(a3, 9)
        state[1][c] = _mul(a0, 9) ^ _mul(a1, 14) ^ _mul(a2, 11) ^ _mul(a3, 13)
        state[2][c] = _mul(a0, 13) ^ _mul(a1, 9) ^ _mul(a2, 14) ^ _mul(a3, 11)
        state[3][c] = _mul(a0, 11) ^ _mul(a1, 13) ^ _mul(a2, 9) ^ _mul(a3, 14)

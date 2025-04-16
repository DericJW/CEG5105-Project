import struct
from hashlib import sha256

def generate_mac(key: bytes, data: bytes, counter: int) -> bytes:
    hmac_input = key + data + struct.pack(">H", counter)
    return sha256(hmac_input).digest()[:16]

def verify_mac(key: bytes, data: bytes, counter: int, mac: bytes) -> bool:
    expected_mac = generate_mac(key, data, counter)
    return mac == expected_mac

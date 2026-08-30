from __future__ import annotations

import base64
import hashlib
import json
import os
import urllib.parse

from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.asymmetric import padding as asym_padding
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.serialization import load_der_public_key


def random_urlsafe(byte_count: int = 32) -> str:
    return base64.urlsafe_b64encode(os.urandom(byte_count)).rstrip(b"=").decode()


def code_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode()).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


def encrypt_svc_param(payload: dict[str, object], chk_do_num: int, public_key_b64: str) -> str:
    if chk_do_num < 1:
        raise ValueError("invalid Samsung key derivation iteration count")
    chk_text = str(chk_do_num)
    hashed = base64.b64encode(hashlib.sha256(chk_text.encode()).digest())
    salt = os.urandom(16)
    derived = hashlib.pbkdf2_hmac("sha256", hashed, salt, chk_do_num, dklen=16)
    public_key = load_der_public_key(base64.b64decode(public_key_b64, validate=True))
    if not isinstance(public_key, rsa.RSAPublicKey):
        raise ValueError("Samsung entry point public key is not RSA")
    encrypted_key = public_key.encrypt(base64.b64encode(derived), asym_padding.PKCS1v15())

    iv = os.urandom(16)
    padder = padding.PKCS7(128).padder()
    plaintext = json.dumps(payload, separators=(",", ":")).encode()
    padded = padder.update(plaintext) + padder.finalize()
    encryptor = Cipher(algorithms.AES(derived), modes.CBC(iv)).encryptor()
    encrypted_payload = encryptor.update(padded) + encryptor.finalize()

    envelope = {
        "chkDoNum": chk_text,
        "svcEncParam": base64.b64encode(encrypted_payload).decode(),
        "svcEncKY": base64.b64encode(encrypted_key).decode(),
        "svcEncIV": iv.hex(),
    }
    encoded = base64.b64encode(json.dumps(envelope).encode()).decode()
    return urllib.parse.quote(encoded, safe="")


def decrypt_auth_value(value: str, key: str) -> str:
    key_bytes = key.encode()[:16].ljust(16, b"\0")
    decryptor = Cipher(algorithms.AES(key_bytes), modes.ECB()).decryptor()  # nosec B305
    padded = decryptor.update(bytes.fromhex(value)) + decryptor.finalize()
    unpadder = padding.PKCS7(128).unpadder()
    return (unpadder.update(padded) + unpadder.finalize()).decode()

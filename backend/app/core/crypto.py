"""Field-level encryption for KYB values (GSTIN, PAN, IEC, TRN…).

* :func:`encrypt` / :func:`decrypt` — AES-256-GCM with a random 96-bit nonce
  per value. The key version is bound into the ciphertext as associated
  data, so a value can't be decrypted under the wrong key slot.
  Stored form: ``base64(nonce || ciphertext+tag)``.
* :func:`value_hash` — HMAC-SHA256 of the normalised value under a separate
  key; lets the database reject a duplicate GSTIN without decrypting.
* :func:`last4` — masked display hint.

Keys come from ``KYB_ENC_KEYS`` (``version:base64key,...``) and
``KYB_HASH_KEY``; they never touch the database or git. With DEBUG=false the
app refuses to start without them (:func:`check_keys`). Development uses a
fixed, clearly-marked local key so it works out of the box — data encrypted
with it is NOT protected.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import os
import re
from dataclasses import dataclass
from functools import lru_cache

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import Settings, settings

_NONCE_BYTES = 12
_KEY_BYTES = 32
_DEV_ENC_KEY = hashlib.sha256(b"cor1x-dev-only-kyb-encryption-key").digest()
_DEV_HASH_KEY = hashlib.sha256(b"cor1x-dev-only-kyb-hash-key").digest()


class CryptoConfigError(RuntimeError):
    """Missing or malformed key configuration."""


class DecryptionError(RuntimeError):
    """Ciphertext is corrupt, or was encrypted with an unknown key."""


@dataclass(frozen=True)
class _Keys:
    enc: dict[int, bytes]
    current: int
    hash_key: bytes
    is_dev: bool


def _b64key(raw: str, what: str) -> bytes:
    try:
        key = base64.b64decode(raw.strip(), validate=True)
    except (binascii.Error, ValueError):
        raise CryptoConfigError(f"{what} is not valid base64.") from None
    if len(key) != _KEY_BYTES:
        raise CryptoConfigError(f"{what} must decode to {_KEY_BYTES} bytes (got {len(key)}).")
    return key


def load_keys(s: Settings) -> _Keys:
    """Parse key settings. Dev keys are used only while DEBUG is on and the
    settings are empty."""
    enc_raw, hash_raw = s.kyb_enc_keys.strip(), s.kyb_hash_key.strip()
    if not enc_raw and not hash_raw and s.debug:
        return _Keys(enc={1: _DEV_ENC_KEY}, current=1, hash_key=_DEV_HASH_KEY, is_dev=True)
    if not enc_raw or not hash_raw:
        raise CryptoConfigError("KYB_ENC_KEYS and KYB_HASH_KEY must both be set when DEBUG=false.")
    enc: dict[int, bytes] = {}
    for part in enc_raw.split(","):
        version, sep, key = part.strip().partition(":")
        if not sep or not version.isdigit() or not 1 <= int(version) <= 32767:
            raise CryptoConfigError("KYB_ENC_KEYS entries must look like 'version:base64key' (version 1–32767).")
        if int(version) in enc:
            raise CryptoConfigError(f"KYB_ENC_KEYS lists version {version} twice.")
        enc[int(version)] = _b64key(key, f"KYB_ENC_KEYS version {version}")
    hash_key = _b64key(hash_raw, "KYB_HASH_KEY")
    if hash_key in enc.values():
        raise CryptoConfigError("KYB_HASH_KEY must differ from every encryption key.")
    return _Keys(enc=enc, current=max(enc), hash_key=hash_key, is_dev=False)


@lru_cache(maxsize=1)
def _keys() -> _Keys:
    return load_keys(settings)


def check_keys(s: Settings = settings) -> bool:
    """Validate configuration at startup; returns True when dev keys are in
    use. Raises :class:`CryptoConfigError` otherwise misconfigured."""
    return load_keys(s).is_dev


def encrypt(plaintext: str) -> tuple[str, int]:
    """Return ``(ciphertext_b64, key_version)``."""
    k = _keys()
    nonce = os.urandom(_NONCE_BYTES)
    ct = AESGCM(k.enc[k.current]).encrypt(nonce, plaintext.encode("utf-8"), _aad(k.current))
    return base64.b64encode(nonce + ct).decode("ascii"), k.current


def decrypt(ciphertext_b64: str, key_version: int) -> str:
    k = _keys()
    key = k.enc.get(key_version)
    if key is None:
        raise DecryptionError(f"No key configured for version {key_version}.")
    try:
        blob = base64.b64decode(ciphertext_b64, validate=True)
        return AESGCM(key).decrypt(blob[:_NONCE_BYTES], blob[_NONCE_BYTES:], _aad(key_version)).decode("utf-8")
    except (InvalidTag, binascii.Error, ValueError):
        raise DecryptionError("Value could not be decrypted.") from None


def _aad(version: int) -> bytes:
    return f"cor1x-kyb-v{version}".encode()


_SPACE = re.compile(r"\s+")
_SEPARATORS = re.compile(r"[\s\-./]+")


def normalize_value(raw: str) -> str:
    """Stored / validated form: upper-case, whitespace removed
    (``22aaaaa 0000a1z5`` → ``22AAAAA0000A1Z5``; dashes in ``UDYAM-KA-…`` stay)."""
    return _SPACE.sub("", raw).upper()


def value_hash(normalized: str, *, scope: str) -> str:
    """Keyed hash, scoped to a document type so equal numbers of different
    types don't collide. Separators are ignored, so ``UDYAM-KA-01-…`` and
    ``UDYAMKA01…`` count as the same number."""
    msg = f"{scope}\x00{_SEPARATORS.sub('', normalized)}".encode("utf-8")
    return hmac.new(_keys().hash_key, msg, hashlib.sha256).hexdigest()


def last4(normalized: str) -> str:
    return normalized[-4:]


def mask(last: str | None) -> str | None:
    return f"••••{last}" if last else None

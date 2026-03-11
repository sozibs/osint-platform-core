"""VAPID key management for Web Push notifications."""
from __future__ import annotations

import base64
import json
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

_KEYS_FILE = Path(__file__).parent / "vapid_keys.json"


def _generate_vapid_keys() -> dict[str, str]:
    """Generate a new VAPID key pair using py_vapid / cryptography."""
    try:
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.hazmat.backends import default_backend
        from cryptography.hazmat.primitives.serialization import (
            Encoding,
            PublicFormat,
            PrivateFormat,
            NoEncryption,
        )

        private_key = ec.generate_private_key(ec.SECP256R1(), default_backend())
        public_key = private_key.public_key()

        private_bytes = private_key.private_bytes(
            encoding=Encoding.DER,
            format=PrivateFormat.PKCS8,
            encryption_algorithm=NoEncryption(),
        )
        public_bytes = public_key.public_bytes(
            encoding=Encoding.X962,
            format=PublicFormat.UncompressedPoint,
        )

        return {
            "private_key": base64.urlsafe_b64encode(private_bytes).decode("utf-8").rstrip("="),
            "public_key": base64.urlsafe_b64encode(public_bytes).decode("utf-8").rstrip("="),
        }
    except ImportError:
        logger.warning("cryptography package not installed; VAPID key generation unavailable.")
        return {"private_key": "", "public_key": ""}


def get_vapid_keys() -> dict[str, str]:
    """Load VAPID keys from environment, keys file, or generate new ones."""
    env_private = os.environ.get("VAPID_PRIVATE_KEY", "")
    env_public = os.environ.get("VAPID_PUBLIC_KEY", "")
    if env_private and env_public:
        return {"private_key": env_private, "public_key": env_public}

    if _KEYS_FILE.exists():
        try:
            with _KEYS_FILE.open() as fh:
                return json.load(fh)
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to load VAPID keys from file: %s", exc)

    keys = _generate_vapid_keys()
    if keys["private_key"]:
        try:
            _KEYS_FILE.write_text(json.dumps(keys, indent=2))
            logger.info("Generated and saved new VAPID keys to %s", _KEYS_FILE)
        except OSError as exc:
            logger.warning("Could not persist VAPID keys: %s", exc)

    return keys

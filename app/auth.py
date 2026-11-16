from __future__ import annotations

import hashlib
import hmac
import secrets
from base64 import urlsafe_b64decode, urlsafe_b64encode
from datetime import UTC, datetime, timedelta

from eth_account import Account
from eth_account.messages import encode_defunct
from sqlalchemy import select
from sqlalchemy.orm import Session
from web3 import Web3

from app.models import AuthNonce, User


def normalize_address(address: str) -> str:
    if not Web3.is_address(address):
        raise ValueError("Invalid EVM wallet address")
    return Web3.to_checksum_address(address)


def create_challenge(session: Session, address: str, chain_id: int) -> str:
    wallet = normalize_address(address)
    nonce = secrets.token_urlsafe(24)
    issued_at = datetime.now(UTC)
    expires_at = issued_at + timedelta(minutes=10)
    message = (
        "DataBounty wallet linking\n"
        f"Wallet: {wallet}\n"
        f"Chain ID: {chain_id}\n"
        f"Nonce: {nonce}\n"
        f"Issued at: {issued_at.isoformat()}\n"
        f"Expires at: {expires_at.isoformat()}\n"
        "This request does not send a blockchain transaction."
    )
    session.add(
        AuthNonce(
            wallet_address=wallet,
            nonce_hash=hashlib.sha256(nonce.encode()).hexdigest(),
            message=message,
            expires_at=expires_at,
        )
    )
    session.commit()
    return message


def verify_challenge(session: Session, user: User | None, message: str, signature: str) -> User:
    nonce_row = session.scalar(
        select(AuthNonce).where(AuthNonce.message == message, AuthNonce.used_at.is_(None))
    )
    now = datetime.now(UTC)
    if nonce_row is None or _as_utc(nonce_row.expires_at) < now:
        raise ValueError("Challenge is invalid or expired")
    try:
        recovered = Account.recover_message(encode_defunct(text=message), signature=signature)
    except Exception as exc:
        raise ValueError("Signature is invalid") from exc
    if normalize_address(recovered) != nonce_row.wallet_address:
        raise ValueError("Signature does not match the requested wallet")

    nonce_row.used_at = now
    existing = session.scalar(select(User).where(User.wallet_address == nonce_row.wallet_address))
    if user is None:
        if existing is None:
            raise ValueError("Create an email account before linking this wallet")
        session.commit()
        session.refresh(existing)
        return existing
    if existing is not None and existing.id != user.id:
        raise ValueError("This wallet is already linked to another account")
    user.wallet_address = nonce_row.wallet_address
    session.commit()
    session.refresh(user)
    return user


def normalize_email(email: str) -> str:
    normalized = email.strip().lower()
    if len(normalized) > 320 or "@" not in normalized:
        raise ValueError("Enter a valid email address")
    local, _, domain = normalized.partition("@")
    if not local or "." not in domain or domain.startswith(".") or domain.endswith("."):
        raise ValueError("Enter a valid email address")
    return normalized


def hash_password(password: str) -> str:
    if len(password) < 8:
        raise ValueError("Password must contain at least 8 characters")
    if len(password) > 200:
        raise ValueError("Password is too long")
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1, dklen=32)
    return "scrypt$" + urlsafe_b64encode(salt).decode() + "$" + urlsafe_b64encode(digest).decode()


def verify_password(password: str, encoded: str | None) -> bool:
    if not encoded:
        return False
    try:
        algorithm, salt_text, digest_text = encoded.split("$", 2)
        if algorithm != "scrypt":
            return False
        salt = urlsafe_b64decode(salt_text.encode())
        expected = urlsafe_b64decode(digest_text.encode())
        actual = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1, dklen=32)
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(actual, expected)


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)

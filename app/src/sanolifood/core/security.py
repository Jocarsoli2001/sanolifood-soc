import hmac
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from fastapi import Request


password_hasher = PasswordHasher(time_cost=3, memory_cost=65_536, parallelism=2, hash_len=32, salt_len=16)
DUMMY_PASSWORD_HASH = password_hasher.hash("SanoliFood timing protection 2026")


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return password_hasher.verify(password_hash, password)
    except (InvalidHashError, VerificationError, VerifyMismatchError):
        return False


def password_needs_rehash(password_hash: str) -> bool:
    return password_hasher.check_needs_rehash(password_hash)


def password_validation_errors(password: str) -> list[str]:
    errors: list[str] = []
    if len(password) < 12:
        errors.append("La contraseña debe contener al menos 12 caracteres.")
    categories = sum(
        [
            any(character.islower() for character in password),
            any(character.isupper() for character in password),
            any(character.isdigit() for character in password),
            any(not character.isalnum() for character in password),
        ]
    )
    if categories < 3:
        errors.append("Utiliza al menos tres categorías: minúsculas, mayúsculas, números o símbolos.")
    return errors


def csrf_token(request: Request) -> str:
    token = request.session.get("csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        request.session["csrf_token"] = token
    return token


def csrf_is_valid(request: Request, submitted_token: str) -> bool:
    expected_token = request.session.get("csrf_token", "")
    return bool(expected_token and submitted_token and hmac.compare_digest(expected_token, submitted_token))

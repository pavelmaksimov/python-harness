# JWT and password hashing helpers

Copy into `project/libs/security.py` (copy only if missing). Requires `pyjwt` and
`"pwdlib[argon2]"` (`uv add pyjwt "pwdlib[argon2]"`) plus the `SECRET_KEY` /
`JWT_ALGORITHM` / `ACCESS_TOKEN_EXPIRE_MINUTES` Settings fields from
[`python-jwt.mdc`](python-jwt.mdc). No FastAPI or ORM imports here — and no business logic:
components import these helpers instead of touching the `jwt` / `pwdlib` libraries.

```python
from datetime import datetime, timedelta, timezone

import jwt
from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher
from pwdlib.hashers.bcrypt import BcryptHasher

from project.exceptions import AuthError
from project.settings import Settings


class TokenInvalidError(AuthError):
    """Token signature, format, or payload is not valid."""


class TokenExpiredError(AuthError):
    """Token `exp` has passed."""


# Argon2 hashes new passwords; Bcrypt only verifies (and rehashes) legacy ones.
_password_hash = PasswordHash((Argon2Hasher(), BcryptHasher()))

# Verify against this when the user is missing so login timing does not reveal
# whether the username exists. Generated once at import; never a real password.
DUMMY_HASH = _password_hash.hash("timing-equalized-dummy-password")


def verify_password(password: str, password_hash: str) -> tuple[bool, str | None]:
    """Returns (valid, new_hash); new_hash is set when the stored hash must be rehashed."""
    valid, updated = _password_hash.verify_and_update(password, password_hash)
    return valid, updated


def get_password_hash(password: str) -> str:
    return _password_hash.hash(password)


def create_access_token(subject: object, expires_delta: timedelta) -> str:
    expire = datetime.now(timezone.utc) + expires_delta
    return jwt.encode(
        {"exp": expire, "sub": str(subject)},
        Settings().SECRET_KEY.get_secret_value(),
        algorithm=Settings().JWT_ALGORITHM,
    )


def decode_token(token: str) -> str:
    """Returns the token subject.

    Raises TokenExpiredError when `exp` has passed, TokenInvalidError for any other
    invalid, tampered, or malformed token.
    """
    try:
        payload = jwt.decode(
            token,
            Settings().SECRET_KEY.get_secret_value(),
            algorithms=[Settings().JWT_ALGORITHM],
        )
        
    except jwt.ExpiredSignatureError as e:
        raise TokenExpiredError("Token has expired") from e
    
    except jwt.InvalidTokenError as e:
        raise TokenInvalidError("Token is invalid") from e
    
    except jwt.PyJWTError as e:
        raise AuthError("Authorization error") from e

    sub = payload.get("sub")
    if sub is None:
        raise TokenInvalidError("Token has no subject")

    return str(sub)
```

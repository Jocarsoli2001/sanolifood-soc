from collections.abc import Callable

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from sanolifood.database.session import get_db
from sanolifood.models import User


class AuthenticationRequired(Exception):
    pass


class PermissionDenied(Exception):
    def __init__(self, message: str = "No tienes permisos para realizar esta acción.") -> None:
        self.message = message
        super().__init__(message)


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    user_id = request.session.get("user_id")
    if not user_id:
        raise AuthenticationRequired
    user = db.get(User, int(user_id))
    if user is None or not user.is_active:
        request.session.clear()
        raise AuthenticationRequired
    request.state.current_user = user
    return user


def require_roles(*allowed_roles: str) -> Callable[..., User]:
    def dependency(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise PermissionDenied
        return current_user

    return dependency

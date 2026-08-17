import logging

from sqlalchemy import select

from sanolifood.core.config import get_settings
from sanolifood.core.events import record_event
from sanolifood.core.logging import configure_logging
from sanolifood.core.security import hash_password, password_validation_errors
from sanolifood.database.session import SessionLocal
from sanolifood.models import User, UserRole


def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    logger = logging.getLogger("sanolifood.bootstrap")
    password = settings.bootstrap_admin_password.get_secret_value()

    if not password or password.startswith("CHANGE_ME"):
        logger.warning("bootstrap_admin_skipped", extra={"event_type": "identity.bootstrap.skipped"})
        return

    errors = password_validation_errors(password)
    if errors:
        raise SystemExit("BOOTSTRAP_ADMIN_PASSWORD no cumple la política: " + " ".join(errors))

    username = settings.bootstrap_admin_username.strip().lower()
    email = settings.bootstrap_admin_email.strip().lower()
    with SessionLocal() as db:
        existing = db.scalar(select(User).where(User.username == username))
        if existing:
            logger.info(
                "bootstrap_admin_exists",
                extra={"event_type": "identity.bootstrap.exists", "actor_username": username},
            )
            return

        admin = User(
            username=username,
            email=email,
            full_name=settings.bootstrap_admin_full_name.strip(),
            password_hash=hash_password(password),
            role=UserRole.ADMIN,
            is_active=True,
        )
        db.add(admin)
        db.flush()
        record_event(
            db,
            event_type="identity.user.bootstrap_created",
            outcome="success",
            actor=admin,
            resource_type="user",
            resource_id=str(admin.id),
            details={"role": UserRole.ADMIN},
        )
        db.commit()
        logger.info(
            "bootstrap_admin_created",
            extra={"event_type": "identity.bootstrap.created", "actor_username": username},
        )


if __name__ == "__main__":
    main()

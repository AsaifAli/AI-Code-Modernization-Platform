from sqlalchemy.orm import Session
from app.domain.interfaces.i_user_repository import IUserRepository
from app.infrastructure.db.models import User
import logging
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)
class UserRepository(IUserRepository):
    """Concrete implementation of IUserRepository using PostgreSQL."""

    def __init__(self, db: Session):
        self.db = db

    def get_user_by_email(self, email: str):
        try:
            user = (
                self.db.query(User)
                .filter(User.email == email)
                .first()
            )
            return user
        except SQLAlchemyError:
            logger.exception(f"DB error while fetching user by email: {email}")
            raise
        finally:
            self.db.close()

    def create_user(self, email: str, hashed_password: str):
        try:
            new_user = User(
                email=email,
                hashed_password=hashed_password
            )
            self.db.add(new_user)
            self.db.commit()
            self.db.refresh(new_user)

            logger.info(f"User created successfully: {email}")
            return new_user

        except SQLAlchemyError as e:
            self.db.rollback()
            logger.exception(f"Database error while creating user {email}")
            raise

        except Exception as e:
            self.db.rollback()
            logger.exception(f"Unexpected error while creating user {email}")
            raise

        finally:
            self.db.close()
            logger.debug("Database session closed")

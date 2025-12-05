from core.deps import get_user_uow
from core.users import UserCreate
import config

if __name__ == "__main__":
    with get_user_uow() as users:
        user = UserCreate(
            email=config.SUPERUSER_EMAIL,
            password=config.SUPERUSER_PASSWORD,
            is_superuser=True,
            is_active=True,
            full_name=config.SUPERUSER_FULL_NAME
        )
        users.create(user, update_if_exist=True)
        users.commit()

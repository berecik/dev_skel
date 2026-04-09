"""Authentication helpers for the django-bolt skeleton.

Tokens are minted using the wrapper-shared JWT secret (``JWT_SECRET``)
so a token issued by one service in the wrapper is accepted by every
other service that follows the same convention.
"""

from django.conf import settings
from django.contrib.auth.models import User
from django_bolt import Token, create_jwt_for_user


class AuthService:
    """JWT + OAuth helpers built on django_bolt's stateless token primitives."""

    @staticmethod
    def get_tokens_for_user(user) -> dict:
        access = create_jwt_for_user(
            user,
            secret=settings.JWT_SECRET,
            algorithm=settings.JWT_ALGORITHM,
            expires_in=settings.JWT_ACCESS_TTL,
            extra_claims={"iss": settings.JWT_ISSUER},
        )
        refresh = create_jwt_for_user(
            user,
            secret=settings.JWT_SECRET,
            algorithm=settings.JWT_ALGORITHM,
            expires_in=settings.JWT_REFRESH_TTL,
            extra_claims={"iss": settings.JWT_ISSUER, "token_type": "refresh"},
        )
        return {"access": access, "refresh": refresh}

    @staticmethod
    def register_user(username: str, email: str, password: str):
        return User.objects.create_user(
            username=username, email=email, password=password
        )

    @staticmethod
    def authenticate_user(username: str, password: str):
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            return None
        if not user.check_password(password):
            return None
        tokens = AuthService.get_tokens_for_user(user)
        return {**tokens, "user_id": user.id, "username": user.username}

    @staticmethod
    def oauth_login(provider: str, access_token: str):
        username = f"{provider}_user_{access_token[:8]}"
        user, created = User.objects.get_or_create(
            username=username,
            defaults={"email": f"{username}@oauth.local"},
        )
        tokens = AuthService.get_tokens_for_user(user)
        return {
            **tokens,
            "user_id": user.id,
            "username": user.username,
            "created": created,
        }

    @staticmethod
    def refresh_tokens(refresh_token: str):
        try:
            token = Token.decode(refresh_token, settings.JWT_SECRET)
            if token.extras.get("token_type") != "refresh":
                return None
            user = User.objects.get(id=int(token.sub))
            return AuthService.get_tokens_for_user(user)
        except Exception:
            return None

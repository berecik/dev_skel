from django.apps import AppConfig
from django.db.models.signals import post_migrate


def _seed_after_migrate(sender, **kwargs):
    from app.seed import seed_default_accounts
    try:
        seed_default_accounts()
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning("[seed] %s", exc)


class AppMainConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "app"

    def ready(self):
        post_migrate.connect(_seed_after_migrate, sender=self)

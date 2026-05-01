from django.apps import AppConfig


class SchedulingConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'SDIMS_apps.scheduling'


    def ready(self):
        import SDIMS_apps.scheduling.signals  # noqa: F401 — registers all signal handlers
 
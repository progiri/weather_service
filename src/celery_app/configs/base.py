from django.conf import settings

from celery import schedules


class BaseConfig:
    accept_content = ('json',)  # Ignore other content
    broker_connection_timeout = 1
    broker_transport_options = {
        'connect_timeout': 1,
        'max_retries': 5,
    }
    broker_url = settings.CELERY_BROKER_URL
    enable_utc = True
    result_backend = settings.CELERY_RESULT_BACKEND
    result_expires = 7200  # 2 hours.
    result_persistent = False
    result_serializer = 'json'
    task_serializer = 'json'
    timezone = 'Europe/Kiev'

    imports = (
        'celery_app.tasks.weather',
    )
    beat_schedule = {
        'task-auto-start-meteo-data-process': {
            'task': 'celery_app.tasks.weather.task_auto_start_meteo_data_process',
            'schedule': schedules.crontab(minute='*/15'),
        }
    }

from __future__ import absolute_import

import os

from celery import Celery

from celery.concurrency import asynpool
asynpool.PROC_ALIVE_TIMEOUT = 60.0


os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

app = Celery('core')
app.config_from_object('celery_app.configs.base:BaseConfig')
# some celery pools crushes on server
app.conf.worker_proc_alive_timeout = 60


if __name__ == '__main__':
    app.start()

"""
WSGI config for bom_management project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/4.2/howto/deployment/wsgi/
"""

import os

from django.core.wsgi import get_wsgi_application

# os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bom_management.settings')
# 本番環境用のDjango設定を指定
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bom_management.settings.production')

application = get_wsgi_application()

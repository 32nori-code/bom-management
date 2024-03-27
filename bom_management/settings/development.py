from .base import *

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = []

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/4.2/howto/static-files/

STATIC_URL = 'static/'


LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            # 'level': 'DEBUG', # 開発環境時の設定
            'level': 'INFO',  # 本番環境時の設定
            'class': 'logging.handlers.RotatingFileHandler',
            # 'filename': 'django_logs.log',
            'filename': os.path.join(BASE_DIR, 'logs', 'django_logs.log'),
            'maxBytes': 1024*1024*5, # 5MB
            'backupCount': 5, # 最大5ファイルまでバックアップ
            'formatter': 'verbose',
        },
        'console': {
            # 'level': 'DEBUG', # 開発環境時の設定
            'level': 'INFO',  # 本番環境時の設定
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['file', 'console'],
            # 'level': 'DEBUG',   # 開発環境時の設定
            'level': 'INFO',  # 本番環境時の設定
            'propagate': True,
        },
    },
}

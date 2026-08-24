import os
env_name = os.getenv('DJANGO_ENV', 'development')
if env_name == 'production':
    from .production import *
elif env_name == 'test':
    from .test import *
else:
    from .development import *

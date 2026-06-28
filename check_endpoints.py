import os
import django
from django.conf import settings
from django.test import Client
from django.urls import get_resolver
from django.urls.resolvers import URLPattern, URLResolver

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.base')
# If config.settings.base doesn't work, we might need config.settings.local etc, but let's assume it works.
django.setup()

def get_urls(url_patterns, prefix=''):
    urls = []
    for pattern in url_patterns:
        if isinstance(pattern, URLPattern):
            url = prefix + str(pattern.pattern)
            urls.append(url)
        elif isinstance(pattern, URLResolver):
            url = prefix + str(pattern.pattern)
            urls.extend(get_urls(pattern.url_patterns, prefix=url))
    return urls

urls = get_urls(get_resolver().url_patterns)

# Filter out complex urls with regex params like (?P<pk>[0-9]+)
# Or we can just test the ones that have no parameters
static_urls = []
for url in urls:
    if '<' not in url and '(?P' not in url and '*' not in url:
        if not url.startswith('^'):
            static_urls.append('/' + url)
        else:
            static_urls.append(url.replace('^', '/').replace('$', ''))

client = Client(SERVER_NAME='localhost')

print(f"Testing {len(static_urls)} static endpoints without parameters...")
success_count = 0
error_count = 0

for url in static_urls:
    try:
        response = client.get(url)
        status = response.status_code
        print(f"GET {url} -> {status}")
        if status >= 500:
            error_count += 1
            print(f"!!! Error 500 on {url}")
        else:
            success_count += 1
    except Exception as e:
        print(f"GET {url} -> ERROR: {e}")
        error_count += 1

print(f"Done. Tested {len(static_urls)} static endpoints.")
print(f"Success/Redirect/Auth: {success_count}, Server Errors: {error_count}")

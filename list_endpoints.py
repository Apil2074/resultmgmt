import os
import sys
import django

# Setup django
sys.path.append(os.getcwd())
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")
django.setup()

from django.urls import get_resolver, URLPattern, URLResolver

def list_urls(lis, acc=None):
    if acc is None:
        acc = []
    if not lis:
        return
    l = lis[0]
    if isinstance(l, URLPattern):
        yield "".join(acc) + str(l.pattern)
    elif isinstance(l, URLResolver):
        yield from list_urls(l.url_patterns, acc + [str(l.pattern)])
    yield from list_urls(lis[1:], acc)

urls = sorted(set(list_urls(get_resolver().url_patterns)))
for url in urls:
    print(url)

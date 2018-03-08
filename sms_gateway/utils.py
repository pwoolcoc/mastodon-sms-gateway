import records
from urllib.parse import urlparse, urljoin

__all__ = ['get_db', 'is_safe_url']

# For now we are using SQLite for development, but we should be able to switch
# to postgres or something else fairly easily since we aren't doing any crazy
# SQL stuff (not that sqlite can DO much crazy SQL stuff)
DEFAULT_DATABASE_URL = "sqlite:////tmp/mastotwilio.db"

def get_db():
    """
    Since we've defined all our routes in this module, this provides us with an
    easy way to get a database connection. This will have to be refactored when
    we move to postgres, most likely
    """
    import os
    connstr = os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)
    return records.Database(connstr)

def is_safe_url(target, host_url):
    """
    Shamelessly stolen from a flask snippet, to make sure we don't redirect to
    a different host
    """
    ref_url = urlparse(host_url)
    test_url = urlparse(urljoin(host_url, target))
    return test_url.scheme in ('http', 'https') and \
        ref_url.netloc == test_url.netloc


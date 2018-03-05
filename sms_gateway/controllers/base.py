from flask import request

OAUTH_REDIRECT_URI = 'redirect'

__all__ = ['BaseController']

class BaseController(object):
    def get_redirect_uri(self):
        url = request.host_url
        if url.endswith('/'):
            return "{0}{1}".format(url, OAUTH_REDIRECT_URI)
        else:
            return "{0}/{1}".format(url, OAUTH_REDIRECT_URI)


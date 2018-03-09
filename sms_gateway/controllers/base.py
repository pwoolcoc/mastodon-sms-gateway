from flask import request

OAUTH_REDIRECT_URI = 'redirect'

__all__ = ['BaseController']


class BaseController(object):
    def get_redirect_uri(self, host):
        if host.endswith('/'):
            return "{0}{1}".format(host, OAUTH_REDIRECT_URI)
        else:
            return "{0}/{1}".format(host, OAUTH_REDIRECT_URI)

    def getstats(self):
        raise NotImplementedError

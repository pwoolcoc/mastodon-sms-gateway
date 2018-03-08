import pytest

from sms_gateway.controllers.base import BaseController

def test_get_redirect_uri():
    controller = BaseController()
    url = controller.get_redirect_uri('http://example.com/')
    assert url == 'http://example.com/redirect'
    url = controller.get_redirect_uri('http://example.com')
    assert url == 'http://example.com/redirect'

def test_getstats():
    controller = BaseController()
    with pytest.raises(NotImplementedError):
        controller.getstats()

import pytest
from unittest.mock import Mock
from mastodon.Mastodon import MastodonNetworkError

from sms_gateway.controllers.domain import DomainController, CouldNotConnect, \
        DomainDoesntExist
from sms_gateway.controllers.oauth_session import OAuthSessionController

from tests.helpers import db, domain_controller, db_setup, single_user, \
        single_oauth_session, single_domain

def test_pass_oauth_controller(db_setup):
    oauth_controller = OAuthSessionController(db_setup)
    domain_controller = DomainController(db_setup, oauth_controller=oauth_controller)
    assert domain_controller.oauth_controller is oauth_controller

def test_get_or_insert(domain_controller, single_domain):
    domain = domain_controller.get_or_insert('my.domain', 'http://example.com')   
    assert domain.domain == 'my.domain'
    assert domain.client_id == 'abcd'
    assert domain.client_secret == 'efgh'

def test_get_domain(domain_controller, db_setup):
    domain = domain_controller.get_domain('my.domain')
    assert domain is None


def test_mastodon_network_error(domain_controller):
    domain_controller.mastodon.create_app = Mock(side_effect=MastodonNetworkError)
    with pytest.raises(CouldNotConnect):
        domain_controller.register_domain('my.domain', 'http://example.com')

def test_from_session(domain_controller, single_domain, single_oauth_session):
    session = {'uuid': single_oauth_session}
    domain = domain_controller.from_session(session)
    assert domain.domain == 'my.domain'
    assert domain.client_id == 'abcd'
    assert domain.client_secret == 'efgh'

def test_get_by_id(domain_controller, db_setup):
    with pytest.raises(DomainDoesntExist):
        domain = domain_controller.get_by_id(1)

def test_getstats(domain_controller, single_domain):
    stats = domain_controller.getstats()
    assert stats['count'] == 1
    assert stats['domains'][0] is not None

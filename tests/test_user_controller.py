import pytest
from unittest.mock import Mock

from sms_gateway.controllers.domain import DomainController
from sms_gateway.controllers.user import UserController, UserNotFound, \
        UserExists
from sms_gateway.controllers.oauth_session import OAuthSessionController
from sms_gateway.models.user import User
from sms_gateway.models.domain import Domain

from tests.helpers import db, user_controller, db_setup, single_user, \
        single_oauth_session, single_domain

def test_pass_domain_controller(db_setup):
    domain_controller = DomainController(db_setup)
    user_controller = UserController(db_setup,
            domain_controller=domain_controller)
    assert user_controller.domain_controller is domain_controller

def test_pass_oauth_controller(db_setup):
    oauth_controller = OAuthSessionController(db)
    user_controller = UserController(db, oauth_controller=oauth_controller)
    assert user_controller.oauth_controller is oauth_controller

def test_extract_user_domain(user_controller):
    users = ['@foo@my.domain', 'foo@my.domain']
    for u in users:
        user, domain = user_controller.extract_user_domain(u)
        assert user == 'foo'
        assert domain == 'my.domain'

def test_extract_user_domain_none(user_controller):
    user, domain = user_controller.extract_user_domain(None)
    assert user is None and domain is None

def test_get_by_user_and_domain_succeeds(user_controller, single_user):
    user = user_controller.get_by_user_and_domain('foo', 'my.domain')
    assert type(user) == User
    assert user.uuid == single_user
    assert user.user == 'foo'
    assert user.auth_token == 'efgh'
    assert user.domain_id == 1

def test_get_by_user_and_domain_fails_no_default(user_controller, single_user):
    with pytest.raises(UserNotFound):
        user = user_controller.get_by_user_and_domain('bar', 'my.domain')

def test_get_by_user_and_domain_fails_with_default(user_controller, single_user):
    user = user_controller.get_by_user_and_domain('bar', 'my.domain', None)
    assert user is None

def test_user_exists_true(user_controller, single_user):
    assert user_controller.user_exists('foo', 'my.domain')

def test_user_exists_false(user_controller, single_user):
    assert not user_controller.user_exists('bar', 'my.domain')

def test_get_auth_token(user_controller, single_user):
    user_controller.mastodon.log_in = Mock(name='log_in')
    grant_code = 'abcdefgh'
    domain = Domain(id=1, client_id='01234', client_secret='ghefcdab',
            domain='my.domain')
    host = 'http://example.com'
    res = user_controller.get_auth_token(grant_code, domain, host)
    user_controller.mastodon.log_in.assert_called_once_with(code=grant_code,
            redirect_uri='http://example.com/redirect',
            scopes=['read', 'write'])

def test_begin_authorize(user_controller, db_setup):
    user_controller.mastodon.auth_request_url = Mock(name='auth_request_url')
    user_controller.mastodon.create_app = Mock(name='create_app',
            return_value=('abcd', 'efgh'))
    redirect_uri = user_controller.begin_authorize("foo@my.domain",
            "http://example.com")
    user_controller.mastodon.auth_request_url.assert_called_once_with(
            scopes=['read', 'write'],
            redirect_uris='http://example.com/redirect')

def test_begin_authorize_no_user(user_controller):
    with pytest.raises(ValueError):
        user_controller.begin_authorize(None, 'http://example.com')

def test_create(user_controller, db_setup):
    domain = Domain(id=1, client_id='01234', client_secret='ghefcdab',
            domain='my.domain')
    user = user_controller.create('foo', domain, 'abcdefgh')
    assert user.id == 1
    assert user.uuid is not None
    assert user.user == 'foo'
    assert user.auth_token == 'abcdefgh'
    assert user.domain_id == 1

def test_get_by_id_not_found(user_controller, db_setup):
    res = user_controller.get_by_id('abcd-1234')
    assert res is None

def test_create_from_session(user_controller, single_oauth_session, single_domain):
    user_controller.mastodon.log_in = Mock(name='log_in', return_value='12345678')
    res = user_controller.create_from_session('grantcode',
            dict(signup_uuid=single_oauth_session), 'http://example.com')
    assert res is not None

def test_get_domain(user_controller, single_user):
    user = user_controller.get_by_id(single_user)
    domain = user_controller.get_domain(user)
    assert domain.domain == 'my.domain'
    assert domain.client_id == '01234'
    assert domain.client_secret == '5678'

def test_validate_and_login(user_controller, single_user):
    user = user_controller.validate_and_login('foo@my.domain')
    assert user.uuid == single_user
    assert user.user == 'foo'
    assert user.auth_token == 'efgh'
    assert user.domain_id == 1

def test_validate_and_login_not_found(user_controller, db_setup):
    with pytest.raises(UserNotFound):
        user = user_controller.validate_and_login('foo@my.domain')

def test_get_masto_client(user_controller, single_user):
    user = user_controller.get_by_id(single_user)
    domain = user_controller.get_domain(user)
    client = user_controller.get_masto_client(user)
    assert client is not None
    assert client.client_id == domain.client_id
    assert client.client_secret == domain.client_secret
    assert client.access_token == user.auth_token
    assert client.api_base_url == "https://{0}".format(domain.domain)

def test_get_stats(user_controller, single_user):
    stats = user_controller.getstats()
    assert stats['count'] == 1
    assert stats['users'][0] is not None

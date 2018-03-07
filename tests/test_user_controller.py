import pytest
import records
from unittest.mock import patch, Mock
from mastodon import Mastodon
from uuid import uuid4

from sms_gateway.controllers.domain import DomainController
from sms_gateway.controllers.user import UserController, UserNotFound, \
        UserExists
from sms_gateway.controllers.oauth_session import OAuthSessionController
from sms_gateway.migrations import migrate, unmigrate
from sms_gateway.models.user import User
from sms_gateway.models.domain import Domain

db = records.Database('sqlite:///:memory:')

@pytest.fixture
def controller():
    return UserController(db)

@pytest.fixture
def db_setup(request):
    migrate(db)
    def db_teardown():
        unmigrate(db)
    request.addfinalizer(db_teardown)
    return db

@pytest.fixture
def single_user(db_setup):
    uuid = str(uuid4())
    db.query('''
        INSERT INTO domains (domain, client_id, client_secret)
        VALUES (:domain, :client_id, :client_secret)
    ''', domain='my.domain', client_id='01234', client_secret='5678')
    db.query('''
        INSERT INTO users (uuid, user, auth_token, domain_id)
        VALUES (:uuid, :user, :auth_token, :domain_id)
    ''', uuid=uuid, user='foo', auth_token='efgh', domain_id='1')
    return uuid

@pytest.fixture
def single_oauth_session(db_setup):
    uuid = str(uuid4())
    user = 'foo'
    domain = 'my.domain'
    db.query('''
        INSERT INTO oauth_session (uuid, user, domain)
        VALUES (:uuid, :user, :domain)
    ''', uuid=uuid, user=user, domain=domain)
    return uuid

@pytest.fixture
def single_domain(db_setup):
    domain = 'my.domain'
    client_id = 'abcd'
    client_secret = 'efgh'
    db.query('''
        INSERT INTO domains (domain, client_id, client_secret)
        VALUES (:domain, :client_id, :client_secret)
    ''', domain=domain, client_id=client_id, client_secret=client_secret)
    return db

def test_pass_domain_controller(db_setup):
    domain_controller = DomainController(db_setup)
    user_controller = UserController(db_setup,
            domain_controller=domain_controller)
    assert user_controller.domain_controller is domain_controller

def test_pass_oauth_controller(db_setup):
    oauth_controller = OAuthSessionController(db)
    user_controller = UserController(db, oauth_controller=oauth_controller)
    assert user_controller.oauth_controller is oauth_controller

def test_extract_user_domain(controller):
    users = ['@foo@my.domain', 'foo@my.domain']
    for u in users:
        user, domain = controller.extract_user_domain(u)
        assert user == 'foo'
        assert domain == 'my.domain'

def test_extract_user_domain_none(controller):
    user, domain = controller.extract_user_domain(None)
    assert user is None and domain is None

def test_get_by_user_and_domain_succeeds(controller, single_user):
    user = controller.get_by_user_and_domain('foo', 'my.domain')
    assert type(user) == User
    assert user.uuid == single_user
    assert user.user == 'foo'
    assert user.auth_token == 'efgh'
    assert user.domain_id == 1

def test_get_by_user_and_domain_fails_no_default(controller, single_user):
    with pytest.raises(UserNotFound):
        user = controller.get_by_user_and_domain('bar', 'my.domain')

def test_get_by_user_and_domain_fails_with_default(controller, single_user):
    user = controller.get_by_user_and_domain('bar', 'my.domain', None)
    assert user is None

def test_user_exists_true(controller, single_user):
    assert controller.user_exists('foo', 'my.domain')

def test_user_exists_false(controller, single_user):
    assert not controller.user_exists('bar', 'my.domain')

def test_get_auth_token(controller, single_user):
    controller.mastodon.log_in = Mock(name='log_in')
    grant_code = 'abcdefgh'
    domain = Domain(id=1, client_id='01234', client_secret='ghefcdab',
            domain='my.domain')
    host = 'http://example.com'
    res = controller.get_auth_token(grant_code, domain, host)
    controller.mastodon.log_in.assert_called_once_with(code=grant_code,
            redirect_uri='http://example.com/redirect',
            scopes=['read', 'write'])

def test_begin_registration(controller, db_setup):
    controller.mastodon.auth_request_url = Mock(name='auth_request_url')
    controller.mastodon.create_app = Mock(name='create_app',
            return_value=('abcd', 'efgh'))
    redirect_uri = controller.begin_registration("foo@my.domain",
            "http://example.com")
    controller.mastodon.auth_request_url.assert_called_once_with(
            scopes=['read', 'write'],
            redirect_uris='http://example.com/redirect')

def test_begin_registration_no_user(controller):
    with pytest.raises(ValueError):
        controller.begin_registration(None, 'http://example.com')

def test_begin_registration_existing_user(controller, single_user):
    with pytest.raises(UserExists):
        controller.begin_registration('foo@my.domain', 'http://example.com')

def test_create(controller, db_setup):
    domain = Domain(id=1, client_id='01234', client_secret='ghefcdab',
            domain='my.domain')
    user = controller.create('foo', domain, 'abcdefgh')
    assert user.id == 1
    assert user.uuid is not None
    assert user.user == 'foo'
    assert user.auth_token == 'abcdefgh'
    assert user.domain_id == 1

def test_get_by_id_not_found(controller, db_setup):
    res = controller.get_by_id('abcd-1234')
    assert res is None

def test_create_from_session(controller, single_oauth_session, single_domain):
    controller.mastodon.log_in = Mock(name='log_in', return_value='12345678')
    res = controller.create_from_session('grantcode',
            dict(signup_uuid=single_oauth_session), 'http://example.com')
    assert res is not None

def test_get_domain(controller, single_user):
    user = controller.get_by_id(single_user)
    domain = controller.get_domain(user)
    assert domain.domain == 'my.domain'
    assert domain.client_id == '01234'
    assert domain.client_secret == '5678'

def test_validate_and_login(controller, single_user):
    user = controller.validate_and_login('foo@my.domain')
    assert user.uuid == single_user
    assert user.user == 'foo'
    assert user.auth_token == 'efgh'
    assert user.domain_id == 1

def test_validate_and_login_not_found(controller, db_setup):
    with pytest.raises(UserNotFound):
        user = controller.validate_and_login('foo@my.domain')

def test_get_masto_client(controller, single_user):
    user = controller.get_by_id(single_user)
    domain = controller.get_domain(user)
    client = controller.get_masto_client(user)
    assert client is not None
    assert client.client_id == domain.client_id
    assert client.client_secret == domain.client_secret
    assert client.access_token == user.auth_token
    assert client.api_base_url == "https://{0}".format(domain.domain)

def test_get_stats(controller, single_user):
    stats = controller.getstats()
    assert stats['count'] == 1
    assert stats['users'][0] is not None

import pytest
import records
from unittest.mock import patch, Mock
from mastodon import Mastodon
from mastodon.Mastodon import MastodonNetworkError
from uuid import uuid4

from sms_gateway.controllers.domain import DomainController, CouldNotConnect, \
        DomainDoesntExist
from sms_gateway.controllers.user import UserController, UserNotFound, \
        UserExists
from sms_gateway.controllers.oauth_session import OAuthSessionController
from sms_gateway.migrations import migrate, unmigrate
from sms_gateway.models.user import User
from sms_gateway.models.domain import Domain

db = records.Database('sqlite:///:memory:')

@pytest.fixture
def controller():
    return DomainController(db)

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
    id = 1
    domain = 'my.domain'
    client_id = 'abcd'
    client_secret = 'efgh'
    db.query('''
        INSERT INTO domains (id, domain, client_id, client_secret)
        VALUES (:id, :domain, :client_id, :client_secret)
    ''', id=id, domain=domain, client_id=client_id, client_secret=client_secret)
    return id

def test_pass_oauth_controller(db_setup):
    oauth_controller = OAuthSessionController(db_setup)
    domain_controller = DomainController(db_setup, oauth_controller=oauth_controller)
    assert domain_controller.oauth_controller is oauth_controller

def test_get_or_insert(controller, single_domain):
    domain = controller.get_or_insert('my.domain', 'http://example.com')   
    assert domain.domain == 'my.domain'
    assert domain.client_id == 'abcd'
    assert domain.client_secret == 'efgh'

def test_get_domain(controller, db_setup):
    domain = controller.get_domain('my.domain')
    assert domain is None


def test_mastodon_network_error(controller):
    controller.mastodon.create_app = Mock(side_effect=MastodonNetworkError)
    with pytest.raises(CouldNotConnect):
        controller.register_domain('my.domain', 'http://example.com')

def test_from_session(controller, single_domain, single_oauth_session):
    session = {'uuid': single_oauth_session}
    domain = controller.from_session(session)
    assert domain.domain == 'my.domain'
    assert domain.client_id == 'abcd'
    assert domain.client_secret == 'efgh'

def test_get_by_id(controller, db_setup):
    with pytest.raises(DomainDoesntExist):
        domain = controller.get_by_id(1)

def test_getstats(controller, single_domain):
    stats = controller.getstats()
    assert stats['count'] == 1
    assert stats['domains'][0] is not None

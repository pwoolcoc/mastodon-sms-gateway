import pytest
import records
from unittest.mock import patch
from mastodon import Mastodon

from sms_gateway.controllers.user import UserController, UserNotFound
from sms_gateway.migrations import migrate, unmigrate
from sms_gateway.models.user import User

db = records.Database('sqlite:///:memory:')

@pytest.fixture
def controller():
    return UserController(db, mastodon=patch('mastodon.Mastodon', autospec=True))

@pytest.fixture
def db_setup(request):
    migrate(db)
    def db_teardown():
        unmigrate(db)
    request.addfinalizer(db_teardown)

@pytest.fixture
def single_user(db_setup):
    db.query('''
        INSERT INTO domains (domain, client_id, client_secret)
        VALUES (:domain, :client_id, :client_secret)
    ''', domain='my.domain', client_id='01234', client_secret='5678')
    db.query('''
        INSERT INTO users (uuid, user, auth_token, domain_id)
        VALUES (:uuid, :user, :auth_token, :domain_id)
    ''', uuid='abcd', user='foo', auth_token='efgh', domain_id='1')
    

def test_extract_user_domain(controller):
    users = ['@foo@my.domain', 'foo@my.domain']
    for u in users:
        user, domain = controller.extract_user_domain(u)
        assert user == 'foo'
        assert domain == 'my.domain'

def test_get_by_user_and_domain_succeeds(controller, single_user):
    user = controller.get_by_user_and_domain('foo', 'my.domain')
    assert type(user) == User
    assert user.uuid == 'abcd'
    assert user.user == 'foo'
    assert user.auth_token == 'efgh'
    assert user.domain_id == 1

def test_get_by_user_and_domain_fails_no_default(controller, single_user):
    with pytest.raises(UserNotFound):
        user = controller.get_by_user_and_domain('bar', 'my.domain')

def test_get_by_user_and_domain_fails_with_default(controller, single_user):
    user = controller.get_by_user_and_domain('bar', 'my.domain', None)
    assert user is None

def test_user_exists(controller, single_user):
    assert controller.user_exists('foo', 'my.domain')
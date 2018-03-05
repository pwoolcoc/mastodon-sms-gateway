import pytest
import records

from sms_gateway.controllers.user import UserController

db = records.Database('sqlite:///:memory:')

class TestUserController:
    def test_extract_user_domain(self):
        users = ['@foo@my.domain', 'foo@my.domain']
        controller = UserController(db)
        for u in users:
            user, domain = controller.extract_user_domain(u)
            assert user == 'foo'
            assert domain == 'my.domain'

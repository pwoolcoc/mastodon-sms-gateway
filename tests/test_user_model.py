from sms_gateway.models.user import User
from uuid import uuid4

def test_get_id():
    uuid = uuid4()
    u = User(id=1, uuid=uuid, user='foo', auth_token='abcd', domain_id=1)
    assert u.uuid == uuid   

from records import Record
from collections import namedtuple

__all__ = ['User']

class User(namedtuple('User', ['id', 'user', 'auth_token', 'domain_id'])):
    @staticmethod
    def fromrecord(record: Record):
        return User(id=record.id, user=record.user,
                auth_token=record.auth_token, domain_id=record.domain_id)

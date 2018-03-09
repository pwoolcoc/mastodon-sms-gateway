from flask_login import UserMixin
from records import Record
from collections import namedtuple

__all__ = ['User']


class User(namedtuple('User', ['id', 'uuid', 'user', 'auth_token', 'domain_id']), UserMixin):
    def get_id(self):
        return self.uuid

    @staticmethod
    def fromrecord(record: Record):
        return User(id=record.id, uuid=record.uuid, user=record.user,
                    auth_token=record.auth_token, domain_id=record.domain_id)

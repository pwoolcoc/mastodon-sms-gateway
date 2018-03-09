from records import Record
from collections import namedtuple

__all__ = ['Domain']


class Domain(namedtuple('Domain', ['id', 'domain', 'client_id', 'client_secret'])):
    @staticmethod
    def fromrecord(record: Record):
        return Domain(id=record.id, domain=record.domain,
                      client_id=record.client_id, client_secret=record.client_secret)

from flask import Session
from uuid import uuid4
from records import Database

from sms_gateway.controllers.base import BaseController


class OAuthSessionController(BaseController):
    def __init__(self, db: Database):
        self.db = db

    def add(self, user, domain):
        u = str(uuid4())
        self.db.query('''
        insert into oauth_session (uuid, user, domain)
        values (:uuid, :user, :domain)
        ''', uuid=u, user=user, domain=domain)
        return dict(uuid=u, user=user, domain=domain)

    def get(self, uuid) -> dict:
        result = self.db.query('''
        select uuid, user, domain
        from oauth_session
        where uuid = :uuid
        ''', uuid=uuid)
        row = result.first()
        return dict(uuid=row.uuid, user=row.user, domain=row.domain)

    def delete(self, uuid):
        self.db.query('''
        delete from oauth_session
        where uuid = :uuid
        ''', uuid=uuid)
        return None

    def delete_from_session(self, session: Session):
        uuid = session['auth_uuid']
        return self.delete(uuid)

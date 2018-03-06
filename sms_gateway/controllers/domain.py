from flask import Session
from records import Database
from mastodon import Mastodon
from mastodon.Mastodon import MastodonNetworkError

from sms_gateway.controllers.base import BaseController
from sms_gateway.controllers.oauth_session import OAuthSessionController
from sms_gateway.models.domain import Domain

class CouldNotConnect(Exception):
    pass

class DomainDoesntExist(Exception):
    pass

class DomainController(BaseController):
    def __init__(self, db: Database, oauth_controller=None):
        self.db = db

        if oauth_controller is None:
            self.oauth_controller = OAuthSessionController(db)
        else:
            self.oauth_controller = oauth_controller

    def get_or_insert(self, domain: str, host: str) -> Domain:
        if self.domain_exists(domain):
            domain = self.get_domain(domain)
        else:
            domain = self.insert_new_domain(domain, host)
        return domain

    def get_domain(self, domain: str) -> Domain:
        rows = self.db.query('''
        select id, domain, client_id, client_secret
        from domains
        where domain = :domain
        ''', domain=domain)
        result = rows.first()
        if not result:
            return None
        return Domain.fromrecord(result)

    def domain_exists(self, domain: str) -> bool:
        rows = self.db.query('''
        select id
        from domains
        where domain = :domain
        ''', domain=domain)
        if rows.first():
            return True
        return False

    def insert_new_domain(self, domain: str, host: str) -> Domain:
        fulldomain = self.register_domain(domain, host)
        #TODO when upgrading to 0.5.3/0.6, this will need to change to:
        # with db.transaction() as conn:
        #     conn.query(..)
        with self.db.transaction() as tx:
            self.db.query('''
            insert into domains (domain, client_id, client_secret)
            values (:domain, :client_id, :client_secret)
            ''', **fulldomain)
            result = self.db.query('''
            select id, domain, client_id, client_secret
            from domains
            where domain = :domain
            and client_id = :client_id
            and client_secret = :client_secret
            ''', **fulldomain)
            first = result.first()
            tx.commit()
        domain = Domain.fromrecord(first)
        return domain

    def register_domain(self, domain: str, host: str) -> dict:
        redirect_uri = self.get_redirect_uri(host)
        try:
            client_id, client_secret = Mastodon.create_app('sms-gateway', scopes=['read', 'write'],
                    redirect_uris=redirect_uri,
                    api_base_url='https://{0}'.format(domain), request_timeout=600)
        except MastodonNetworkError as e:
            raise CouldNotConnect(domain)
        return dict(domain=domain, client_id=client_id,
                client_secret=client_secret)

    def from_session(self, session: Session) -> Domain:
        sess_uuid = session['uuid']
        sess = self.oauth_controller.get(sess_uuid)
        domain = sess['domain']
        return self.get_domain(domain)

    def get_by_id(self, id: str) -> Domain:
        result = self.db.query('''
        select id, domain, client_id, client_secret
        from domains
        where id = :id
        ''', id=id)
        row = result.first()
        if not row:
            raise DomainDoesntExist
        return Domain.fromrecord(row)

    def getstats(self):
        domains = self.db.query(''' select * from domains ''').all(as_dict=True)
        return dict(count=len(domains), domains=domains)

from flask import Session
from records import Database
from mastodon import Mastodon

from controllers.base import BaseController
from controllers.oauth_session import OAuthSessionController
from models.domain import Domain

class DomainController(BaseController):
    def __init__(self, db: Database, oauth_controller=None):
        self.db = db

        if oauth_controller is None:
            self.oauth_controller = OAuthSessionController(db)
        else:
            self.oauth_controller = oauth_controller

    def get_or_insert(self, domain: str) -> Domain:
        if self.domain_exists(domain):
            print("domain exists")
            domain = self.get_domain(domain)
        else:
            print("domain does not exist, creating")
            domain = self.insert_new_domain(domain)
        return domain

    def get_domain(self, domain: str) -> Domain:
        rows = self.db.query('''
        select id, domain, client_id, client_secret
        from domains
        where domain = :domain
        ''', domain=domain)
        result = rows.first()
        if not result:
            print("couldn't find domain?")
            return None
        return Domain.fromrecord(result)

    def domain_exists(self, domain: str) -> bool:
        rows = self.db.query('''
        select id
        from domains
        where domain = :domain
        ''', domain=domain)
        if rows.first():
            print("domain", domain, "exists")
            return True
        print("domain does not exist")
        return False

    def insert_new_domain(self, domain: str) -> Domain:
        print("creating domain", domain)
        fulldomain = self.register_domain(domain)
        print('full domain: ', fulldomain)
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

    def register_domain(self, domain: str) -> dict:
        redirect_uri = self.get_redirect_uri()
        print("redirect: ", redirect_uri)
        client_id, client_secret = Mastodon.create_app('sms-gateway', scopes=['read', 'write'],
                redirect_uris=redirect_uri,
                api_base_url='https://{0}'.format(domain), request_timeout=600)
        return dict(domain=domain, client_id=client_id,
                client_secret=client_secret)

    def from_session(self, session: Session) -> Domain:
        sess_uuid = session['uuid']
        sess = self.oauth_controller.get(sess_uuid)
        domain = sess['domain']
        return self.get_domain(domain)


from flask import session, Session
from mastodon import Mastodon
from records import Database
from uuid import uuid4

from controllers.base import BaseController
from controllers.domain import DomainController
from controllers.oauth_session import OAuthSessionController
from models.user import User
from models.domain import Domain

sentinel = object()

class UserExists(Exception):
    pass

class UserNotFound(Exception):
    pass

class UserController(BaseController):
    def __init__(self, db: Database, oauth_controller=None,
            domain_controller=None):
        self.db = db
        if domain_controller is None:
            self.domain_controller = DomainController(db)
        else:
            self.domain_controller = domain_controller

        if oauth_controller is None:
            self.oauth_controller = OAuthSessionController(db)
        else:
            self.oauth_controller = oauth_controller

    def begin_registration(self, user: str) -> str:
        user, domain = self.extract_user_domain(user)
        if user is None or domain is None:
            raise ValueError('incorrect user string')
        else:
            redirect_uri = self.get_register_uri(user, domain)
            sess = self.oauth_controller.add(user, domain)
            session['signup_uuid'] = sess['uuid']
            return redirect_uri

    def extract_user_domain(self, user):
        if user is None:
            return None
        user, domain = user.lstrip('@').split('@')
        return (user, domain)

    def get_register_uri(self, user: str, domain: str) -> str:
        if self.user_exists(user, domain):
            raise UserExists
        domain = self.domain_controller.get_or_insert(domain)
        mastodon = Mastodon(client_id=domain.client_id,
                            client_secret=domain.client_secret,
                            api_base_url=domain.domain)
        return mastodon.auth_request_url(scopes=['read', 'write'],
                redirect_uris=self.get_redirect_uri())

    def get_by_user_and_domain(self, user: str, domain: str, default=sentinel) -> User:
        result = self.db.query('''
        select users.id, users.uuid, users.user, users.auth_token, users.domain_id
        from users
        inner join domains
        on users.domain_id = domains.id
        where users.user = :user and domains.domain = :domain
        ''', user=user, domain=domain)
        user = result.first()
        if user:
            return User.fromrecord(user)
        if default is sentinel:
            raise UserNotFound
        else:
            return default

    def user_exists(self, user: str, domain: str) -> bool:
        user = self.get_by_user_and_domain(user, domain, default=None)
        if user is not None:
            return True
        return False

    def get_auth_token(self, grant_code: str, domain: Domain) -> str:
        mastodon = Mastodon(client_id=domain.client_id,
                client_secret=domain.client_secret, api_base_url=domain.domain)
        auth_token = mastodon.log_in(code=grant_code,
            redirect_uri=self.get_redirect_uri(), scopes=['read', 'write'])
        return auth_token

    def create(self, username: str, domain: Domain, auth_token: str) -> User:
        uuid = str(uuid4())
        with self.db.transaction() as tx:
            self.db.query('''
            insert into users (uuid, user, auth_token, domain_id)
            values (:uuid, :user, :auth_token, :domain_id)
            ''', uuid=uuid, user=username, auth_token=auth_token, domain_id=domain.id)
            tx.commit()
        return self.get_by_id(uuid)

    def create_from_session(self, code: str, session: Session) -> User:
        try:
            uuid = session['signup_uuid']
            oauth_session = self.oauth_controller.get(uuid)
            domain = self.domain_controller.get_domain(oauth_session['domain'])
            auth_token = self.get_auth_token(code, domain)
            return self.create(oauth_session['user'], domain, auth_token)
        finally:
            self.oauth_controller.delete(uuid)

    def get_by_id(self, user_id: str) -> User:
        result = self.db.query('''
        select id, uuid, user, auth_token, domain_id
        from users
        where uuid = :uuid
        ''', uuid=user_id)
        row = result.first()
        if not row:
            return None
        return User.fromrecord(row)

    def validate_and_login(self, user: str) -> User:
        user, domain = self.extract_user_domain(user)
        user_rec = self.get_by_user_and_domain(user, domain)
        if user_rec is None:
            raise UserNotFound
        return user_rec

    def get_domain(self, user: User) -> Domain:
        return self.domain_controller.get_by_id(user.domain_id)

    def get_masto_client(self, user: User) -> Mastodon:
        domain = self.get_domain(user)
        mastodon = Mastodon(client_id=domain.client_id,
                        client_secret=domain.client_secret,
                        access_token=user.auth_token, api_base_url=domain.domain)
        return mastodon

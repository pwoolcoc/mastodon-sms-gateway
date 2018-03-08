from flask import Session
from mastodon import Mastodon
from records import Database
from uuid import uuid4

from sms_gateway.controllers.base import BaseController
from sms_gateway.controllers.domain import DomainController
from sms_gateway.controllers.oauth_session import OAuthSessionController
from sms_gateway.models.user import User
from sms_gateway.models.domain import Domain

sentinel = object()

class UserExists(Exception):
    pass

class UserNotFound(Exception):
    pass

class UserController(BaseController):
    def __init__(self, db: Database, oauth_controller=None,
            domain_controller=None, mastodon=Mastodon):
        self.db = db
        if domain_controller is None:
            self.domain_controller = DomainController(db)
        else:
            self.domain_controller = domain_controller

        self.domain_controller.mastodon = mastodon

        if oauth_controller is None:
            self.oauth_controller = OAuthSessionController(db)
        else:
            self.oauth_controller = oauth_controller

        self.mastodon = mastodon

    def begin_authorize(self, user: str, host: str) -> (str, str):
        user, domain = self.extract_user_domain(user)
        if user is None or domain is None:
            raise ValueError('incorrect user string')
        else:
            redirect_uri = self.get_register_uri(domain, host)
            session = self.oauth_controller.add(user, domain)
            return redirect_uri, session

    def extract_user_domain(self, user: str):
        if user is None:
            return None, None
        user, domain = user.lstrip('@').split('@')
        return (user, domain)

    def get_register_uri(self, domain: str, host: str) -> str:
        domain = self.domain_controller.get_or_insert(domain, host)
        mastodon = self.mastodon(client_id=domain.client_id,
                            client_secret=domain.client_secret,
                            api_base_url=domain.domain)
        return mastodon.auth_request_url(scopes=['read', 'write'],
                redirect_uris=self.get_redirect_uri(host))

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

    def get_auth_token(self, grant_code: str, domain: Domain, host: str) -> str:
        mastodon = self.mastodon(client_id=domain.client_id,
                client_secret=domain.client_secret, api_base_url=domain.domain)
        auth_token = mastodon.log_in(code=grant_code,
            redirect_uri=self.get_redirect_uri(host), scopes=['read', 'write'])
        return auth_token

    def create(self, username: str, domain: Domain, auth_token: str) -> User:
        uuid = str(uuid4())
        self.db.query('''
        insert into users (uuid, user, auth_token, domain_id)
        values (:uuid, :user, :auth_token, :domain_id)
        ''', uuid=uuid, user=username, auth_token=auth_token, domain_id=domain.id)
        return self.get_by_id(uuid)

    def update(self, user: User, domain: Domain, auth_token: str) -> User:
        self.db.query('''
        update users set auth_token = :auth_token
        where user = :user and domain_id = :domain_id
        ''', user=user.user, domain_id=domain.id, auth_token=auth_token)
        return self.get_by_id(user.uuid) # get a user objects with the new values

    def create_or_update(self, username: str, domain: Domain, auth_token: str) -> User:
        user = self.get_by_user_and_domain(username, domain.domain, default=None)
        if user is not None:
            return self.update(user, domain, auth_token)
        else:
            return self.create(username, domain, auth_token)

    def create_from_session(self, code: str, session: Session, host: str) -> User:
        try:
            uuid = session['auth_uuid']
            oauth_session = self.oauth_controller.get(uuid)
            domain = self.domain_controller.get_domain(oauth_session['domain'])
            auth_token = self.get_auth_token(code, domain, host)
            return self.create_or_update(oauth_session['user'], domain, auth_token)
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
        return user_rec

    def get_domain(self, user: User) -> Domain:
        return self.domain_controller.get_by_id(user.domain_id)

    def get_masto_client(self, user: User) -> Mastodon:
        domain = self.get_domain(user)
        mastodon = self.mastodon(client_id=domain.client_id,
                        client_secret=domain.client_secret,
                        access_token=user.auth_token, api_base_url=domain.domain)
        return mastodon

    def getstats(self):
        users = self.db.query(''' select * from users ''').all(as_dict=True)
        return dict(count=len(users), users=users)

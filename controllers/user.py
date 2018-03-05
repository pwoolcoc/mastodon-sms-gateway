from flask import session, Session
from mastodon import Mastodon
from records import Database

from controllers.base import BaseController
from controllers.domain import DomainController
from controllers.oauth_session import OAuthSessionController
from models.user import User
from models.domain import Domain

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
            session['uuid'] = sess['uuid']
            return redirect_uri

    def extract_user_domain(self, user):
        if user is None:
            return None
        user, domain = user.lstrip('@').split('@')
        return (user, domain)

    def get_register_uri(self, user: str, domain: str) -> str:
        if self.user_exists(user, domain):
            return "user exists"
        domain = self.domain_controller.get_or_insert(domain)
        mastodon = Mastodon(client_id=domain.client_id,
                            client_secret=domain.client_secret,
                            api_base_url=domain.domain)
        return mastodon.auth_request_url(scopes=['read', 'write'],
                redirect_uris=self.get_redirect_uri())


    def user_exists(self, user: str, domain: str) -> bool:
        rows = self.db.query('''
        select users.id from users 
        inner join domains on
            users.domain_id = domains.id
        where users.user = :user
            and domains.domain = :domain
        ''', user=user, domain=domain)
        if rows.first():
            print("user exists")
            return True
        print("user doesn't exist")
        return False

    def get_auth_token(self, grant_code: str, domain: Domain) -> str:
        mastodon = Mastodon(client_id=domain.client_id,
                client_secret=domain.client_secret, api_base_url=domain.domain)
        auth_token = mastodon.log_in(code=grant_code,
            redirect_uri=self.get_redirect_uri(), scopes=['read', 'write'])
        return auth_token

    def create(self, username: str, domain: Domain, auth_token: str) -> User:
        with self.db.transaction() as tx:
            self.db.query('''
            insert into users (user, auth_token, domain_id)
            values (:user, :auth_token, :domain_id)
            ''', user=username, auth_token=auth_token, domain_id=domain.id)
            result = self.db.query('''
            select id, user, auth_token, domain_id
            from users
            where user = :user and auth_token = :auth_token and domain_id = :domain_id
            ''', user=username, auth_token=auth_token, domain_id=domain.id)
            row = result.first()
            tx.commit()
        return User.fromrecord(row)

    def create_from_session(self, code: str, session: Session) -> User:
        try:
            uuid = session['uuid']
            oauth_session = self.oauth_controller.get(uuid)
            domain = self.domain_controller.get_domain(oauth_session['domain'])
            auth_token = self.get_auth_token(code, domain)
            self.create(oauth_session['user'], domain, auth_token)
        finally:
            self.oauth_controller.delete(uuid)

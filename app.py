from flask import Flask, request, render_template, redirect, session
import records
from uuid import uuid4
from mastodon import Mastodon
import twilio

from models.domain import Domain
from models.user import User

app = Flask(__name__)

OAUTH_REDIRECT_URI = 'redirect'

def get_db():
    return records.Database("sqlite:////tmp/mastotwilio.db")

def domain_exists(db, domain: str) -> bool:
    rows = db.query('''
    select id from domains where domain = :domain
    ''', domain=domain)
    if rows.first():
        print("domain", domain, "exists")
        return True
    print("domain does not exist")
    return False

def get_redirect_uri():
    url = request.host_url
    if url.endswith('/'):
        return "{0}{1}".format(url, OAUTH_REDIRECT_URI)
    else:
        return "{0}/{1}".format(url, OAUTH_REDIRECT_URI)

def register_domain(domain: str) -> dict:
    redirect_uri = get_redirect_uri()
    print("redirect: ", redirect_uri)
    client_id, client_secret = Mastodon.create_app('sms-gateway', scopes=['read', 'write'],
            redirect_uris=redirect_uri,
            api_base_url='https://{0}'.format(domain), request_timeout=600)
    return dict(domain=domain, client_id=client_id,
            client_secret=client_secret)

def insert_new_domain(db, domain: str) -> Domain:
    print("creating domain", domain)
    fulldomain = register_domain(domain)
    print('full domain: ', fulldomain)
    #TODO when upgrading to 0.5.3, this will need to change to:
    # with db.transaction() as conn:
    #     conn.query(..)
    with db.transaction() as tx:
        db.query('''
        insert into domains (domain, client_id, client_secret)
        values (:domain, :client_id, :client_secret)
        ''', **fulldomain)
        result = db.query('''
        select id, domain, client_id, client_secret
        from domains
        where domain = :domain
          and client_id = :client_id
          and client_secret = :client_secret
        ''', **fulldomain)
        first = result.first()
        tx.commit()
    print('record: ', first)
    domain = Domain.fromrecord(first)
    print(domain)
    return domain

def get_domain(db, domain: str) -> dict:
    rows = db.query('''
    select id, domain, client_id, client_secret from domains where domain = :domain
    ''', domain=domain)
    result = rows.first()
    if result:
        return Domain.fromrecord(result)

    print("couldn't find domain?")
    return None

def get_or_insert_domain(db, domain: str):
    if not domain_exists(db, domain):
        print("domain does not exist, creating")
        domain = insert_new_domain(db, domain)
    else:
        print("domain exists")
        domain = get_domain(db, domain)
    return domain

def user_exists(db, user, domain) -> bool:
    rows = db.query('''
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

def signup_user_uri(db, user: str, domain: str) -> str:
    if user_exists(db, user, domain):
        return "user exists"
    domain = get_or_insert_domain(db, domain)
    mastodon = Mastodon(client_id=domain.client_id,
                        client_secret=domain.client_secret,
                        api_base_url=domain.domain)
    return mastodon.auth_request_url(scopes=['read', 'write'],
            redirect_uris=get_redirect_uri())

def extract_user_domain(user):
    if user is None:
        return None
    user, domain = user.lstrip('@').split('@')
    return (user, domain)

def add_new_oauth_auth_session(db, user, domain):
    u = str(uuid4())
    db.query('''
    insert into oauth_session (uuid, user, domain)
    values (:uuid, :user, :domain)
    ''', uuid=u, user=user, domain=domain)
    return dict(uuid=u, user=user, domain=domain)

def get_oauth_auth_session(db, uuid) -> dict:
    result = db.query('''
    select uuid, user, domain
    from oauth_session
    where uuid = :uuid
    ''', uuid=uuid)
    row = result.first()
    return dict(uuid=row.uuid, user=row.user, domain=row.domain)

def cleanup_oauth_session(db, uuid):
    db.query('''
    delete from oauth_session
    where uuid = :uuid
    ''', uuid=uuid)
    return None

def create_user(db, username: str, domain: Domain, auth_token: str) -> User:
    with db.transaction() as tx:
        db.query('''
        insert into users (user, auth_token, domain_id)
        values (:user, :auth_token, :domain_id)
        ''', user=username, auth_token=auth_token, domain_id=domain.id)
        result = db.query('''
        select id, user, auth_token, domain_id
        from users
        where user = :user and auth_token = :auth_token and domain_id = :domain_id
        ''', user=username, auth_token=auth_token, domain_id=domain.id)
        row = result.first()
        tx.commit()
    return User.fromrecord(row)

@app.route('/redirect', methods=('GET', 'POST'))
def oauth_masto_redirect():
    code = request.args.get('code', None)
    sess_uuid = session['uuid']
    db = get_db()
    sess = get_oauth_auth_session(db, sess_uuid)
    domain = sess['domain']
    print('code is ', code)
    print('domain is ', domain)
    try:
        result = db.query('''
        select id, domain, client_id, client_secret
        from domains
        where domain = :domain
        ''', domain=domain)
        domain = Domain.fromrecord(result.first())
        mastodon = Mastodon(client_id=domain.client_id,
                client_secret=domain.client_secret, api_base_url=domain.domain)
        auth_token = mastodon.log_in(code=code,
            redirect_uri=get_redirect_uri(), scopes=['read', 'write'])
        create_user(db, sess['user'], domain, auth_token)
    finally:
        cleanup_oauth_session(db, sess_uuid)
    return "code is {0}".format(code)


@app.route("/signup", methods=('GET', 'POST'))
def signup():
    error = None
    if request.method == 'POST':
        user = request.form['user']
        user, domain = extract_user_domain(user)
        if user is None or domain is None:
            error = 'No username'
        else:
            db = get_db()
            redirect_uri = signup_user_uri(db, user, domain)
            sess = add_new_oauth_auth_session(db, user, domain)
            session['uuid'] = sess['uuid']
            return redirect(redirect_uri)

    return render_template('signup.html', error=error)

def ensure_migrations_table_exists(db):
    rows = db.query("select name from sqlite_master where type = 'table' and name = 'migrations'")
    if not rows.first():
        db.query('''
        create table migrations (
            id INTEGER PRIMARY KEY,
            num INTEGER NOT NULL,
            migration TEXT NOT NULL
        )
        ''')

def migrate():
    db = get_db()
    ensure_migrations_table_exists(db)
    rows = db.query('select max(num) as max_num from migrations')
    result = rows.first()
    max_num = result['max_num']
    if not max_num:
        num = 0
    else:
        num = max_num + 1
    for i, migration in enumerate(MIGRATIONS[num:]):
        db.query(migration)
        db.query('''
        insert into migrations (num, migration)
        values (:num, :migration)
        ''', num=num+i, migration=migration)

MIGRATIONS = [
    '''
    CREATE TABLE domains (
        id INTEGER PRIMARY KEY,
        domain TEXT UNIQUE NOT NULL,
        client_id TEXT NOT NULL,
        client_secret TEXT NOT NULL
    )
    ''',
    '''
    CREATE TABLE oauth_session (
        id INTEGER PRIMARY KEY,
        uuid TEXT NOT NULL,
        user TEXT NOT NULL,
        domain TEXT NOT NULL
    )
    ''',
    '''
    CREATE TABLE users (
        id INTEGER PRIMARY KEY,
        user TEXT NOT NULL,
        auth_token TEXT NOT NULL,
        domain_id INTEGER NOT NULL,
        FOREIGN KEY (domain_id) REFERENCES domains(id)
    )
    ''',
]

if __name__ == '__main__':
    import os
    migrate()
    app.secret_key=os.urandom(24)
    app.run(debug=True)

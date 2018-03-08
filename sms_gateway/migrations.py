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

def migrate(db): # pragma: no cover
    ensure_migrations_table_exists(db)
    rows = db.query('select max(num) as max_num from migrations')
    result = rows.first()
    max_num = result['max_num']
    if not max_num:
        num = 0
    else:
        num = max_num + 1
    for i, migration in enumerate(UP[num:]):
        db.query(migration)
        db.query('''
        insert into migrations (num, migration)
        values (:num, :migration)
        ''', num=num+i, migration=migration)


def unmigrate(db): # pragma: no cover
    rows = db.query('select max(num) as max_num from migrations')
    result = rows.first()
    max_num = result['max_num']
    if not max_num:
        num = 0
    else:
        num = max_num + 1
    for i, migration in enumerate(reversed(DOWN[:num])):
        db.query(migration)
        db.query('''
        delete from migrations
        where num = :num
        ''', num=num-i-1)

UP = [
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
        uuid TEXT NOT NULL,
        user TEXT NOT NULL,
        auth_token TEXT NOT NULL,
        domain_id INTEGER NOT NULL,
        FOREIGN KEY (domain_id) REFERENCES domains(id)
    )
    ''',
]

DOWN = [
    '''
    DROP TABLE IF EXISTS domains
    ''',
    '''
    DROP TABLE IF EXISTS oauth_session
    ''',
    '''
    DROP TABLE IF EXISTS users
    ''',
]

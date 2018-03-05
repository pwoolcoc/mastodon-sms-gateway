from urllib.parse import urlparse, urljoin
from flask import Flask, request, render_template, redirect, \
        session, abort, url_for
from flask_login import LoginManager, login_user, logout_user, \
        login_required, current_user
import records
from mastodon import Mastodon
import twilio

from controllers.user import UserController, UserExists
from controllers.oauth_session import OAuthSessionController
from controllers.domain import DomainController, CouldNotConnect
from models.domain import Domain
from models.user import User

# For now we are using SQLite for development, but we should be able to switch
# to postgres or something else fairly easily since we aren't doing any crazy
# SQL stuff (not that sqlite can DO much crazy SQL stuff)
DEFAULT_DATABASE_URL = "sqlite:////tmp/mastotwilio.db"

# The actual Flask app. This is what we will attach everything else to,
# including the login_manager, http routes, and anything else that needs to
# interact with our application
app = Flask(__name__)
login_manager = LoginManager(app)

def get_db():
    """
    Since we've defined all our routes in this module, this provides us with an
    easy way to get a database connection. This will have to be refactored when
    we move to postgres, most likely
    """
    import os
    connstr = os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)
    return records.Database(connstr)

@app.route('/redirect', methods=('GET', 'POST'))
def oauth_masto_redirect():
    """
    This endpoint is what a mastodon instance will redirect the user to after
    the user authorizes our application to access their account
    """
    db = get_db()
    code = request.args.get('code', None)

    oauth_controller = OAuthSessionController(db)
    domain_controller = DomainController(db, oauth_controller=oauth_controller)
    user_controller = UserController(db, oauth_controller=oauth_controller,
            domain_controller=domain_controller)

    user = user_controller.create_from_session(code, session)
    return do_login(user, user_controller)

@app.route("/signup", methods=('GET', 'POST'))
def signup():
    """
    This endpoint allows the user to register using their mastodon account. All
    we ask from them is the user@domain of their account, then we shuttle them
    off to their instance for authentication. We consider them "registered"
    when we have a valid access_token we can use to authenticate to their
    instance
    """
    error = None
    if request.method == 'POST':
        user = request.form['user']
        db = get_db()
        user_controller = UserController(db)
        try:
            redirect_uri = user_controller.begin_registration(user)
            return redirect(redirect_uri)
        except CouldNotConnect as e:
            error = "Could not connect to host {0}".format(e)
        except ValueError as e:
            error = e
        except UserExists:
            user = user_controller.validate_and_login(user)
            return do_login(user, user_controller)

    return render_template('signup.html', error=error)

@app.route('/login', methods=('GET', 'POST'))
def login():
    if request.method == 'POST':
        user = request.form['user']
        user_controller = UserController(get_db())
        user = user_controller.validate_and_login(user)
        return do_login(user, user_controller)
    return render_template('login.html')

def do_login(user, user_controller):
    login_user(user)

    next = request.args.get('next')

    if not is_safe_url(next):
        return abort(400)

    return redirect(next or url_for('runapp'))

@app.route("/logout")
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/', methods=('GET',))
def index():
    return render_template('index.html')

@app.route('/app')
@login_required
def runapp():
    return render_template('app.html')

@login_manager.user_loader
def get_user(user_id):
    user_controller = UserController(get_db())
    return user_controller.get_by_id(user_id)

def is_safe_url(target):
    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    return test_url.scheme in ('http', 'https') and \
        ref_url.netloc == test_url.netloc

if __name__ == '__main__':
    import os
    from migrations import migrate
    migrate(get_db())

    app.secret_key=os.urandom(24)
    app.run(debug=True)

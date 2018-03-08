from urllib.parse import urlparse, urljoin
from flask import Flask, request, render_template, redirect, \
        session, abort, url_for, jsonify
from flask_login import LoginManager, login_user, logout_user, \
        login_required, current_user
import records
from mastodon import Mastodon
import twilio

from sms_gateway.controllers.user import UserController, UserExists
from sms_gateway.controllers.oauth_session import OAuthSessionController
from sms_gateway.controllers.domain import DomainController, CouldNotConnect
from sms_gateway.controllers.stats import StatsController
from sms_gateway.models.domain import Domain
from sms_gateway.models.user import User

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

    user = user_controller.create_from_session(code, session, request.host_url)
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
            redirect_uri, sess = user_controller.begin_authorize(user,
                    request.host_url)
            session['signup_uuid'] = sess['uuid']
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
    """
    This route serves both the login form and also handles the POST from the
    login form
    """
    if request.method == 'POST':
        user = request.form['user']
        user_controller = UserController(get_db())
        user = user_controller.validate_and_login(user)
        return do_login(user, user_controller)
    return render_template('login.html')

def do_login(user: User, user_controller: UserController):
    """
    This is a method that takes care of all the login-related things that
    happen in a couple places in this app
    """
    login_user(user)

    next = request.args.get('next')

    if not is_safe_url(next):
        return abort(400)

    return redirect(next or url_for('runapp'))

@app.route("/logout")
def logout():
    """
    Logout route, simple enough
    """
    logout_user()
    return redirect(url_for('index'))

@app.route('/', methods=('GET',))
def index():
    """
    This will be the main non-logged-in landing page
    """
    return render_template('index.html')

@app.route('/app')
@login_required
def runapp():
    """
    This will be the main logged-in landing page
    """
    return render_template('app.html')

@app.route('/stats')
@login_required
def stats():
    """
    This will have to go or be vastly improved eventually, but for now I like
    the immediate view into the db that this provides
    """
    db = get_db()
    user_controller = UserController(db)
    domain = user_controller.get_domain(current_user)
    if current_user.user is not 'balrogboogie' and \
            domain.domain is not 'ceilidh.space':
        return abort(403)
    stats_controller = StatsController(db)
    return jsonify(stats_controller.getstats())

@login_manager.user_loader
def get_user(user_id):
    """
    This method is required by Flask-Login, so it knows how to get a User
    object from a user id
    """
    user_controller = UserController(get_db())
    return user_controller.get_by_id(user_id)

def is_safe_url(target):
    """
    Shamelessly stolen from a flask snippet, to make sure we don't redirect to
    a different host
    """
    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    return test_url.scheme in ('http', 'https') and \
        ref_url.netloc == test_url.netloc


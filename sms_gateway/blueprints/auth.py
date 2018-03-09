from flask import request, render_template, redirect, \
        session, abort, url_for, Blueprint
from flask_login import login_user, logout_user

from sms_gateway.utils import get_db, is_safe_url
from sms_gateway.controllers.user import UserController
from sms_gateway.controllers.oauth_session import OAuthSessionController
from sms_gateway.controllers.domain import DomainController, CouldNotConnect
from sms_gateway.models.user import User

__all__ = ['auth']

auth = Blueprint('auth', __name__, template_folder='templates')


@auth.route('/redirect', methods=('GET', 'POST'))
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


@auth.route("/signup", methods=('GET', 'POST'))
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
        redirect_uri, error = start_auth(user)
        if error is None:
            return redirect(redirect_uri)
    return render_template('signup.html', error=error)


@auth.route('/login', methods=('GET', 'POST'))
def login():
    """
    This route serves both the login form and also handles the POST from the
    login form
    """
    error = None
    if request.method == 'POST':
        user = request.form['user']
        redirect_uri, error = start_auth(user)
        if error is None:
            return redirect(redirect_uri)
    return render_template('login.html', error=error)


def start_auth(user):
    error = None
    user_controller = UserController(get_db())
    try:
        redirect_uri, sess = user_controller.begin_authorize(user,
                                                             request.host_url)
        session['auth_uuid'] = sess['uuid']
        return redirect_uri, None
    except CouldNotConnect as e:
        error = "Could not connect to host {0}".format(e)
    except ValueError as e:
        error = e
    return None, error


def do_login(user: User, user_controller: UserController):
    """
    This is a method that takes care of all the login-related things that
    happen in a couple places in this app
    """
    login_user(user)

    next = request.args.get('next')

    if not is_safe_url(next, request.host_url):
        return abort(400)

    return redirect(next or url_for('runapp'))


@auth.route("/logout")
def logout():
    """
    Logout route, simple enough
    """
    logout_user()
    return redirect(url_for('index'))

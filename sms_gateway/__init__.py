from flask import Flask, request, render_template, redirect, \
        session, abort, url_for, jsonify
from flask_login import LoginManager, login_required, current_user

from sms_gateway.utils import get_db
from sms_gateway.controllers.user import UserController
from sms_gateway.controllers.oauth_session import OAuthSessionController
from sms_gateway.controllers.domain import DomainController, CouldNotConnect
from sms_gateway.controllers.stats import StatsController
from sms_gateway.models.domain import Domain
from sms_gateway.models.user import User
from sms_gateway.blueprints.auth import auth

# The actual Flask app. This is what we will attach everything else to,
# including the login_manager, http routes, and anything else that needs to
# interact with our application
app = Flask(__name__)
login_manager = LoginManager(app)

app.register_blueprint(auth)


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

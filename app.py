from flask import Flask, request, render_template, redirect, session
import records
from mastodon import Mastodon
import twilio

from controllers.user import UserController
from controllers.oauth_session import OAuthSessionController
from controllers.domain import DomainController
from models.domain import Domain
from models.user import User

DEFAULT_DATABASE_URL = "sqlite:////tmp/mastotwilio.db"

app = Flask(__name__)

def get_db():
    import os
    connstr = os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)
    return records.Database(connstr)

@app.route('/redirect', methods=('GET', 'POST'))
def oauth_masto_redirect():
    db = get_db()
    code = request.args.get('code', None)

    oauth_controller = OAuthSessionController(db)
    domain_controller = DomainController(db, oauth_controller=oauth_controller)
    user_controller = UserController(db, oauth_controller=oauth_controller,
            domain_controller=domain_controller)

    user_controller.create_from_session(code, session)
    return "code is {0}".format(code)

@app.route("/signup", methods=('GET', 'POST'))
def signup():
    error = None
    if request.method == 'POST':
        user = request.form['user']
        db = get_db()
        user_controller = UserController(db)
        try:
            redirect_uri = user_controller.begin_registration(user)
            return redirect(redirect_uri)
        except ValueError as e:
            error = e

    return render_template('signup.html', error=error)

if __name__ == '__main__':
    import os
    from migrations import migrate
    migrate(get_db())

    app.secret_key=os.urandom(24)
    app.run(debug=True)

from sms_gateway.controllers.oauth_session import OAuthSessionController

from tests.helpers import db, db_setup, single_oauth_session

def test_delete_from_session(db_setup, single_oauth_session):
    controller = OAuthSessionController(db)
    controller.delete_from_session({'signup_uuid': single_oauth_session})

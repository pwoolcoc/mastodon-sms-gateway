from sms_gateway.controllers.stats import StatsController

from tests.helpers import db, db_setup, single_user, single_domain, \
        user_controller, domain_controller

def test_initialize(db_setup):
    s = StatsController(db)

def test_initialize_pass_user_and_domain(user_controller, domain_controller):
    s = StatsController(db, user_controller=user_controller,
            domain_controller=domain_controller)

def test_getstats(single_user):
    s = StatsController(db)
    stats = s.getstats()
    users = stats['users']
    domains = stats['domains']
    assert users is not None
    assert domains is not None

from sms_gateway.controllers.base import BaseController
from sms_gateway.controllers.user import UserController
from sms_gateway.controllers.domain import DomainController

__all__ = ['StatsController']

class StatsController(BaseController):
    def __init__(self, db, user_controller=None, domain_controller=None):
        self.db = db

        if user_controller is None:
            self.user_controller = UserController(db)
        else:
            self.user_controller = user_controller

        if domain_controller is None:
            self.domain_controller = DomainController(db)
        else:
            self.domain_controller = domain_controller

    def getstats(self):
        user_stats = self.user_controller.getstats()
        domain_stats = self.domain_controller.getstats()
        return dict(users=user_stats, domains=domain_stats)


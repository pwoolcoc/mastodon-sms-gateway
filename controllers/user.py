from records import Database

class UserController(object):
    def __init__(db: Database):
        self.db = db


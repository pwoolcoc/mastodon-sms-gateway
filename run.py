"""
This `if` statement makes it so the code block under it is only executed when
this file is run directly. Code that imports this file wouldn't run it, but if
you run `python run.py`, this will run
"""
if __name__ == '__main__':
    import os
    from sms_gateway.migrations import migrate
    from sms_gateway import app, get_db
    migrate(get_db())

    secret_key = os.environ.get('SECRET_KEY', None)
    if secret_key is None:
        app.secret_key = os.urandom(24)
    else:
        app.secret_key = secret_key

    app.run(debug=True)

test: init
	pipenv run py.test -v tests

run: Pipfile.lock
	pipenv run python3 run.py

init: Pipfile.lock

Pipfile.lock: Pipfile
	pipenv install

.PHONY: test

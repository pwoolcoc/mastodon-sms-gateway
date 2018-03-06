test: init
	pipenv run pytest -vs tests

run: Pipfile.lock
	pipenv run python3 run.py

init: Pipfile.lock

Pipfile.lock: Pipfile
	pipenv install

.PHONY: test

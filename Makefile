.PHONY: run test data lint
run:
	./run.sh
test:
	.venv/bin/python -m pytest --cov --cov-fail-under=80
data:
	.venv/bin/python -m datagen
lint:
	.venv/bin/ruff check .

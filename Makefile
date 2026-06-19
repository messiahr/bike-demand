# https://stackabuse.com/how-to-write-a-makefile-automating-python-setup-compilation-and-testing/

PYTHON = python3

APP_DIR=app

.PHONY: help setup run commit bump

.DEFAULT_GOAL = help

help:
	@echo "Available commands:"
	@echo "make run	- run the streamlit app"
	@echo "make commit	- interactive commit with commitizen"
	@echo "make bump	- cut a new version"

setup:
	@uv sync

commit:
	@git add -A
	@uv run cz c

run:
	@cd $(APP_DIR) && uv run streamlit run main.py

bump:
	@uv run cz bump --changelog

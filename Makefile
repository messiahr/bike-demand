# https://stackabuse.com/how-to-write-a-makefile-automating-python-setup-compilation-and-testing/

PYTHON = python3

.PHONY: help setup run commit bump ingest

.DEFAULT_GOAL = help

help:
	@echo "Available commands:"
	@echo "make run	- run the streamlit app"
	@echo "make commit	- interactive commit with commitizen"
	@echo "make bump	- cut a new version"
	@echo "make ingest	- update data/raw"

setup:
	@uv sync

commit:
	@git add -A
	@uv run cz c

run:
	@uv run streamlit run main.py

bump:
	@uv run cz bump --changelog

ingest:
	@uv run python -m src.repositories.hubway_ingest

# https://stackabuse.com/how-to-write-a-makefile-automating-python-setup-compilation-and-testing/

PYTHON = python3

.PHONY: help setup run commit bump ingest

.DEFAULT_GOAL = help

help:
	@echo "Available commands:"
	@echo "make setup	 - set up the virtual environment and install dependencies"
	@echo "make run	- run the streamlit app"
	@echo "make lint	- run ruff and mypy"

setup:
	@uv sync

run:
	@uv run python -m streamlit run main.py

lint:
	@uv run ruff format
	@uv run ruff check --fix src tests
	@uv run mypy src tests --ignore-missing-imports

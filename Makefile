.PHONY: quality test benchmark compile all

quality:
	python portfolio_quality/quality_gate.py .

compile:
	python -m compileall -q agent_service evaluation portfolio_quality tests

test:
	python -m pytest -q

benchmark:
	python evaluation/run_benchmarks.py

all: quality compile test benchmark

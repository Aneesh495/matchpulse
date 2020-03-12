PYTHON ?= python3
RUN_ID ?=
PROFILE ?= full
EVIDENCE ?=
EXPECTED_COMMIT ?= $(shell git rev-parse HEAD)
.PHONY: bootstrap doctor build test data demo bench stress docs acceptance verify release ingest replay train live-demo valuation-audit negative-controls
bootstrap:
	$(PYTHON) -m matchpulse.cli doctor
	npm ci --ignore-scripts --no-audit --no-fund
build:
	$(PYTHON) -c "from pathlib import Path; from matchpulse.resources import guard; guard(Path.cwd(), 50000000)"
	npm run build
	go build -o bin/matchpulse ./cmd/matchpulse
doctor:
	$(PYTHON) -m matchpulse.cli doctor
test:
	$(PYTHON) -m unittest discover -s tests -v
	go test -race ./...
	npm run typecheck
data:
	$(PYTHON) -m matchpulse.cli data
demo:
	$(PYTHON) -m matchpulse.cli demo
ingest:
	$(PYTHON) -m matchpulse.cli ingest $(if $(INPUT),--input "$(INPUT)",)
replay:
	$(PYTHON) -m matchpulse.cli replay --speed $(or $(SPEED),20) $(if $(INPUT),--input "$(INPUT)",)
train:
	$(PYTHON) -m matchpulse.cli train $(if $(RUN_ID),--run-id "$(RUN_ID)",)
live-demo: build
	./bin/matchpulse
valuation-audit:
	$(PYTHON) -m matchpulse.cli valuation-audit $(if $(INPUT),--input "$(INPUT)",)
bench stress:
	$(PYTHON) -m matchpulse.cli bench --profile diagnostic --run-id "$(RUN_ID)"
acceptance:
	$(PYTHON) -m matchpulse.cli acceptance --profile "$(PROFILE)" --run-id "$(RUN_ID)"
verify:
	$(PYTHON) -m matchpulse.verify "$(EVIDENCE)" --source . --expected-commit "$(EXPECTED_COMMIT)"
negative-controls:
	$(PYTHON) scripts/negative-controls.py "$(EVIDENCE)" "$(RUN_ID)"
docs:
	$(PYTHON) scripts/check-docs.py
release:
	$(PYTHON) -m matchpulse.cli release

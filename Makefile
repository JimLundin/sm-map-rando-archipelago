# One target per iteration loop (docs/architecture.md). Variables can be overridden: make test-ap AP=~/Archipelago
PY      ?= python3
AP      ?= /tmp/smmr-rw/Archipelago
ROM     ?=
CARGO   ?= cargo
ENGINE  := engine/target/dev-release/smmr-engine

.PHONY: test-core engine data test-ap fixtures fetch

test-core:              ## core stages, no Archipelago, no Rust (< 1 s)
	$(PY) -m pytest -q tests/core

engine:                 ## incremental, optimized engine build
	cd engine && $(CARGO) build --profile dev-release

fetch:                  ## Map Rando data not in its repository (Mosaic patches)
	$(PY) tools/fetch_data.py

data: engine            ## world data generated from Map Rando (commit the result)
	$(PY) tools/stage.py info -o world/smmr/data/info.json
	$(PY) tools/gen_presets.py

fixtures: engine        ## re-record the seed fixture the core tests replay
	$(PY) tools/stage.py upgrade fixtures/settings/default-vanilla.json -o fixtures/settings/default-vanilla.upgraded.json
	$(PY) tools/stage.py randomize fixtures/settings/default-vanilla.upgraded.json --seed 1 -o fixtures/seeds/default-vanilla-1.json

test-ap: engine         ## the World in an Archipelago checkout (worlds/smmr symlinked); ROM=... also patches
	ln -sfn $(CURDIR)/world/smmr $(AP)/worlds/smmr
	cd $(AP) && SKIP_REQUIREMENTS_UPDATE=1 SMMR_TEST_ROM="$(ROM)" $(PY) -m pytest -q worlds/smmr/test

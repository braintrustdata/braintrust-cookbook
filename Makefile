.PHONY: node-packages mise-install setup tslab

.PHONY: mise-install
mise-install:
	@command -v mise >/dev/null 2>&1 || { echo "Error: mise is not installed. Visit https://mise.jdx.dev/getting-started.html"; exit 1; }
	mise install

setup: mise-install venv/.initialized node-packages tslab
	source venv/bin/activate && npx tslab install

tslab:
	npm install -g tslab

node-packages: pnpm-lock.yaml
	pnpm install

venv/.initialized: requirements.txt venv/bin/activate
	source venv/bin/activate && pip install -r requirements.txt
	touch venv/.initialized

venv/bin/activate:
	python3 -m venv venv

.PHONY: fixup
fixup:
	source venv/bin/activate && pre-commit run --all-files

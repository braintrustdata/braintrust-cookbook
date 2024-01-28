.PHONY: node-packages setup tslab

setup: venv/.initialized node-packages tslab
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

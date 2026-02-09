NPM = npm
SHELL := /bin/bash

.PHONY: help install clean run

CLEAN_FILES = node_modules package-lock.json pnpm-lock.yaml	


install:
	@echo "install dependencies..."
	$(NPM) install

run:
	@if [ ! -d "node_modules" ]; then \
			echo "missing node_modules, installing..."; \
			npm install; \
	fi
	$(NPM) run dev

clean:
	rm -rf $(CLEAN_FILES)


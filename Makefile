.PHONY: openapi

# Generate OpenAPI spec from backend and write to mobile_frontend/
openapi:
	cd backend && PYTHONPATH=. .venv/bin/python scripts/dump_openapi.py > ../mobile_frontend/openapi.json
	@echo "✓ mobile_frontend/openapi.json updated"

.PHONY: dev test replay download-fixtures

dev:
	npm run dev:frontend &
	cd backend && uvicorn app.main:app --reload --port 8000

test:
	cd backend && pytest -v

replay:
	cd backend && REPLAY_SESSION=spa_2024 uvicorn app.main:app --reload --port 8000

download-fixtures:
	cd backend && python tests/fixtures/download_spa_2024.py

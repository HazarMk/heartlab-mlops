.PHONY: setup data train up down drift retrain test-api
setup:
	pip install -r requirements.txt && git init -q 2>/dev/null; dvc init -q 2>/dev/null || true
data:
	python src/generate_data.py
train:
	MLFLOW_TRACKING_URI=http://localhost:5000 dvc repro
up:
	docker compose up -d --build
down:
	docker compose down
drift:
	python src/generate_data.py --drift && python src/drift.py
retrain:
	python src/drift.py --current data/incoming/heart_labeled.csv --retrain && dvc repro retraining/dvc.yaml:retrain
test-api:
	curl -s -X POST localhost:8000/predict -H 'Content-Type: application/json' \
	 -d '{"age":63,"sex":1,"cp":1,"trestbps":145,"chol":233,"fbs":1,"restecg":2,"thalach":150,"exang":0,"oldpeak":2.3,"slope":3,"ca":0,"thal":6}'

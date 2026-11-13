FROM python:3.11-slim
WORKDIR /srv
COPY requirements-api.txt .
RUN pip install --no-cache-dir -r requirements-api.txt
COPY app ./app
RUN mkdir -p /srv/src
COPY src/features.py ./src/features.py
ENV MLFLOW_TRACKING_URI=http://mlflow:5000
ENV MODEL_NAME=heart-disease-classifier
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

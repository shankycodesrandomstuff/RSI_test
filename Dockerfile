# Build only from a trusted, locally available base image in an offline setting.
FROM python:3.11-slim
WORKDIR /app
COPY . /app
RUN useradd --create-home --uid 10001 experimenter
USER 10001
ENTRYPOINT ["python3", "run_experiment.py"]

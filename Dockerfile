FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV PASTY_DB=/data/pastyspace.db \
    PASTY_MAX_MB=50
VOLUME /data
EXPOSE 8000
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:8000", "--timeout", "120", "--preload", "--forwarded-allow-ips", "*", "app:app"]

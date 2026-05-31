FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY myntra_size_monitor.py .

CMD ["python", "myntra_size_monitor.py"]

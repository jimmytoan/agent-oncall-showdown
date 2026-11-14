FROM python:3.13-slim
RUN pip install --no-cache-dir httpx==0.28.1
COPY traffic.py /traffic.py
CMD ["python", "-u", "/traffic.py"]

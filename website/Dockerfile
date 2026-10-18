FROM python:3.12-slim
WORKDIR /site
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY server.py orgs.json ./
COPY static ./static
RUN useradd -r site && chown -R site /site
USER site
CMD exec uvicorn server:app --host 0.0.0.0 --port ${PORT:-8080} --proxy-headers --no-server-header

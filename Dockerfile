FROM python:3.12-slim

WORKDIR /app

# install deps first for better layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# app code + the price template used to seed reference data
COPY . .
# strip any CRLF (in case files were authored on Windows) and make entrypoint executable
RUN sed -i 's/\r$//' docker-entrypoint.sh && chmod +x docker-entrypoint.sh

EXPOSE 8000
ENTRYPOINT ["sh", "./docker-entrypoint.sh"]

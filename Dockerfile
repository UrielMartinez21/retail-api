# Use lightweight Python image
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies for PostgreSQL
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libpq-dev \
        gcc \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . .

# Expose Django's default port
EXPOSE 8000

# Default command to run the Django dev server
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]

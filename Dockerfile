# Build stage
FROM python:3.11-slim as builder

WORKDIR /app
COPY requirements.txt .

# Loại bỏ các thư viện Windows và cài đặt Django trực tiếp
RUN grep -v "pywin32" requirements.txt > requirements-linux.txt && \
    pip install --no-cache-dir --upgrade pip && \
    pip install django python-dotenv && \
    pip wheel --no-cache-dir --wheel-dir /app/wheels -r requirements-linux.txt

# Final stage
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PATH="/scripts:${PATH}"

WORKDIR /app

# Cài đặt các dependencies hệ thống
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    netcat-traditional \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Cài đặt Django và các thư viện cần thiết trước
RUN pip install --no-cache-dir django psycopg2-binary gunicorn python-dotenv

# Cài đặt Python packages từ wheels
COPY --from=builder /app/wheels /wheels
COPY --from=builder /app/requirements-linux.txt .
RUN pip install --no-cache-dir --no-index --find-links=/wheels -r requirements-linux.txt

# Tạo thư mục cho AI và cấp quyền
RUN mkdir -p /app/AI/cv_processed_data /app/AI/job_processed_data
RUN chmod -R 777 /app/AI/cv_processed_data /app/AI/job_processed_data

# Copy code
COPY . .
COPY ./scripts /scripts
RUN chmod +x /scripts/*

# Tạo user không phải root
RUN adduser --disabled-password --no-create-home app-user
RUN find /app -not -path "/app/AI/cv_processed_data*" -not -path "/app/AI/job_processed_data*" -exec chown -R app-user:app-user {} \; 2>/dev/null || true

USER app-user

CMD ["entrypoint.sh"]
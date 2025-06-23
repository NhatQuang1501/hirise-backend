FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PATH="/scripts:${PATH}"

WORKDIR /app

# Cài đặt các dependencies
COPY requirements.txt .
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    gcc \
    netcat-traditional \
    && pip install --upgrade pip \
    && pip install -r requirements.txt \
    && apt-get purge -y --auto-remove build-essential gcc \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Tạo thư mục cho AI và cấp quyền
RUN mkdir -p /app/AI/cv_processed_data /app/AI/job_processed_data
RUN chmod -R 777 /app/AI/cv_processed_data /app/AI/job_processed_data

# Copy toàn bộ code vào container
COPY . .
COPY ./scripts /scripts
RUN chmod +x /scripts/*

# Tạo user không phải root để chạy ứng dụng
RUN adduser --disabled-password --no-create-home app-user
# Chỉ thay đổi quyền sở hữu cho các file trong container, không bao gồm thư mục được mount
RUN find /app -not -path "/app/AI/cv_processed_data*" -not -path "/app/AI/job_processed_data*" -exec chown -R app-user:app-user {} \; 2>/dev/null || true

USER app-user

# Mặc định sẽ chạy entrypoint.sh
CMD ["entrypoint.sh"]
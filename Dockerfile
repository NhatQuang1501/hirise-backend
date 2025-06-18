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

# Copy toàn bộ code vào container
COPY . .
COPY ./scripts /scripts
RUN chmod +x /scripts/*

# Tạo user không phải root để chạy ứng dụng
RUN adduser --disabled-password --no-create-home app-user
RUN chown -R app-user:app-user /app
USER app-user

# Mặc định sẽ chạy entrypoint.sh
CMD ["entrypoint.sh"]
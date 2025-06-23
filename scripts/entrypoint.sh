#!/bin/sh

set -e

# Đợi database sẵn sàng
echo "Waiting for PostgreSQL..."
while ! nc -z $DB_HOST_DEPLOY $DB_PORT_DEPLOY; do
  sleep 0.1
done
echo "PostgreSQL started"

# Đảm bảo thư mục AI tồn tại và có quyền ghi
mkdir -p /app/AI/cv_processed_data /app/AI/job_processed_data
chmod -R 777 /app/AI/cv_processed_data /app/AI/job_processed_data
echo "AI directories checked and permissions set"

# Thực hiện migrations
python manage.py migrate

# Thu thập static files
python manage.py collectstatic --noinput

# Chạy server
exec gunicorn hirise.wsgi:application --bind 0.0.0.0:8000 --workers 3
#!/bin/sh

set -e

# Đợi database sẵn sàng
echo "Waiting for PostgreSQL..."
while ! nc -z $DB_HOST $DB_PORT; do
  sleep 0.1
done
echo "PostgreSQL started"

# Thực hiện migrations
python manage.py migrate

# Tạo superuser nếu chưa có (tùy chọn)
python manage.py shell -c "from users.models import User; User.objects.filter(email='admin@gmail.com').exists() or User.objects.create_superuser('admin@gmail.com', 'adminpassword')"

# Thu thập static files
python manage.py collectstatic --noinput

# Chạy server
exec gunicorn hirise.wsgi:application --bind 0.0.0.0:8000 --workers 3
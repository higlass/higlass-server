rm -f db.sqlite3
python manage.py makemigrations api
python manage.py migrate

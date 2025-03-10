FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set work directory
WORKDIR /app

# Install dependencies
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . /app/

# Run gunicorn
<<<<<<< HEAD
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "fend.wsgi:application", "--env", "DJANGO_SETTINGS_MODULE=fend.settings.production"]
=======
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "fend.wsgi:application", "--env", "DJANGO_SETTINGS_MODULE=fend.settings.production"]
>>>>>>> 49a0f47d9328d62f13594881f034637ba7403c39

# Base Python Image
FROM python:3.9-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    wget \
    unzip \
    ffmpeg \
    curl \
    chromium \
    && rm -rf /var/lib/apt/lists/*

# Set environment variables for Chromium
ENV CHROME_BIN=/usr/bin/chromium

# Set working directory
WORKDIR /app

# Copy project files into the container
COPY . /app

# Set execution permissions for chromedriver
RUN chmod +x /app/chromedriver

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Expose port 5000 for Flask
EXPOSE 5000

# Start the Flask app
CMD ["python3", "app.py", "-i"]

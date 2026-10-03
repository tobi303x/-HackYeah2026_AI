# Use an official lightweight Python image.
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV CHROMA_PERSIST_DIRECTORY=/app/chroma_data

# Set the working directory inside the container
WORKDIR /app

# Create chroma data directory
RUN mkdir -p /app/chroma_data

# Copy the requirements file and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Expose the port the app runs on
EXPOSE 5000

# Command to run the application using Gunicorn.
# Using 1 worker with 4 threads is recommended for embedded ChromaDB / SQLite to prevent multi-process file lock contention while allowing concurrency.
CMD ["gunicorn", "--workers", "1", "--threads", "4", "--bind", "0.0.0.0:5000", "app:app"]

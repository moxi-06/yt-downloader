# Use a lightweight official Python image
FROM python:3.10-slim

# Set the working directory inside the container
WORKDIR /app

# Copy the requirements file into the container
COPY requirements.txt .

# Install the Python dependencies (pytube)
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of your application code into the container
COPY . /app

# Define the default command to run when the container starts.
# We use the Entrypoint to ensure the script is always called,
# and let the user pass arguments (like the URL) to the script later.
ENTRYPOINT ["python", "main.py"]

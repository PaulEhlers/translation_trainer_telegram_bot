# Use a lightweight Python base image
FROM python:3.9

# Set the working directory inside the container
WORKDIR /app

# Install required Python packages
COPY bot/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Expose the command to run the bot (entry point)
CMD ["python", "bot.py"]

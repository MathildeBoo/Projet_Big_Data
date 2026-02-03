# backend/Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Installation des dépendances
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copie du code
COPY . .

# Commande de lancement (L'API écoute sur le port 8000)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
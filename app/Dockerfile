# Dockerfile corrigé
FROM python:3.11-slim

WORKDIR /app

# On retire "app/" car Docker est déjà dans ce dossier
COPY requirements.txt . 
RUN pip install --no-cache-dir -r requirements.txt

# On copie tout le contenu du dossier actuel (.) vers /app
COPY . .

EXPOSE 5000

CMD ["python", "app.py"]
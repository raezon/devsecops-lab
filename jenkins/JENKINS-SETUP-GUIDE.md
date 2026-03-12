# 🚀 JENKINS DOCKER COMPOSE - GUIDE COMPLET

## 📋 FICHIERS CRÉÉS

```
.
├─ docker-compose.yml          # Docker Compose principal
├─ Dockerfile                  # Custom Jenkins image
├─ .env                        # Variables d'environnement
├─ jenkins/
│  ├─ casc.yaml               # Jenkins Configuration as Code
│  ├─ plugins.txt             # Liste des plugins
│  ├─ scripts/                # Scripts personnalisés
│  └─ init.groovy.d/          # Groovy init scripts
├─ nginx/
│  ├─ nginx.conf              # Configuration Nginx
│  └─ ssl/                    # Certificats SSL/TLS
└─ postgres/
   └─ init.sql               # Script d'initialisation BD
```

---

## ✅ PRE-REQUIS

```
✓ Docker 20.10+
✓ Docker Compose 1.29+
✓ Au moins 8GB RAM disponible
✓ Au moins 20GB disque
✓ Port 80, 443, 8080, 5432 disponibles
```

Installation:
```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install docker.io docker-compose -y

# Mac
brew install docker docker-compose

# Verify
docker --version
docker-compose --version
```

---

## 🔧 CONFIGURATION INITIALE

### **1. Cloner/Télécharger les fichiers**

```bash
# Créer répertoire de travail
mkdir -p ~/jenkins-ci && cd ~/jenkins-ci

# Structure de répertoires
mkdir -p jenkins/scripts jenkins/init.groovy.d
mkdir -p nginx/ssl
mkdir -p postgres
```

### **2. Copier tous les fichiers créés**

```
docker-compose.yml      → ~/jenkins-ci/
Dockerfile              → ~/jenkins-ci/
.env                    → ~/jenkins-ci/
casc.yaml              → ~/jenkins-ci/jenkins/
plugins.txt            → ~/jenkins-ci/jenkins/
nginx.conf             → ~/jenkins-ci/nginx/
```

### **3. Configurer les variables d'environnement**

```bash
# Éditer .env avec tes données
nano .env

# Variables importantes à changer:
POSTGRES_PASSWORD=ton_mot_de_passe_securise
GITHUB_TOKEN=ton_github_token
DOCKER_HUB_PASSWORD=ton_docker_password
EMAIL_PASSWORD=ton_email_app_password
SLACK_TOKEN=ton_slack_token
```

### **4. Créer les certificats SSL (optionnel)**

```bash
# Auto-signed certificate (dev)
mkdir -p nginx/ssl
openssl req -x509 -nodes -days 365 \
  -newkey rsa:2048 \
  -keyout nginx/ssl/private.key \
  -out nginx/ssl/certificate.crt

# Production: Utiliser Let's Encrypt via Certbot
sudo certbot certonly --standalone -d jenkins.example.com
```

### **5. Créer le script PostgreSQL (optionnel)**

```bash
cat > postgres/init.sql << 'EOF'
-- Create Jenkins database extensions if needed
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Create additional tables if using PostgreSQL for Jenkins metrics
CREATE TABLE IF NOT EXISTS jenkins_metrics (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP DEFAULT NOW(),
    metric_name VARCHAR(255),
    metric_value FLOAT,
    labels JSONB
);

CREATE INDEX idx_jenkins_metrics_timestamp 
ON jenkins_metrics(timestamp DESC);

GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public 
TO jenkins_user;
EOF
```

---

## 🚀 DÉMARRAGE

### **Option 1: Build custom image**

```bash
# Depuis le répertoire ~/jenkins-ci/
docker-compose build

# Puis démarrer
docker-compose up -d
```

### **Option 2: Utiliser image pré-configurée**

```bash
# Directement (sans build)
docker-compose up -d
```

### **Vérifier le démarrage**

```bash
# Logs Jenkins
docker-compose logs -f jenkins

# Vérifier les services
docker-compose ps

# Vérifier la santé
docker-compose logs jenkins | grep "Jenkins is fully up"
```

---

## 📊 ACCÈS JENKINS

### **Récupérer le mot de passe initial**

```bash
# Méthode 1: Docker logs
docker-compose logs jenkins | grep "generated password"

# Méthode 2: Lire le fichier directement
docker exec jenkins_master cat /var/jenkins_home/secrets/initialAdminPassword

# Stocker dans variable
JENKINS_PASSWORD=$(docker exec jenkins_master cat /var/jenkins_home/secrets/initialAdminPassword)
echo $JENKINS_PASSWORD
```

### **URLs d'accès**

```
HTTP:  http://localhost:8080
HTTPS: https://localhost/
SSH Agent: localhost:50000

Utilisateur: admin
Mot de passe: (voir ci-dessus)
```

### **Login administrateur**

```
1. Ouvrir: http://localhost:8080
2. Entrer le mot de passe initial
3. Installer plugins suggérés
4. Créer utilisateur admin
5. Terminer configuration
```

---

## 🔌 PLUGINS INSTALLES

### **Vérifier les plugins installés**

```bash
# Via UI: Jenkins → Manage Jenkins → Manage Plugins → Installed

# Via API:
curl -u admin:password http://localhost:8080/pluginManager/api/json?tree=plugins[shortName,version]

# Compter les plugins
curl -u admin:password http://localhost:8080/pluginManager/api/json?tree=plugins[shortName] | jq '.plugins | length'
```

### **Ajouter plugins supplémentaires**

```bash
# Éditer jenkins/plugins.txt et ajouter:
# example-plugin:latest

# Redéployer:
docker-compose down
docker-compose up -d
```

---

## ⚙️ CONFIGURATION JCasC

### **Vérifier JCasC est chargé**

```bash
# Jenkins → Manage Jenkins → Configuration as Code

# Via API:
curl -u admin:password http://localhost:8080/configuration-as-code/api/json
```

### **Valider YAML syntax**

```bash
# Utiliser un validateur YAML online:
# https://www.yamllint.com/

# Ou en local:
python3 -m pip install yamllint
yamllint jenkins/casc.yaml
```

### **Recharger configuration**

```bash
# Après modifications du casc.yaml:
docker exec jenkins_master \
  curl -X POST http://localhost:8080/configuration-as-code/reload \
  --user admin:password
```

---

## 🔐 SÉCURITÉ

### **Changer mot de passe admin**

```bash
# Jenkins UI → Manage Jenkins → Security → User Account

# Ou via CLI:
docker exec jenkins_master \
  java -jar /opt/jenkins.jar -c \
  "Jenkins.instance.securityRealm.createAccount('admin', 'new_password')"
```

### **Configurer email SMTP**

```bash
# .env - Update:
SMTP_HOST=smtp.gmail.com
EMAIL_USER=your_email@gmail.com
EMAIL_PASSWORD=your_app_specific_password

# Puis:
docker-compose restart jenkins
```

### **Configurer GitHub/GitLab tokens**

```bash
# GitHub: https://github.com/settings/tokens
# GitLab: https://gitlab.com/-/user_settings/personal_access_tokens

# Ajouter les secrets dans .env:
GITHUB_TOKEN=ghp_...
GITLAB_TOKEN=glpat_...

# Jenkins utilisera via JCasC
```

---

## 📈 MONITORING & LOGS

### **Logs en temps réel**

```bash
# Tous les services
docker-compose logs -f

# Seulement Jenkins
docker-compose logs -f jenkins

# Seulement PostgreSQL
docker-compose logs -f postgres

# Seulement Nginx
docker-compose logs -f nginx

# Les 100 dernières lignes
docker-compose logs --tail=100 jenkins
```

### **Accéder au système**

```bash
# Shell Jenkins
docker exec -it jenkins_master bash

# PostgreSQL
docker exec -it jenkins_postgres psql -U jenkins_user -d jenkins_db

# Nginx
docker exec -it jenkins_nginx bash
```

### **Métriques Prometheus (optionnel)**

```bash
# Si Prometheus plugin activé:
curl http://localhost:8080/metrics

# Pour Grafana:
# Data source: http://jenkins:8080/metrics
```

---

## 🐛 TROUBLESHOOTING

### **Jenkins ne démarre pas**

```bash
# Vérifier les logs
docker-compose logs jenkins

# Problèmes courants:
# 1. Pas assez de RAM: Augmenter JAVA_HEAP dans .env
# 2. Port déjà utilisé: Changer port dans docker-compose.yml
# 3. Erreur CASC: Vérifier YAML syntax

# Solution:
docker-compose down
# Corriger le problème
docker-compose up -d
```

### **PostgreSQL ne démarre pas**

```bash
# Vérifier les droits
docker exec jenkins_postgres pg_isready

# Réinitialiser les données
docker-compose down -v  # -v supprime les volumes!
docker-compose up -d
```

### **Nginx retourne 502 Bad Gateway**

```bash
# Vérifier Jenkins est accessible
docker exec jenkins_nginx curl http://jenkins:8080/login

# Vérifier logs Nginx
docker-compose logs nginx

# Redémarrer Nginx
docker-compose restart nginx
```

### **Plugins ne s'installent pas**

```bash
# Vérifier le fichier plugins.txt
cat jenkins/plugins.txt

# Réinstaller:
docker-compose down
docker-compose up --build
```

---

## 🧹 MAINTENANCE

### **Backup Jenkins Home**

```bash
# Créer une sauvegarde
docker exec jenkins_master tar czf - /var/jenkins_home | \
  gzip > jenkins_backup_$(date +%Y%m%d).tar.gz

# Restaurer à partir d'une sauvegarde
docker-compose down
gunzip < jenkins_backup_20240115.tar.gz | \
  docker exec -i jenkins_master tar xzf -
docker-compose up -d
```

### **Backup PostgreSQL**

```bash
# Full backup
docker exec jenkins_postgres pg_dump -U jenkins_user jenkins_db | \
  gzip > postgres_backup_$(date +%Y%m%d).sql.gz

# Restore
gunzip < postgres_backup_20240115.sql.gz | \
  docker exec -i jenkins_postgres psql -U jenkins_user jenkins_db
```

### **Nettoyer les espaces**

```bash
# Supprimer les images non utilisées
docker image prune -a

# Supprimer les conteneurs arrêtés
docker container prune

# Supprimer les volumes non utilisés (attention!)
docker volume prune
```

### **Mise à jour Jenkins**

```bash
# Vérifier l'image disponible
docker pull jenkins/jenkins:lts-alpine

# Mettre à jour dans docker-compose.yml
# Redéployer:
docker-compose down
docker-compose up -d
```

---

## 🛑 ARRÊT & REDÉMARRAGE

### **Arrêt gracieux**

```bash
# Arrêter tous les services
docker-compose down

# Conserver les données
# (volumes ne sont pas supprimés)
```

### **Arrêt complet avec suppression données**

```bash
# ⚠️  ATTENTION: Supprime TOUS les données!
docker-compose down -v
```

### **Redémarrer**

```bash
docker-compose restart

# Ou redémarrer un service spécifique
docker-compose restart jenkins
```

---

## 📝 NOTES IMPORTANTES

```
1. SÉCURITÉ
   - Changer tous les mots de passe dans .env
   - Utiliser SSL/TLS en production
   - Configurer firewall
   - Mettre à jour régulièrement

2. PERFORMANCE
   - Ajuster JAVA_HEAP selon besoins (4G-8G)
   - PostgreSQL optimisé pour 256MB+ RAM
   - Nginx caching activé
   - G1GC configured pour latency

3. BACKUP
   - Backuper jenkins_home régulièrement
   - Backuper PostgreSQL
   - Tester les restaurations

4. MONITORING
   - Suivre les logs
   - Configurer email notifications
   - Ajouter monitoring (Prometheus/Grafana)
   - Alertes sur webhook failures

5. SCALING
   - Ajouter agents Jenkins pour distributed builds
   - Load balancer en front (nginx est inclus)
   - Augmenter executors si besoin
```

---

## 📞 SUPPORT COMMANDES

```bash
# Voir tous les services
docker-compose ps

# Redémarrer un service
docker-compose restart SERVICE_NAME

# Arrêter un service
docker-compose stop SERVICE_NAME

# Démarrer un service
docker-compose start SERVICE_NAME

# Voir les logs détaillés
docker-compose logs SERVICE_NAME

# Exécuter une commande
docker exec CONTAINER_NAME COMMAND

# Entrer en shell
docker exec -it CONTAINER_NAME /bin/bash

# Copier un fichier
docker cp LOCAL_FILE CONTAINER_NAME:/REMOTE_PATH
docker cp CONTAINER_NAME:/REMOTE_FILE LOCAL_FILE
```

---

## 🎉 SETUP COMPLET!

**Maintenant tu as:**
- ✅ Jenkins LTS dernière version
- ✅ PostgreSQL pour données
- ✅ Nginx reverse proxy avec SSL
- ✅ 100+ plugins pré-configurés
- ✅ JCasC pour configuration automatique
- ✅ Docker-in-Docker support
- ✅ Performance tuning optimisé
- ✅ Backups & monitoring ready

**Prochaines étapes:**
1. Démarrer les services: `docker-compose up -d`
2. Accéder à Jenkins: http://localhost:8080
3. Créer des jobs/pipelines
4. Configurer webhooks GitHub/GitLab
5. Ajouter agents distributifs si besoin

---

**Bon déploiement! 🚀**
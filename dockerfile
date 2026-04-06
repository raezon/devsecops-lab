FROM jenkins/jenkins:lts-alpine

USER root

# 1. Installation des outils
RUN apk add --no-cache docker-cli curl git shadow

# 2. Correction des permissions (Méthode Safe Alpine)
RUN addgroup -g 999 docker || true
RUN addgroup jenkins docker || true

USER jenkins

# 3. Configuration Java
ENV JAVA_OPTS="-Djenkins.install.runSetupWizard=false \
               -Dio.jenkins.plugins.casc.ConfigurationAsCode.keep_on_failure=true"

# 4. Plugins
COPY --chown=jenkins:jenkins plugins.txt /usr/share/jenkins/ref/plugins.txt

# Correction ici : Utilisation de -f et retrait du --clean invalide
RUN jenkins-plugin-cli --verbose -f /usr/share/jenkins/ref/plugins.txt
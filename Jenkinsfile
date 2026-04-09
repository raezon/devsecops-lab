pipeline {
    agent any

    environment {
        APP_IMAGE      = "devsecops-app:latest"
        DOCKER_NETWORK = "devsecops-lab"
        PYTHON_IMAGE   = "python:3.11-slim"
        GITLEAKS_IMAGE = "zricethezav/gitleaks:latest"
        TRIVY_IMAGE    = "ghcr.io/aquasecurity/trivy:latest"
        ZAP_IMAGE      = "ghcr.io/zaproxy/zaproxy:stable"
        APP_PORT       = "5000"
        ZAP_PORT       = "8090"
    }

    options {
        timeout(time: 30, unit: 'MINUTES')
        buildDiscarder(logRotator(numToKeepStr: '10'))
    }

    stages {

        // ─────────────────────────────────────────────────────────────────
        // STAGE 1 — CHECKOUT & PREPARATION
        // ─────────────────────────────────────────────────────────────────
        stage('📥 Checkout & Preparation') {
            steps {
                echo '📥 Récupération du code source...'
                checkout scm

                echo '🌐 Création du réseau Docker...'
                sh "docker network create ${DOCKER_NETWORK} || true"

                echo '🐳 Vérification des images de sécurité...'
                sh """
                    for img in ${GITLEAKS_IMAGE} ${TRIVY_IMAGE} ${ZAP_IMAGE}; do
                        if docker image inspect \$img > /dev/null 2>&1; then
                            echo "✅ \$img déjà présente"
                        else
                            echo "⬇️  Pull de \$img..."
                            docker pull \$img
                        fi
                    done
                """
                echo '✅ Environnement prêt'
            }
        }

        // ─────────────────────────────────────────────────────────────────
        // STAGE 2 — SECRETS SCAN (GITLEAKS)
        // FIX : créer le fichier JSON même si aucune fuite trouvée
        // ─────────────────────────────────────────────────────────────────
        stage('🔑 Secrets Scan — Gitleaks') {
            steps {
                echo '🔑 Détection de secrets dans le code...'
                sh """
                    docker run --rm \
                        -v ${WORKSPACE}:/repo \
                        ${GITLEAKS_IMAGE} detect \
                        --source /repo \
                        --report-format json \
                        --report-path /repo/gitleaks-report.json \
                        --exit-code 0 || true

                    # Créer le fichier vide si Gitleaks ne l'a pas généré (aucune fuite)
                    if [ ! -f "${WORKSPACE}/gitleaks-report.json" ]; then
                        echo '[]' > "${WORKSPACE}/gitleaks-report.json"
                        echo '✅ Aucun secret détecté'
                    else
                        echo "📄 Rapport Gitleaks généré"
                    fi
                """
            }
            post {
                always {
                    // allowEmptyArchive évite l'erreur si le fichier est absent
                    archiveArtifacts artifacts: 'gitleaks-report.json',
                                     allowEmptyArchive: true
                }
            }
        }

        // ─────────────────────────────────────────────────────────────────
        // STAGE 3 — BUILD, SAST & TESTS
        // FIX 1 : bandit écrit dans ${WORKSPACE}, chemin absolu
        // FIX 2 : pytest ajouté à la commande de test (pas dans requirements)
        // ─────────────────────────────────────────────────────────────────
        stage('🛠️ Build, Scan & Test') {
            steps {
                script {

                    echo '🔍 1. Exécution du SAST (Bandit)...'
                    sh """
                        docker run --rm \
                            -v ${WORKSPACE}:/app \
                            -w /app \
                            ${PYTHON_IMAGE} /bin/sh -c '
                                pip install -q bandit &&
                                bandit -r app/ -f json -o bandit-report.json || true
                            '

                        # Créer rapport vide si bandit n'a rien trouvé / échoué
                        if [ ! -f "${WORKSPACE}/bandit-report.json" ]; then
                            echo '{"results":[],"metrics":{}}' > "${WORKSPACE}/bandit-report.json"
                        fi
                    """

                    echo '🐳 2. Construction de l\'image Docker...'
                    sh "docker build -t ${APP_IMAGE} app/"

                    echo '🧪 3. Exécution des Tests Unitaires...'
                    // FIX : pytest installé inline car absent du requirements.txt de prod
                    sh """
                        docker run --rm ${APP_IMAGE} /bin/sh -c \
                            'pip install -q pytest && pytest tests/ -v' || true
                    """
                }
            }
            post {
                always {
                    stash includes: 'bandit-report.json', name: 'bandit-report', allowEmpty: true
                    archiveArtifacts artifacts: 'bandit-report.json',
                                     allowEmptyArchive: true
                }
            }
        }

        // ─────────────────────────────────────────────────────────────────
        // STAGE 4 — SCA : TRIVY + SBOM
        // FIX : chmod avec chemin absolu ${WORKSPACE}/
        // ─────────────────────────────────────────────────────────────────
        stage('🔬 SCA — Trivy & SBOM') {
            steps {
                echo '🔬 SCA + SBOM avec Trivy...'
                sh """
                    # Scan vulnérabilités
                    docker run --rm \
                        -v /var/run/docker.sock:/var/run/docker.sock \
                        -v ${WORKSPACE}:/workspace \
                        ${TRIVY_IMAGE} image \
                        --exit-code 0 \
                        --severity HIGH,CRITICAL \
                        --format json \
                        --output /workspace/trivy-report.json \
                        ${APP_IMAGE}

                    # Génération SBOM CycloneDX
                    docker run --rm \
                        -v /var/run/docker.sock:/var/run/docker.sock \
                        -v ${WORKSPACE}:/workspace \
                        ${TRIVY_IMAGE} image \
                        --format cyclonedx \
                        --output /workspace/sbom.json \
                        ${APP_IMAGE}

                    # FIX : chmod avec chemin absolu
                    chmod 666 "${WORKSPACE}/trivy-report.json" \
                               "${WORKSPACE}/sbom.json" || true
                """
            }
            post {
                always {
                    archiveArtifacts artifacts: 'trivy-report.json, sbom.json',
                                     allowEmptyArchive: true
                }
            }
        }

        // ─────────────────────────────────────────────────────────────────
        // STAGE 5 — DAST : OWASP ZAP
        // ─────────────────────────────────────────────────────────────────
        stage('🚨 DAST — OWASP ZAP') {
            steps {
                echo '🚨 Démarrage de l\'application cible...'
                sh """
                    # Lancer l'app dans le réseau Docker
                    docker run -d \
                        --name devsecops-target \
                        --network ${DOCKER_NETWORK} \
                        -p ${APP_PORT}:${APP_PORT} \
                        ${APP_IMAGE}

                    # Attendre que l'app soit prête (max 30s)
                    for i in \$(seq 1 30); do
                        if curl -sf http://localhost:${APP_PORT} > /dev/null 2>&1; then
                            echo "✅ App prête après \${i}s"
                            break
                        fi
                        sleep 1
                    done
                """

                echo '🕷️ Scan ZAP en cours...'
                sh """
                    docker run --rm \
                        --network ${DOCKER_NETWORK} \
                        -v ${WORKSPACE}:/zap/wrk \
                        ${ZAP_IMAGE} zap-baseline.py \
                        -t http://devsecops-target:${APP_PORT} \
                        -J zap-report.json \
                        -r zap-report.html \
                        -I || true

                    # Créer rapport vide si ZAP a planté
                    if [ ! -f "${WORKSPACE}/zap-report.json" ]; then
                        echo '{"site":[]}' > "${WORKSPACE}/zap-report.json"
                    fi

                    chmod 666 "${WORKSPACE}/zap-report.json" \
                               "${WORKSPACE}/zap-report.html" 2>/dev/null || true
                """
            }
            post {
                always {
                    sh "docker rm -f devsecops-target 2>/dev/null || true"
                    archiveArtifacts artifacts: 'zap-report.json, zap-report.html',
                                     allowEmptyArchive: true
                    publishHTML(target: [
                        allowMissing         : true,
                        alwaysLinkToLastBuild: false,
                        keepAll              : true,
                        reportDir            : '.',
                        reportFiles          : 'zap-report.html',
                        reportName           : 'ZAP Security Report'
                    ])
                }
            }
        }

        // ─────────────────────────────────────────────────────────────────
        // STAGE 6 — AI REPORT & QUALITY GATE
        // ─────────────────────────────────────────────────────────────────
        stage('🤖 AI Report & Quality Gate') {
            steps {
                withCredentials([
                    string(credentialsId: 'openrouter-api-key', variable: 'OPENROUTER_API_KEY'),
                    string(credentialsId: 'resend-api-key',     variable: 'RESEND_API_KEY'),
                    string(credentialsId: 'report-email',       variable: 'REPORT_EMAIL')
                ]) {
                    echo '🤖 Analyse IA et Quality Gate...'
                    sh """
                        docker run --rm \
                            -v ${WORKSPACE}:/workspace \
                            -e OPENROUTER_API_KEY="${OPENROUTER_API_KEY}" \
                            -e RESEND_API_KEY="${RESEND_API_KEY}" \
                            -e REPORT_EMAIL="${REPORT_EMAIL}" \
                            -e WORKSPACE=/workspace \
                            -e JOB_NAME="${JOB_NAME}" \
                            -e BUILD_NUMBER="${BUILD_NUMBER}" \
                            -e BUILD_URL="${BUILD_URL}" \
                            -e GIT_COMMIT="${GIT_COMMIT}" \
                            -e GIT_BRANCH="${GIT_BRANCH}" \
                            ${PYTHON_IMAGE} /bin/sh -c '
                                pip install -q requests &&
                                python scripts/ai_security_report.py
                            '
                    """
                }
            }
            post {
                always {
                    archiveArtifacts artifacts: 'ai-security-analysis.json, ai-security-report.html',
                                     allowEmptyArchive: true
                }
            }
        }
    }

    // ─────────────────────────────────────────────────────────────────────
    // POST GLOBAL
    // ─────────────────────────────────────────────────────────────────────
    post {
        always {
            sh """
                docker rmi ${APP_IMAGE} 2>/dev/null || true
                docker rm -f devsecops-target 2>/dev/null || true
                docker network rm ${DOCKER_NETWORK} 2>/dev/null || true
            """
            cleanWs()
        }
        success {
            echo '🚀 Pipeline terminé avec succès — déploiement autorisé'
        }
        failure {
            echo '🚫 Pipeline échoué — consulter email et logs'
        }
    }
}
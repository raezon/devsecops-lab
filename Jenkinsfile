pipeline {
    agent any
    environment {
        APP_PORT           = '5000'
        ZAP_PORT           = '8090'
        DOCKER_NET         = 'devsecops-lab'
        OPENROUTER_API_KEY = credentials('openrouter-api-key')
        RESEND_API_KEY     = credentials('resend-api-key')
        REPORT_EMAIL       = credentials('report-email')
    }

    stages {

        // =============================================================
        //  CHECKOUT + PREPARATION
        // =============================================================
        stage('📥 Checkout & Preparation') {
            steps {
                echo '📥 Récupération du code source...'
                checkout scm

                echo '🌐 Création du réseau Docker...'
                sh 'docker network create ${DOCKER_NET} || true'

                echo '🐳 Préparation des images de sécurité...'
                sh '''
                    for IMAGE in \
                        zricethezav/gitleaks:latest \
                        ghcr.io/aquasecurity/trivy:latest \
                        ghcr.io/zaproxy/zaproxy:stable
                    do
                        docker image inspect $IMAGE > /dev/null 2>&1 \
                            && echo "✅ $IMAGE déjà présente" \
                            || (echo "⬇️ Pull $IMAGE..." && docker pull $IMAGE)
                    done
                '''
                echo '✅ Environnement prêt'
            }
        }

        // =============================================================
        //  SECRETS SCAN
        // =============================================================
        stage('🔑 Secrets Scan — Gitleaks') {
            steps {
                echo '🔑 Détection de secrets dans le code...'
                sh '''
                    docker run --rm \
                      -v "$(pwd)":/repo \
                      zricethezav/gitleaks:latest detect \
                        --source /repo \
                        --report-format json \
                        --report-path /repo/gitleaks-report.json \
                        --exit-code 0
                '''
            }
            post {
                always {
                    archiveArtifacts artifacts: 'gitleaks-report.json',
                                     allowEmptyArchive: true
                }
            }
        }

        // =============================================================
        //  BUILD TEST SAST
        // =============================================================
        // =============================================================
        //  FUSION : SAST, BUILD & TESTS
        // =============================================================
        stage('🛠️ Build, Scan & Test') {
            steps {
                script {
                    echo '🔍 1. Exécution du SAST (Bandit)...'
                    // On lance Bandit via un docker éphémère pour scanner le code source
                    sh '''
                        docker run --rm -v "$(pwd)":/app -w /app python:3.11-slim /bin/sh -c "
                            pip install -q bandit && \
                            bandit -r app/ -f json -o bandit-report.json || true
                        "
                    '''

                    echo '🐳 2. Construction de l\'image Docker...'
                    sh "docker build -t devsecops-app:latest app/"

                    echo '🧪 3. Exécution des Tests Unitaires...'
                    // On lance les tests DIRECTEMENT à l'intérieur de l'image qu'on vient de construire
                    // Pas besoin de réinstaller pytest dans Jenkins !
                    sh 'docker run --rm devsecops-app:latest pytest tests/ || true'
                }
            }
            post {
                always {
                    // On sauvegarde le rapport Bandit pour l'IA plus tard
                    stash name: 'bandit-report', includes: 'bandit-report.json', allowEmpty: true
                    archiveArtifacts artifacts: 'bandit-report.json', allowEmptyArchive: true
                }
            }
        }
        // =============================================================
        //  SCA TRIVY
        // =============================================================
        stage('🔬 SCA — Trivy & SBOM') {
            steps {
                echo '🔬 SCA + SBOM avec Trivy...'
                sh '''
                    docker run --rm \
                      -v /var/run/docker.sock:/var/run/docker.sock \
                      -v "$(pwd)":/workspace \
                      ghcr.io/aquasecurity/trivy:latest image \
                        --exit-code 0 \
                        --severity HIGH,CRITICAL \
                        --format json \
                        --output /workspace/trivy-report.json \
                        devsecops-app:latest
                '''
                sh '''
                    docker run --rm \
                      -v /var/run/docker.sock:/var/run/docker.sock \
                      -v "$(pwd)":/workspace \
                      ghcr.io/aquasecurity/trivy:latest image \
                        --format cyclonedx \
                        --output /workspace/sbom.json \
                        devsecops-app:latest
                '''
            }
            post {
                always {
                    archiveArtifacts artifacts: 'trivy-report.json, sbom.json',
                                     allowEmptyArchive: true
                }
            }
        }

        // =============================================================
        //  DAST ZAP
        // =============================================================
        stage('🚨 DAST — OWASP ZAP') {
            options {
                timeout(time: 10, unit: 'MINUTES')
                retry(2)
            }
            steps {
                echo '🚨 DAST avec OWASP ZAP...'
                sh '''
                    # 1. On s'assure que le dossier a les bons droits pour le conteneur
                    chmod 777 "$(pwd)"

                    # 2. Lancement de l'app (on augmente un peu le sleep pour être sûr)
                    docker run -d \
                    --name target-app \
                    --network ${DOCKER_NET} \
                    -p ${APP_PORT}:5000 \
                    devsecops-app:latest
                    sleep 10
                '''
                sh '''
                    # 3. On lance ZAP en spécifiant /zap/wrk/ pour les rapports
                    docker run --rm \
                    --user root \
                    --network ${DOCKER_NET} \
                    -v "$(pwd)":/zap/wrk:rw \
                    ghcr.io/zaproxy/zaproxy:stable \
                    zap-baseline.py \
                        -t http://target-app:5000 \
                        -r /zap/wrk/zap-report.html \
                        -J /zap/wrk/zap-report.json \
                        -I
                '''
            }
            post {
                always {
                    // On nettoie le conteneur cible
                    sh 'docker stop target-app || true'
                    sh 'docker rm target-app || true'
                    
                    // On archive même si le fichier est vide ou absent pour ne pas faire crash le pipeline
                    archiveArtifacts artifacts: 'zap-report.json', allowEmptyArchive: true
                    
                    publishHTML([
                        allowMissing:          true,
                        alwaysLinkToLastBuild: true,
                        keepAll:               true,
                        reportDir:             '.',
                        reportFiles:           'zap-report.html',
                        reportName:            'ZAP Security Report'
                    ])
                }
            }
        }

        // =============================================================
        //  AI SECURITY REPORT + QUALITY GATE
        // =============================================================
        stage('🤖 AI Report & Quality Gate') {
            steps {
                script {
                    echo '🤖 Analyse IA DeepSeek + Quality Gate...'

                    unstash 'bandit-report'

                    sh 'pip install requests --quiet || true'

                    def result = sh(
                        script: 'python3 -u scripts/ai_security_report.py', 
                        returnStatus: true
                    )

                    archiveArtifacts(
                        artifacts: 'ai-security-analysis.json, ai-security-report.html',
                        allowEmptyArchive: true
                    )

                    publishHTML([
                        allowMissing:          true,
                        alwaysLinkToLastBuild: true,
                        keepAll:               true,
                        reportDir:             '.',
                        reportFiles:           'ai-security-report.html',
                        reportName:            'AI Security Report'
                    ])

                    if (result != 0) {
                        error('🚫 DÉPLOIEMENT BLOQUÉ — Voir email AI pour détails')
                    }

                    echo '🚀 Quality Gate passée — déploiement autorisé !'
                }
            }
        }

    }

    // =============================================================
    //  POST — NETTOYAGE
    // =============================================================
    post {
        always {
            sh 'docker rmi  devsecops-app:latest || true'
            sh 'docker network rm ${DOCKER_NET} || true'
            cleanWs()
        }
        success {
            echo '✅ Pipeline terminé avec succès'
        }
        failure {
            echo '🚫 Pipeline échoué — consulter email et logs'
        }
    }
}
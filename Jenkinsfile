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
        stage('🔍 Build, Test & SAST') {
            agent {
                docker {
                    image 'python:3.11'
                    args  '-u root -e HOME=/tmp'
                }
            }
            steps {
                echo '🔧 Installation des dépendances...'
                sh 'pip install -q -r app/requirements.txt pytest'

                echo '🧪 Tests unitaires...'
                sh 'pytest app/tests/ -v --tb=short || true'

                echo '🔍 SAST — Bandit...'
                sh '''
                    bandit -r app/ \
                      -f json \
                      -o ${WORKSPACE}/bandit-report.json \
                      || true
                '''
                sh 'bandit -r app/ || true'
            }
            post {
                always {
                    stash name: 'bandit-report',
                          includes: 'bandit-report.json'
                    archiveArtifacts artifacts: 'bandit-report.json',
                                     allowEmptyArchive: true
                }
            }
        }

        // =============================================================
        //  DOCKER BUILD
        // =============================================================
        stage('🐳 Docker Build') {
            steps {
                echo '🐳 Construction de l\'image Docker...'
                sh """
                    docker build \
                      -t devsecops-app:latest \
                      -t devsecops-app:${env.BUILD_NUMBER} \
                      -t devsecops-app:${env.GIT_COMMIT.take(7)} \
                      app/
                """
                echo "🏷️ Tags: latest | ${env.BUILD_NUMBER} | ${env.GIT_COMMIT.take(7)}"
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
                    docker run -d \
                      --name target-app \
                      --network ${DOCKER_NET} \
                      -p ${APP_PORT}:5000 \
                      devsecops-app:latest
                    sleep 5
                '''
                sh '''
                    docker run --rm \
                      --user root \
                      --network ${DOCKER_NET} \
                      -p ${ZAP_PORT}:8090 \
                      -v "$(pwd)":/zap/wrk:rw \
                      ghcr.io/zaproxy/zaproxy:stable \
                      zap-baseline.py \
                        -t http://target-app:5000 \
                        -r zap-report.html \
                        -J zap-report.json \
                        -I
                '''
            }
            post {
                always {
                    sh 'docker stop target-app || true'
                    sh 'docker rm   target-app || true'
                    publishHTML([
                        allowMissing:          true,
                        alwaysLinkToLastBuild: true,
                        keepAll:               true,
                        reportDir:             '.',
                        reportFiles:           'zap-report.html',
                        reportName:            'ZAP Security Report'
                    ])
                    archiveArtifacts artifacts: 'zap-report.json',
                                     allowEmptyArchive: true
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
                        script: 'python3 scripts/ai_security_report.py',
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
            sh 'docker stop target-app || true'
            sh 'docker rm   target-app || true'
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
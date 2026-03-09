pipeline {
    agent any
    environment {
        APP_PORT   = '5000'
        ZAP_PORT   = '8090'
        DOCKER_NET = 'devsecops-lab'
    }
    stages {

        stage('Checkout') {
            steps {
                echo '📥 Récupération du code source...'
                checkout scm
            }
        }

        stage('Secrets Scan - Gitleaks') {
            steps {
                echo '🔑 Détection de secrets dans le code...'
                sh '''
                    docker image inspect zricethezav/gitleaks:latest > /dev/null 2>&1 \
                        && echo "✅ Gitleaks déjà présent" \
                        || docker pull zricethezav/gitleaks:latest
                '''
                sh '''
                    docker run --rm \
                      -v $(pwd):/repo \
                      zricethezav/gitleaks:latest detect \
                        --source /repo \
                        --report-format json \
                        --report-path /repo/gitleaks-report.json \
                        --exit-code 0
                '''
            }
            post {
                always {
                    archiveArtifacts artifacts: 'gitleaks-report.json', allowEmptyArchive: true
                }
            }
        }

        stage('Build, Test & SAST') {
            agent {
                docker {
                    image 'python:3.11-slim'
                    args  '-u root -e HOME=/tmp'
                }
            }
            steps {
                echo '🔧 Installation des dépendances...'
                sh 'pip install -q -r app/requirements.txt pytest'
                echo '🧪 Tests unitaires...'
                sh 'pytest tests/ -v'
                echo '🔍 SAST — Bandit...'
                sh 'bandit -r app/ -f json -o bandit-report.json || true'
                sh 'bandit -r app/ || true'
            }
            post {
                always {
                    stash name: 'bandit-report', includes: 'bandit-report.json'
                    archiveArtifacts artifacts: 'bandit-report.json', allowEmptyArchive: true
                }
            }
        }

        stage('Docker Build') {
            steps {
                echo '🐳 Construction de l\'image Docker...'
                sh """
                    docker build \
                      -t devsecops-app:latest \
                      -t devsecops-app:${env.BUILD_NUMBER} \
                      -t devsecops-app:${env.GIT_COMMIT.take(7)} \
                      .
                """
                echo "🏷️ Tags : latest | ${env.BUILD_NUMBER} | ${env.GIT_COMMIT.take(7)}"
            }
        }

        stage('SCA - Trivy Scan & SBOM') {
            steps {
                echo '🔬 SCA + SBOM avec Trivy...'
                sh '''
                    docker image inspect aquasec/trivy:latest > /dev/null 2>&1 \
                        && echo "✅ Trivy déjà présent" \
                        || docker pull aquasec/trivy:latest
                '''
                sh '''
                    docker run --rm \
                      -v /var/run/docker.sock:/var/run/docker.sock \
                      -v $(pwd):/workspace \
                      aquasec/trivy:latest image \
                        --exit-code 0 \
                        --severity HIGH,CRITICAL \
                        --format json \
                        --output /workspace/trivy-report.json \
                        devsecops-app:latest
                '''
                sh '''
                    docker run --rm \
                      -v /var/run/docker.sock:/var/run/docker.sock \
                      -v $(pwd):/workspace \
                      aquasec/trivy:latest image \
                        --format cyclonedx \
                        --output /workspace/sbom.json \
                        devsecops-app:latest
                '''
            }
            post {
                always {
                    archiveArtifacts artifacts: 'trivy-report.json, sbom.json', allowEmptyArchive: true
                }
            }
        }

        stage('DAST - OWASP ZAP Pentest') {
            options {
                timeout(time: 10, unit: 'MINUTES')
                retry(2)
            }
            steps {
                echo '🚨 DAST avec OWASP ZAP...'
                sh '''
                    docker image inspect ghcr.io/zaproxy/zaproxy:stable > /dev/null 2>&1 \
                        && echo "✅ ZAP déjà présent" \
                        || docker pull ghcr.io/zaproxy/zaproxy:stable
                '''
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
                      -v $(pwd):/zap/wrk:rw \
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
                        allowMissing: true,
                        reportDir:    '.',
                        reportFiles:  'zap-report.html',
                        reportName:   'ZAP Security Report'
                    ])
                    archiveArtifacts artifacts: 'zap-report.json', allowEmptyArchive: true
                }
            }
        }

        stage('Quality Gate') {
            steps {
                script {
                    echo '🔎 Quality Gate...'
                    unstash 'bandit-report'
                    def result = sh(
                        script: 'python3 scripts/quality_gate.py',
                        returnStatus: true
                    )
                    env.SECURITY_SUMMARY = fileExists('security-summary.txt')
                        ? readFile('security-summary.txt')
                        : 'Rapport non disponible.'
                    if (result != 0) {
                        error('🚫 DÉPLOIEMENT BLOQUÉ — Vulnérabilités détectées !')
                    }
                    echo '🚀 Quality Gate passée — déploiement autorisé !'
                }
            }
        }
    }

    post {
        success {
            echo '✅ Pipeline terminé — déploiement autorisé !'
            emailext(
                to:       'amardjebabla10@gmail.com',
                from:     'onboarding@resend.dev',
                subject:  "✅ [${env.JOB_NAME}] Build #${env.BUILD_NUMBER} — Quality Gate OK",
                mimeType: 'text/html',
                body:     """
<html><body style="font-family:Arial,sans-serif;color:#1e293b;">

<table width="100%" style="background:#1A2B4A;padding:24px;">
  <tr><td>
    <h1 style="color:white;margin:0;">✅ Déploiement autorisé</h1>
    <p style="color:#93C5FD;margin:4px 0 0;">${env.JOB_NAME} — Build #${env.BUILD_NUMBER}</p>
  </td></tr>
</table>

<table width="100%" style="padding:16px;">
  <tr>
    <td style="padding:4px;"><b>Pipeline</b></td><td>${env.JOB_NAME}</td>
    <td style="padding:4px;"><b>Build</b></td><td>#${env.BUILD_NUMBER}</td>
  </tr>
  <tr>
    <td style="padding:4px;"><b>Commit</b></td><td>${env.GIT_COMMIT}</td>
    <td style="padding:4px;"><b>Branch</b></td><td>${env.GIT_BRANCH}</td>
  </tr>
</table>

<table width="100%" style="background:#F1F5F9;padding:16px;border-left:4px solid #2563EB;">
  <tr><td>
    <h3 style="color:#1A2B4A;margin:0 0 12px;">🔎 Résultats Sécurité</h3>
    <pre style="font-size:13px;white-space:pre-wrap;">${env.SECURITY_SUMMARY}</pre>
  </td></tr>
</table>

<table width="100%" style="padding:16px;">
  <tr>
    <td><a href="${env.BUILD_URL}" style="background:#2563EB;color:white;padding:10px 20px;text-decoration:none;border-radius:4px;">🔗 Voir le Build</a></td>
    <td><a href="${env.BUILD_URL}artifact/" style="background:#0D9488;color:white;padding:10px 20px;text-decoration:none;border-radius:4px;">📦 Voir les Rapports</a></td>
    <td><a href="${env.BUILD_URL}ZAP_20Security_20Report/" style="background:#EA580C;color:white;padding:10px 20px;text-decoration:none;border-radius:4px;">🚨 Rapport ZAP</a></td>
  </tr>
</table>

</body></html>
"""
            )
        }

        failure {
            echo '❌ Pipeline échoué — déploiement BLOQUÉ.'
            emailext(
                to:       'amardjebabla10@gmail.com',
                from:     'onboarding@resend.dev',
                subject:  "🚫 [${env.JOB_NAME}] Build #${env.BUILD_NUMBER} — DÉPLOIEMENT BLOQUÉ",
                mimeType: 'text/html',
                body:     """
<html><body style="font-family:Arial,sans-serif;color:#1e293b;">

<table width="100%" style="background:#DC2626;padding:24px;">
  <tr><td>
    <h1 style="color:white;margin:0;">🚫 Déploiement BLOQUÉ</h1>
    <p style="color:#FCA5A5;margin:4px 0 0;">${env.JOB_NAME} — Build #${env.BUILD_NUMBER}</p>
  </td></tr>
</table>

<table width="100%" style="padding:16px;">
  <tr>
    <td style="padding:4px;"><b>Pipeline</b></td><td>${env.JOB_NAME}</td>
    <td style="padding:4px;"><b>Build</b></td><td>#${env.BUILD_NUMBER}</td>
  </tr>
  <tr>
    <td style="padding:4px;"><b>Commit</b></td><td>${env.GIT_COMMIT}</td>
    <td style="padding:4px;"><b>Branch</b></td><td>${env.GIT_BRANCH}</td>
  </tr>
</table>

<table width="100%" style="background:#FFF1F2;padding:16px;border-left:4px solid #DC2626;">
  <tr><td>
    <h3 style="color:#DC2626;margin:0 0 12px;">🔎 Résultats Sécurité</h3>
    <pre style="font-size:13px;white-space:pre-wrap;">${env.SECURITY_SUMMARY ?: 'Non disponible.'}</pre>
  </td></tr>
</table>

<table width="100%" style="background:#FFF7ED;padding:16px;border-left:4px solid #EA580C;margin-top:12px;">
  <tr><td>
    <h3 style="color:#EA580C;margin:0 0 8px;">⚡ Action requise</h3>
    <p style="margin:0;">Corriger les vulnérabilités listées ci-dessus avant de relancer le pipeline.</p>
  </td></tr>
</table>

<table width="100%" style="padding:16px;">
  <tr>
    <td><a href="${env.BUILD_URL}console" style="background:#DC2626;color:white;padding:10px 20px;text-decoration:none;border-radius:4px;">📋 Voir les Logs</a></td>
    <td><a href="${env.BUILD_URL}artifact/" style="background:#0D9488;color:white;padding:10px 20px;text-decoration:none;border-radius:4px;">📦 Voir les Rapports</a></td>
    <td><a href="${env.BUILD_URL}ZAP_20Security_20Report/" style="background:#EA580C;color:white;padding:10px 20px;text-decoration:none;border-radius:4px;">🚨 Rapport ZAP</a></td>
  </tr>
</table>

</body></html>
"""
            )
        }
    }
}

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
                
                sh 'docker network create devsecops-lab || true'

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
                        allowMissing:          true,
                        alwaysLinkToLastBuild: true,
                        keepAll:               true,
                        reportDir:             '.',
                        reportFiles:           'zap-report.html',
                        reportName:            'ZAP Security Report'
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
        always {
            script {
                def isOk    = currentBuild.result == null || currentBuild.result == 'SUCCESS'
                def summary = env.SECURITY_SUMMARY ?: 'Pipeline échoué avant la Quality Gate — consulte les logs.'
                def color   = isOk ? '#1A2B4A' : '#DC2626'
                def subColor= isOk ? '#93C5FD' : '#FCA5A5'
                def border  = isOk ? '#2563EB' : '#DC2626'
                def status  = isOk ? '✅ Déploiement autorisé' : '🚫 Déploiement BLOQUÉ'
                def subject = isOk
                    ? "✅ [${env.JOB_NAME}] Build #${env.BUILD_NUMBER} — Quality Gate OK"
                    : "🚫 [${env.JOB_NAME}] Build #${env.BUILD_NUMBER} — DÉPLOIEMENT BLOQUÉ"

                emailext(
                    to:       'amardjebabla10@gmail.com',
                    from:     'onboarding@resend.dev',
                    subject:  subject,
                    mimeType: 'text/html',
                    body:     """
<html>
<body style="font-family:Arial,sans-serif;color:#1e293b;margin:0;padding:0;">

  <!-- HEADER -->
  <table width="100%" cellpadding="0" cellspacing="0" style="background:${color};padding:28px 24px;">
    <tr><td>
      <h1 style="color:white;margin:0;font-size:22px;">${status}</h1>
      <p style="color:${subColor};margin:6px 0 0;font-size:14px;">${env.JOB_NAME} — Build #${env.BUILD_NUMBER}</p>
    </td></tr>
  </table>

  <!-- BUILD INFO -->
  <table width="100%" cellpadding="0" cellspacing="0" style="padding:16px 24px;border-bottom:1px solid #E2E8F0;">
    <tr>
      <td style="padding:6px 12px 6px 0;width:120px;color:#6B7280;font-size:13px;"><b>Pipeline</b></td>
      <td style="padding:6px;font-size:13px;">${env.JOB_NAME}</td>
      <td style="padding:6px 12px 6px 24px;width:120px;color:#6B7280;font-size:13px;"><b>Build</b></td>
      <td style="padding:6px;font-size:13px;">#${env.BUILD_NUMBER}</td>
    </tr>
    <tr>
      <td style="padding:6px 12px 6px 0;color:#6B7280;font-size:13px;"><b>Commit</b></td>
      <td style="padding:6px;font-size:13px;font-family:monospace;">${env.GIT_COMMIT ?: 'N/A'}</td>
      <td style="padding:6px 12px 6px 24px;color:#6B7280;font-size:13px;"><b>Branch</b></td>
      <td style="padding:6px;font-size:13px;">${env.GIT_BRANCH ?: 'N/A'}</td>
    </tr>
  </table>

  <!-- SECURITY RESULTS -->
  <table width="100%" cellpadding="0" cellspacing="0"
         style="margin:16px 0;background:#F8FAFC;border-left:4px solid ${border};padding:16px 20px;">
    <tr><td>
      <h3 style="color:#1A2B4A;margin:0 0 12px;font-size:15px;">🔎 Résultats Sécurité</h3>
      <pre style="font-size:12px;white-space:pre-wrap;margin:0;color:#1e293b;line-height:1.6;">${summary}</pre>
    </td></tr>
  </table>

  <!-- ACTION REQUIRED (failure only) -->
  ${isOk ? '' : """
  <table width="100%" cellpadding="0" cellspacing="0"
         style="margin:12px 0;background:#FFF7ED;border-left:4px solid #EA580C;padding:16px 20px;">
    <tr><td>
      <h3 style="color:#EA580C;margin:0 0 6px;font-size:15px;">⚡ Action requise</h3>
      <p style="margin:0;font-size:13px;">Corriger les vulnérabilités listées ci-dessus avant de relancer le pipeline.</p>
    </td></tr>
  </table>
  """}

  <!-- BUTTONS -->
  <table width="100%" cellpadding="0" cellspacing="0" style="padding:16px 24px 24px;">
    <tr>
      <td style="padding-right:8px;">
        <a href="${env.BUILD_URL}console"
           style="display:inline-block;background:#1A2B4A;color:white;padding:10px 18px;
                  text-decoration:none;border-radius:4px;font-size:13px;">
          📋 Logs Jenkins
        </a>
      </td>
      <td style="padding-right:8px;">
        <a href="${env.BUILD_URL}artifact/"
           style="display:inline-block;background:#0D9488;color:white;padding:10px 18px;
                  text-decoration:none;border-radius:4px;font-size:13px;">
          📦 Rapports
        </a>
      </td>
      <td>
        <a href="${env.BUILD_URL}ZAP_20Security_20Report/"
           style="display:inline-block;background:#EA580C;color:white;padding:10px 18px;
                  text-decoration:none;border-radius:4px;font-size:13px;">
          🚨 Rapport ZAP
        </a>
      </td>
    </tr>
  </table>

  <!-- FOOTER -->
  <table width="100%" cellpadding="0" cellspacing="0"
         style="background:#F1F5F9;padding:12px 24px;border-top:1px solid #E2E8F0;">
    <tr><td style="font-size:11px;color:#94A3B8;text-align:center;">
      DevSecOps Pipeline — Jenkins CI/CD — ${new Date().format('dd/MM/yyyy HH:mm')}
    </td></tr>
  </table>

</body>
</html>
"""
                )
            }
        }
    }
}
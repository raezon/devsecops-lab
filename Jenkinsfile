// Jenkinsfile
pipeline {
    agent any
    environment {
        APP_PORT   = '5000'
        ZAP_PORT   = '8090'
        DOCKER_NET = 'devsecops-lab'
    }
    stages {

        // ── STAGE 1 : Checkout ──
        stage('Checkout') {
            steps {
                echo '📥 Récupération du code source...'
                checkout scm
            }
        }

        // ── STAGE 2 : Build & Tests unitaires ──
        stage('Build & Test') {
            agent {
                docker {
                    image 'python:3.11-slim'
                    args '-u root -e HOME=/tmp'
                }
            
            }
            steps {
                echo '🔧 Installation des dépendances...'
                sh '''
                    pip install -q \
                        $(pip show flask   2>/dev/null | grep -q flask   || echo flask==2.3.3) \
                        $(pip show pytest  2>/dev/null | grep -q pytest  || echo pytest) \
                        $(pip show bandit  2>/dev/null | grep -q bandit  || echo bandit==1.7.5) \
                    || pip install -q flask==2.3.3 pytest bandit==1.7.5
                '''
                echo '🧪 Exécution des tests unitaires...'
                sh 'pytest tests/ -v'
            }
        }

        // ── STAGE 3 : SAST avec Bandit ──
        stage('SAST - Bandit Security Scan') {
            agent {
                docker {
                    image 'python:3.11-slim'
                    args '-u root -e HOME=/tmp'
                }
            }
            steps {
                echo '🔍 Analyse de sécurité statique (SAST)...'
                sh '''
                    pip show bandit > /dev/null 2>&1 || pip install -q bandit==1.7.5
                    echo "✅ Bandit version : $(bandit --version)"
                '''
                sh 'bandit -r app/ -f json -o bandit-report.json || true'
                sh 'bandit -r app/ || true'
            }
            post {
                always {
                    archiveArtifacts artifacts: 'bandit-report.json',
                                     allowEmptyArchive: true
                }
            }
        }

        // ── STAGE 4 : Docker Build ──
        stage('Docker Build') {
            steps {
                echo '🐳 Construction de l\'image Docker...'
                sh 'docker build -t devsecops-app:latest .'
            }
        }
        // ── STAGE 4.5 : SCA avec Trivy ──
        stage('SCA - Trivy Scan') {
            steps {
                echo '🔬 Analyse des dépendances et de l\'image (SCA)...'

                // Pull Trivy seulement si pas déjà présent
                sh '''
                    docker image inspect aquasec/trivy:latest > /dev/null 2>&1 \
                        && echo "✅ Image Trivy déjà présente — skip pull" \
                        || docker pull aquasec/trivy:latest
                '''

                // Scanner et générer le rapport JSON
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

                // Afficher un résumé lisible dans les logs
                sh '''
                    docker run --rm \
                    -v /var/run/docker.sock:/var/run/docker.sock \
                    aquasec/trivy:latest image \
                        --exit-code 0 \
                        --severity HIGH,CRITICAL \
                        devsecops-app:latest
                '''
            }
            post {
                always {
                    archiveArtifacts artifacts: 'trivy-report.json',
                                    allowEmptyArchive: true
                }
            }
        }

        // ── STAGE 5 : DAST avec OWASP ZAP ──
        stage('DAST - OWASP ZAP Pentest') {
            steps {
                echo '🚨 Lancement du pentest dynamique avec OWASP ZAP...'

                // Pull ZAP seulement si pas déjà présent localement
                sh '''
                    docker image inspect ghcr.io/zaproxy/zaproxy:stable > /dev/null 2>&1 \
                        && echo "✅ Image ZAP déjà présente — skip pull" \
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
                    archiveArtifacts artifacts: 'zap-report.json',
                                     allowEmptyArchive: true
                }
            }
        }

        // ── STAGE 6 : Quality Gate ──
        stage('Quality Gate') {
            steps {
                script {
                    echo '🔎 Vérification des seuils de sécurité...'

                    def result = sh(
                        script: '''
                            python3 - <<'EOF'
        import json, sys, os

        issues = []

        # ── Bandit ──
        if os.path.exists('bandit-report.json'):
            with open('bandit-report.json') as f:
                d = json.load(f)
            totals  = d.get('metrics', {}).get('_totals', {})
            high    = int(totals.get('SEVERITY.HIGH',   0))
            medium  = int(totals.get('SEVERITY.MEDIUM', 0))
            print(f"Bandit — HIGH: {high}  MEDIUM: {medium}")
            if high > 0 or medium > 1:
                issues.append(f"BANDIT BLOQUE (HIGH={high}, MEDIUM={medium})")
            else:
                print("OK Bandit")
        else:
            print("WARN bandit-report.json introuvable")

        # ── ZAP ──
        if os.path.exists('zap-report.json'):
            with open('zap-report.json') as f:
                d = json.load(f)
            high   = sum(1 for s in d.get('site',[]) for a in s.get('alerts',[]) if int(a.get('riskcode',0)) == 3)
            medium = sum(1 for s in d.get('site',[]) for a in s.get('alerts',[]) if int(a.get('riskcode',0)) == 2)
            print(f"ZAP — HIGH: {high}  MEDIUM: {medium}")
            if high > 0 or medium > 1:
                issues.append(f"ZAP BLOQUE (HIGH={high}, MEDIUM={medium})")
            else:
                print("OK ZAP")
        else:
            print("WARN zap-report.json introuvable")

        if issues:
            print("GATE_FAIL: " + " | ".join(issues))
            sys.exit(1)
        else:
            print("GATE_PASS")
            sys.exit(0)
        EOF
                        ''',
                        returnStatus: true
                    )

                    if (result != 0) {
                        error("🚫 DÉPLOIEMENT BLOQUÉ — Vulnérabilités détectées ! Consulte les rapports.")
                    } else {
                        echo "🚀 Quality Gate passée — déploiement autorisé !"
                    }
                }
            }
        }
    }

    post {
        success {
            echo '✅ Pipeline terminé — Quality Gate OK — déploiement autorisé !'
        }
        failure {
            echo '❌ Pipeline échoué — déploiement BLOQUÉ. Consulte les rapports Bandit et ZAP.'
        }
    }
}
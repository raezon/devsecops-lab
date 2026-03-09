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

                    // ── Vérification Bandit ──
                    def banditOk = true
                    if (fileExists('bandit-report.json')) {
                        def bandit = readJSON file: 'bandit-report.json'

                        def highCount   = bandit.metrics['_totals']['SEVERITY.HIGH']   ?: 0
                        def mediumCount = bandit.metrics['_totals']['SEVERITY.MEDIUM'] ?: 0

                        echo "Bandit — HIGH: ${highCount}  MEDIUM: ${mediumCount}"

                        if (highCount > 0 || mediumCount > 1) {
                            echo "❌ BANDIT : seuil dépassé (HIGH=${highCount}, MEDIUM=${mediumCount})"
                            banditOk = false
                        } else {
                            echo "✅ BANDIT : seuil respecté"
                        }
                    } else {
                        echo "⚠️ bandit-report.json introuvable — skip"
                    }

                    // ── Vérification ZAP ──
                    def zapOk = true
                    if (fileExists('zap-report.json')) {
                        def zap = readJSON file: 'zap-report.json'

                        def zapHigh   = 0
                        def zapMedium = 0

                        zap.site.each { site ->
                            site.alerts.each { alert ->
                                def risk = alert.riskcode as Integer
                                if (risk == 3) zapHigh++
                                if (risk == 2) zapMedium++
                            }
                        }

                        echo "ZAP — HIGH: ${zapHigh}  MEDIUM: ${zapMedium}"

                        if (zapHigh > 0 || zapMedium > 1) {
                            echo "❌ ZAP : seuil dépassé (HIGH=${zapHigh}, MEDIUM=${zapMedium})"
                            zapOk = false
                        } else {
                            echo "✅ ZAP : seuil respecté"
                        }
                    } else {
                        echo "⚠️ zap-report.json introuvable — skip"
                    }

                    // ── Décision finale ──
                    if (!banditOk || !zapOk) {
                        error("🚫 DÉPLOIEMENT BLOQUÉ — Vulnérabilités MEDIUM > 1 ou HIGH détectées !")
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
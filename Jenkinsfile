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
            steps{
                script{
                    def runCheckout = load 'jenkins/stages/checkout.groovy'
                    runCheckout.runCheckout()
                }
            }
        }

        // ─────────────────────────────────────────────────────────────────
        // STAGE 2 — SECRETS SCAN (GITLEAKS)
        // ─────────────────────────────────────────────────────────────────
        stage('🔑 Secrets Scan — Gitleaks') {
            script{
                    def runSecretsScan = load 'jenkins/stages/stage2.groovy'
                    runSecretsScan.runSecretsScan()
                }
            
        }

        // ─────────────────────────────────────────────────────────────────
        // STAGE 3 — BUILD, SAST (BANDIT) & TESTS
        // ─────────────────────────────────────────────────────────────────
        stage('🛠️ Build, Scan & Test') {
            script{
                def runBuildAndScan = load 'jenkins/stages/stage3.groovy'
                runBuildAndScan.runBuildAndScan()
            }
        }

        // ─────────────────────────────────────────────────────────────────
        // STAGE 4 — SCA : TRIVY + SBOM
        // ─────────────────────────────────────────────────────────────────
        stage('🔬 SCA — Trivy & SBOM') {
            steps{
                script{
                    def runScan = load 'jenkins/stages/stage4.groovy'
                    runScan.runScan()
                }
            }
        }

        // ─────────────────────────────────────────────────────────────────
        // STAGE 5 — DAST : OWASP ZAP
        // ─────────────────────────────────────────────────────────────────
        stage('🚨 DAST — OWASP ZAP') {
            steps{
                script{
                    def runOwaspZap = load 'jenkins/stages/stage5.groovy'
                    runOwaspZap.runOwaspZap()
                }
            }

        }

        // ─────────────────────────────────────────────────────────────────
        // STAGE 6 — AI REPORT & QUALITY GATE
        // script/ai_security_report.py est dans le repo → checkout le fournit
        // ─────────────────────────────────────────────────────────────────
        stage('🤖 AI Report & Quality Gate') {
            steps{
                script{
                    def runAiReports = load 'jenkins/stages/stage6.groovy'
                    runAiReports.runAiReports()
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
            echo '🚫 Pipeline échoué — consulter les logs et rapports'
        }
    }
}
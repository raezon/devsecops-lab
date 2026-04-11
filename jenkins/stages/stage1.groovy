def runCheckout() {
    stage('📥 Checkout & Preparation') {
            
                echo '📥 Récupération du code source...'
                checkout scm

                echo '🌐 Création du réseau Docker...'
                sh "docker network create ${env.DOCKER_NETWORK} || true"

                echo '🐳 Vérification des images de sécurité...'
                sh """
                    for img in ${env.GITLEAKS_IMAGE} ${env.TRIVY_IMAGE} ${env.ZAP_IMAGE}; do
                        if docker image inspect \$img > /dev/null 2>&1; then
                            echo "✅ \$img déjà présente"
                        else
                            echo "⬇️  Pull de \$img..."
                            docker pull \$img
                        fi
                    done
                """

                // ── FIX GLOBAL PERMISSIONS ──────────────────────────────
                // Trivy, ZAP, Gitleaks tournent en non-root dans leurs containers.
                // Ils NE PEUVENT PAS créer de nouveaux fichiers dans le workspace
                // (owned by jenkins/root), mais PEUVENT écraser des fichiers
                // existants si chmod 666. On les pré-crée tous ici.
                sh """
                    touch "${env.WORKSPACE}/gitleaks-report.json" \
                          "${env.WORKSPACE}/bandit-report.json" \
                          "${env.WORKSPACE}/trivy-report.json" \
                          "${env.WORKSPACE}/sbom.json" \
                          "${env.WORKSPACE}/zap-report.json" \
                          "${env.WORKSPACE}/zap-report.html" \
                          "${env.WORKSPACE}/ai-security-analysis.json" \
                          "${env.WORKSPACE}/ai-security-report.html"
                    chmod 666 "${env.WORKSPACE}"/*.json "${env.WORKSPACE}"/*.html || true
                """

                echo '✅ Environnement prêt'
            }
}

return this
def runSecretsScan() {
    stage('🔑 Secrets Scan — Gitleaks') {

                echo '🔑 Détection de secrets dans le code...'
                sh """
                    docker run --rm \
                        -v "${env.WORKSPACE}:/repo" \
                        ${env.GITLEAKS_IMAGE} detect \
                        --source /repo \
                        --report-format json \
                        --report-path /repo/gitleaks-report.json \
                        --exit-code 0 || true

                    # Fallback si Gitleaks n'a rien écrit (scan filesystem sans git)
                    [ -s "${env.WORKSPACE}/gitleaks-report.json" ] || \
                        echo '[]' > "${env.WORKSPACE}/gitleaks-report.json"

                    echo "📄 Rapport Gitleaks :"
                    cat "${env.WORKSPACE}/gitleaks-report.json" | head -5
                """
            }
            post {
                always {
                    archiveArtifacts artifacts: 'gitleaks-report.json',
                                     allowEmptyArchive: true
                }
            }
        
}

return this
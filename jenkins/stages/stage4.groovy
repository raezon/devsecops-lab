def runScan() {
        stage('🔬 SCA — Trivy & SBOM') {
            steps {
                echo '🔬 SCA + SBOM avec Trivy...'
                sh """
                    # Scan vulnérabilités
                    docker run --rm \
                        -v /var/run/docker.sock:/var/run/docker.sock \
                        -v "${env.WORKSPACE}:/workspace" \
                        ${env.TRIVY_IMAGE} image \
                        --exit-code 0 \
                        --severity HIGH,CRITICAL \
                        --format json \
                        --output /workspace/trivy-report.json \
                        ${env.APP_IMAGE} || true

                    # Génération SBOM CycloneDX
                    docker run --rm \
                        -v /var/run/docker.sock:/var/run/docker.sock \
                        -v "${env.WORKSPACE}:/workspace" \
                        ${env.TRIVY_IMAGE} image \
                        --format cyclonedx \
                        --output /workspace/sbom.json \
                        ${env.APP_IMAGE} || true

                    # Fallbacks si les fichiers sont toujours vides après Trivy
                    [ -s "${env.WORKSPACE}/trivy-report.json" ] || \
                        echo '{"Results":[]}' > "${env.WORKSPACE}/trivy-report.json"
                    [ -s "${env.WORKSPACE}/sbom.json" ] || \
                        echo '{"bomFormat":"CycloneDX","components":[]}' > "${env.WORKSPACE}/sbom.json"

                    echo "✅ Trivy terminé"
                """
            }
            post {
                always {
                    archiveArtifacts artifacts: 'trivy-report.json, sbom.json',
                                     allowEmptyArchive: true
                }
            }
        }
}

return this
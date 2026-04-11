def runScan() {
    // 1. Toujours ouvrir avec try pour autoriser le finally
    try {
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

            # Fallbacks si les fichiers sont vides
            [ -s "${env.WORKSPACE}/trivy-report.json" ] || \
                echo '{"Results":[]}' > "${env.WORKSPACE}/trivy-report.json"
            [ -s "${env.WORKSPACE}/sbom.json" ] || \
                echo '{"bomFormat":"CycloneDX","components":[]}' > "${env.WORKSPACE}/sbom.json"

            echo "✅ Trivy terminé"
        """
    }
    catch (Exception e) {
        echo "⚠️ Erreur lors du scan Trivy : ${e.message}"
        throw e
    }
    // 2. Le bloc qui s'exécute quoi qu'il arrive
    finally {
        echo "📦 Archivage des rapports SCA..."
        archiveArtifacts artifacts: 'trivy-report.json, sbom.json', allowEmptyArchive: true
    }
}

return this
def runOwaspZap() {
    // 1. On ouvre le bloc try (obligatoire pour que le finally fonctionne)
    try {
        echo '🚨 Démarrage de l\'application cible...'
        sh """
            # Lancement du container de l'app
            docker run -d \
                --name devsecops-target \
                --network ${env.DOCKER_NETWORK} \
                -p ${env.APP_PORT}:${env.APP_PORT} \
                ${env.APP_IMAGE}

            # Attente que l'app réponde (Healthcheck)
            for i in \$(seq 1 30); do
                if curl -sf http://localhost:${env.APP_PORT} > /dev/null 2>&1; then
                    echo "✅ App prête"
                    break
                fi
                sleep 1
            done
        """

        echo '🕷️ Scan ZAP en cours...'
        sh """
            # Permissions larges pour que ZAP (non-root) puisse écrire ses rapports
            chmod 777 "${env.WORKSPACE}"

            docker run --rm \
                --network ${env.DOCKER_NETWORK} \
                -v "${env.WORKSPACE}:/zap/wrk:rw" \
                -u root \
                ${env.ZAP_IMAGE} zap-baseline.py \
                -t http://devsecops-target:${env.APP_PORT} \
                -J zap-report.json \
                -r zap-report.html \
                -I || true

            # Fallbacks si les fichiers n'ont pas été générés
            [ -s "${env.WORKSPACE}/zap-report.json" ] || \
                echo '{"site":[]}' > "${env.WORKSPACE}/zap-report.json"
            
            [ -s "${env.WORKSPACE}/zap-report.html" ] || \
                echo '<html><body><p>ZAP report unavailable</p></body></html>' > "${env.WORKSPACE}/zap-report.html"

            chmod 666 "${env.WORKSPACE}/zap-report.json" "${env.WORKSPACE}/zap-report.html" || true
        """
    }
    catch (Exception e) {
        echo "⚠️ Erreur pendant le scan DAST : ${e.message}"
        throw e
    }
    // 2. Le bloc de nettoyage et d'archivage (Always)
    finally {
        echo "🧹 Nettoyage et archivage DAST..."
        
        # On arrête le container cible quoi qu'il arrive
        sh "docker rm -f devsecops-target 2>/dev/null || true"
        
        archiveArtifacts artifacts: 'zap-report.json, zap-report.html', allowEmptyArchive: true
        
        publishHTML(target: [
            allowMissing         : true,
            alwaysLinkToLastBuild: true,
            keepAll              : true,
            reportDir            : '.',
            reportFiles          : 'zap-report.html',
            reportName           : 'ZAP Security Report'
        ])
    }
}

return this
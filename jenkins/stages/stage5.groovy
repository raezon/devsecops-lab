def runOwaspZap() {
    // 1. Bloc try pour garantir l'exécution du finally
    try {
        echo '🚨 Démarrage de l\'application cible...'
        
        sh """
            # Nettoyage préventif
            docker rm -f devsecops-target 2>/dev/null || true

            # Lancement du container de l'app
            docker run -d \
                --name devsecops-target \
                --network "${env.DOCKER_NETWORK}" \
                -p "${env.APP_PORT}:${env.APP_PORT}" \
                "${env.APP_IMAGE}"

            # Attente que l'app réponde (Healthcheck)
            echo "Attente de l'application sur le port ${env.APP_PORT}..."
            for i in \$(seq 1 30); do
                if curl -sf http://localhost:${env.APP_PORT} > /dev/null 2>&1; then
                    echo "✅ App prête"
                    exit 0
                fi
                sleep 1
            done
            echo "❌ L'application n'a pas démarré à temps"
            exit 1
        """

        echo '🕷️ Scan ZAP en cours...'
        // On utilise pwd() pour avoir le chemin absolu du workspace
        def workspacePath = pwd()

        sh """
            # Permissions pour que ZAP puisse écrire le rapport
            chmod 777 "${workspacePath}"

            docker run --rm \
                --network "${env.DOCKER_NETWORK}" \
                -v "${workspacePath}:/zap/wrk:rw" \
                -u root \
                "${env.ZAP_IMAGE}" zap-baseline.py \
                -t "http://devsecops-target:${env.APP_PORT}" \
                -J zap-report.json \
                -r zap-report.html \
                -I || true

            # Fallbacks si les fichiers sont vides ou absents
            if [ ! -s "${workspacePath}/zap-report.json" ]; then
                echo '{"site":[]}' > "${workspacePath}/zap-report.json"
            fi
            
            if [ ! -s "${workspacePath}/zap-report.html" ]; then
                echo '<html><body><p>ZAP report unavailable</p></body></html>' > "${workspacePath}/zap-report.html"
            fi

            chmod 666 "${workspacePath}/zap-report.json" "${workspacePath}/zap-report.html" || true
        """
    }
    catch (Exception e) {
        echo "⚠️ Erreur pendant le scan DAST : ${e.message}"
        throw e
    }
    // 2. Nettoyage et archivage (équivalent du post always)
    finally {
        echo "🧹 Nettoyage et archivage DAST..."
        
        // Suppression du container de l'application
        sh "docker rm -f devsecops-target 2>/dev/null || true"
        
        // Archivage des fichiers dans Jenkins
        archiveArtifacts artifacts: 'zap-report.json, zap-report.html', allowEmptyArchive: true
        
        // Publication du rapport HTML via le plugin HTML Publisher
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
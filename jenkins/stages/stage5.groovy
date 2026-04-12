def runOwaspZap() {
    // 1. Bloc try pour sécuriser l'exécution
    try {
        echo '🚨 Démarrage de l\'application cible...'
        
        sh """
            # Nettoyage préventif d'un éventuel container fantôme
            docker rm -f devsecops-target 2>/dev/null || true

            # Lancement du container de l'application
            # On le place dans le réseau dédié pour que ZAP puisse le voir
            docker run -d \
                --name devsecops-target \
                --network "${env.DOCKER_NETWORK}" \
                -p "${env.APP_PORT}:${env.APP_PORT}" \
                "${env.APP_IMAGE}"

            echo "⏳ Attente du démarrage de l'application (Healthcheck interne)..."
            
            # On teste la disponibilité depuis l'INTÉRIEUR du container 
            # pour éviter les problèmes de routage réseau de l'agent Jenkins.
            # On utilise Python car curl n'est pas toujours présent dans l'image.
            for i in \$(seq 1 20); do
                if docker exec devsecops-target python -c "import urllib.request; urllib.request.urlopen('http://localhost:${env.APP_PORT}')" > /dev/null 2>&1; then
                    echo "✅ Application détectée et prête !"
                    exit 0
                fi
                echo "En attente... (\$i/20)"
                sleep 2
            done

            echo "❌ Erreur : L'application n'a pas démarré après 40 secondes."
            echo "--- LOGS DU CONTAINER ---"
            docker logs devsecops-target
            exit 1
        """

        echo '🕷️ Scan ZAP (Baseline) en cours...'
        
        // Récupération du chemin absolu pour le montage de volume
        def workspacePath = pwd()

        sh """
            # On s'assure que ZAP peut écrire les rapports dans le workspace
            chmod 777 "${workspacePath}"

            # Exécution de ZAP
            # -t : URL cible (on utilise le NOM du container sur le network Docker)
            # -I : Ne pas échouer le build si des alertes sont trouvées (on veut juste le rapport)
            docker run --rm \
                --network "${env.DOCKER_NETWORK}" \
                -v "${workspacePath}:/zap/wrk:rw" \
                -u root \
                "${env.ZAP_IMAGE}" zap-baseline.py \
                -t "http://devsecops-target:${env.APP_PORT}" \
                -J zap-report.json \
                -r zap-report.html \
                -I || true

            # Sécurité : Si ZAP échoue à créer les fichiers, on crée des placeholders
            [ -s "${workspacePath}/zap-report.json" ] || echo '{"site":[]}' > "${workspacePath}/zap-report.json"
            [ -s "${workspacePath}/zap-report.html" ] || echo '<html><body>Rapport non généré</body></html>' > "${workspacePath}/zap-report.html"
            
            # Remise des permissions correctes
            chmod 644 "${workspacePath}/zap-report.json" "${workspacePath}/zap-report.html" || true
        """

    } catch (Exception e) {
        echo "⚠️ Échec du stage DAST : ${e.message}"
        throw e
    } finally {
        // 2. Bloc de nettoyage et d'archivage (s'exécute toujours)
        echo "🧹 Nettoyage du container et archivage des rapports..."
        
        sh "docker rm -f devsecops-target 2>/dev/null || true"
        
        // Archivage des fichiers pour la consultation dans Jenkins
        archiveArtifacts artifacts: 'zap-report.json, zap-report.html', allowEmptyArchive: true
        
        // Publication de l'onglet "ZAP Security Report" dans l'interface Jenkins
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
def runOwaspZap() {
    try {
        echo '🚨 Démarrage de l\'application cible...'
        sh """
            # Nettoyage
            docker rm -f devsecops-target 2>/dev/null || true

            # Lancement
            docker run -d \
                --name devsecops-target \
                --network "${env.DOCKER_NETWORK}" \
                -p "${env.APP_PORT}:${env.APP_PORT}" \
                "${env.APP_IMAGE}"

            # RÉCUPÉRATION DE L'IP DU CONTAINER
            TARGET_IP=\$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' devsecops-target)
            echo "✅ Container IP: \$TARGET_IP"

            # Attente sur l'IP du container au lieu de localhost
            echo "Attente de l'application sur http://\$TARGET_IP:${env.APP_PORT}..."
            for i in \$(seq 1 30); do
                if curl -sf "http://\$TARGET_IP:${env.APP_PORT}" > /dev/null 2>&1; then
                    echo "✅ App prête sur le réseau Docker"
                    exit 0
                fi
                sleep 1
            done
            
            # Si échec, on affiche les logs du container pour comprendre pourquoi il a crashé
            docker logs devsecops-target
            echo "❌ L'application n'a pas répondu"
            exit 1
        """

        echo '🕷️ Scan ZAP en cours...'
        def workspacePath = pwd()
        sh """
            chmod 777 "${workspacePath}"

            # Le scan ZAP doit attaquer le NOM du container car ils sont sur le même network
            docker run --rm \
                --network "${env.DOCKER_NETWORK}" \
                -v "${workspacePath}:/zap/wrk:rw" \
                -u root \
                "${env.ZAP_IMAGE}" zap-baseline.py \
                -t "http://devsecops-target:${env.APP_PORT}" \
                -J zap-report.json \
                -r zap-report.html \
                -I || true
        """
    }
    catch (Exception e) {
        echo "⚠️ Erreur : ${e.message}"
        throw e
    }
    finally {
        sh "docker rm -f devsecops-target 2>/dev/null || true"
        archiveArtifacts artifacts: 'zap-report.json, zap-report.html', allowEmptyArchive: true
        publishHTML(target: [
            allowMissing: true, reportDir: '.', reportFiles: 'zap-report.html', reportName: 'ZAP Security Report'
        ])
    }
}
return this
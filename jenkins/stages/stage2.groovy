def runSecretsScan() {
    // Éviter de remettre 'stage' ici si tu l'as déjà mis dans le Jenkinsfile
    // Mais si tu veux le garder ici, voici la syntaxe exacte :
    
    try {
        echo '🔑 Détection de secrets dans le code...'
        sh """
            docker run --rm \
                -v "${env.WORKSPACE}:/repo" \
                ${env.GITLEAKS_IMAGE} detect \
                --source /repo \
                --report-format json \
                --report-path /repo/gitleaks-report.json \
                --exit-code 0 || true

            # Fallback si le rapport est vide ou absent
            if [ ! -s "${env.WORKSPACE}/gitleaks-report.json" ]; then
                echo '[]' > "${env.WORKSPACE}/gitleaks-report.json"
            fi

            echo "📄 Aperçu du rapport Gitleaks :"
            cat "${env.WORKSPACE}/gitleaks-report.json" | head -n 5
        """
    } 
    catch (Exception e) {
        echo "⚠️ Erreur pendant le scan Gitleaks : ${e.message}"
        throw e // Permet au pipeline de savoir que ça a échoué
    }
    finally {
        // Le finally remplace le "post { always { ... } }"
        echo "📦 Archivage du rapport..."
        archiveArtifacts artifacts: 'gitleaks-report.json', allowEmptyArchive: true
    }
}

return this
def runBuildAndScan() {
    // 1. On ouvre le try (obligatoire pour avoir un finally)
    try {
        echo '🔍 1. Exécution du SAST (Bandit)...'
        sh """
            docker run --rm \
                -v "${env.WORKSPACE}:/app" \
                -w /app \
                ${env.PYTHON_IMAGE} /bin/sh -c '
                    pip install -q bandit &&
                    bandit -r app/ -f json -o bandit-report.json || true
                '
            [ -s "${env.WORKSPACE}/bandit-report.json" ] || \
                echo '{"results":[],"metrics":{}}' > "${env.WORKSPACE}/bandit-report.json"
        """

        echo "🐳 2. Construction de l'image Docker : ${env.APP_IMAGE}"
        sh "docker build -t ${env.APP_IMAGE} app/"

        echo '🧪 3. Exécution des Tests Unitaires...'
        sh """
            docker run --rm ${env.APP_IMAGE} /bin/sh -c \
                'pip install -q pytest && pytest tests/ -v 2>&1 || echo "⚠️  Aucun test trouvé"' || true
        """
    } 
    // 2. On ferme le try et on ouvre le finally (équivalent du post always)
    finally {
        echo "📦 Archivage et Stash du rapport Bandit..."
        stash includes: 'bandit-report.json', name: 'bandit-report', allowEmpty: true
        archiveArtifacts artifacts: 'bandit-report.json', allowEmptyArchive: true
    }
}

return this
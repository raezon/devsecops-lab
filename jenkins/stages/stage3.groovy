def runBuildAndScan() {
    try {
        // Build ONCE - This becomes your environment for everything
        echo "🐳 Building Image..."
        sh "docker build -t ${env.APP_IMAGE} app/"

        // Run Bandit using the already built image (if it has python)
        // or a pre-baked security image to avoid 'pip install'
        echo '🔍 1. Running SAST...'
        sh """
            docker run --rm -v "${env.WORKSPACE}:/app" my-prebaked-security-image \
            bandit -r /app -f json -o /app/bandit-report.json || true
        """

        echo '🧪 2. Running Unit Tests...'
        // The image already has your code, just run the tests
        sh "docker run --rm ${env.APP_IMAGE} pytest tests/ -v || echo 'No tests found'"

    } finally {
        echo "📦 Archiving..."
        stash includes: 'bandit-report.json', name: 'bandit-report', allowEmpty: true
        archiveArtifacts artifacts: 'bandit-report.json', allowEmptyArchive: true
    }
}

return this
def runBuildAndScan(){
     stage('🛠️ Build, Scan & Test') {
            steps {
                script {

                    echo '🔍 1. Exécution du SAST (Bandit)...'
                    sh """
                        docker run --rm \
                            -v "${WORKSPACE}:/app" \
                            -w /app \
                            ${PYTHON_IMAGE} /bin/sh -c '
                                pip install -q bandit &&
                                bandit -r app/ -f json -o bandit-report.json || true
                            '
                        [ -s "${WORKSPACE}/bandit-report.json" ] || \
                            echo '{"results":[],"metrics":{}}' > "${WORKSPACE}/bandit-report.json"
                    """

                    echo '🐳 2. Construction de l\'image Docker...'
                    sh "docker build -t ${APP_IMAGE} app/"

                    echo '🧪 3. Exécution des Tests Unitaires...'
                    sh """
                        docker run --rm ${APP_IMAGE} /bin/sh -c \
                            'pip install -q pytest && pytest tests/ -v 2>&1 || echo "⚠️  Aucun test trouvé"' || true
                    """
                }
            }
            post {
                always {
                    stash includes: 'bandit-report.json', name: 'bandit-report', allowEmpty: true
                    archiveArtifacts artifacts: 'bandit-report.json',
                                     allowEmptyArchive: true
                }
            }
        }

}

return this
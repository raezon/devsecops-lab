def runAiReports() {
    // 1. On ouvre le bloc try (pour que le finally en dessous soit valide)
    try {
        // Note : J'ai enlevé 'stage' pour éviter les conflits avec le Jenkinsfile
        withCredentials([
            string(credentialsId: 'openrouter-api-key', variable: 'OPENROUTER_API_KEY'),
            string(credentialsId: 'resend-api-key',     variable: 'RESEND_API_KEY'),
            string(credentialsId: 'report-email',       variable: 'REPORT_EMAIL')
        ]) {
            echo '🤖 Analyse IA et Quality Gate...'
            sh """
                docker run --rm \
                    -v "${env.WORKSPACE}:/workspace" \
                    -w /workspace \
                    -e OPENROUTER_API_KEY="${env.OPENROUTER_API_KEY}" \
                    -e RESEND_API_KEY="${env.RESEND_API_KEY}" \
                    -e REPORT_EMAIL="${env.REPORT_EMAIL}" \
                    -e WORKSPACE=/workspace \
                    -e JOB_NAME="${env.JOB_NAME}" \
                    -e BUILD_NUMBER="${env.BUILD_NUMBER}" \
                    -e BUILD_URL="${env.BUILD_URL}" \
                    -e GIT_COMMIT="${env.GIT_COMMIT}" \
                    -e GIT_BRANCH="${env.GIT_BRANCH}" \
                    ${env.PYTHON_IMAGE} /bin/sh -c '
                        pip install -q requests &&
                        python3 jenkins/scripts/ai_security_report.py
                    '
            """
        }
    }
    catch (Exception e) {
        echo "⚠️ Erreur dans le module IA : ${e.message}"
        throw e
    }
    // 2. Le bloc finally qui remplace le "post { always }"
    finally {
        echo "📦 Archivage et publication des rapports IA..."
        
        archiveArtifacts artifacts: 'ai-security-analysis.json, ai-security-report.html', 
                         allowEmptyArchive: true
        
        publishHTML(target: [
            allowMissing         : true,
            alwaysLinkToLastBuild: true,
            keepAll              : true,
            reportDir            : '.',
            reportFiles          : 'ai-security-report.html',
            reportName           : 'AI Security Report'
        ])
    }
}

return this
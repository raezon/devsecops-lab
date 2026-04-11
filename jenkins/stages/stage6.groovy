def runAiReports(){
    stage('🤖 AI Report & Quality Gate') {
            steps {
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
                                ls -l
                                python3 ../scripts/ai_security_report.py
                            '
                    """
                }
            }
            post {
                always {
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
        }
}

return this
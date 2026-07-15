pipeline {
    agent any

    environment {
        REGISTRY       = "${env.DOCKER_REGISTRY ?: 'ghcr.io/your-org'}"
        IMAGE_BACKEND  = "${REGISTRY}/log-analyzer-backend"
        IMAGE_FRONTEND = "${REGISTRY}/log-analyzer-frontend"
        TAG            = "${env.GIT_COMMIT?.take(7) ?: 'latest'}"
        SONAR_URL      = credentials('SONAR_HOST_URL')
        SONAR_TOKEN    = credentials('SONAR_TOKEN')
        SLACK_CHANNEL  = '#devops-alerts'
    }

    options {
        timeout(time: 45, unit: 'MINUTES')
        disableConcurrentBuilds()
        buildDiscarder(logRotator(numToKeepStr: '10'))
    }

    stages {
        // ── 1. Checkout ──────────────────────────────────────────────────────
        stage('Checkout') {
            steps {
                checkout scm
                sh 'git log --oneline -5'
            }
        }

        // ── 2. Lint & Unit Tests (parallel) ──────────────────────────────────
        stage('Lint & Tests') {
            parallel {
                stage('Backend Tests') {
                    agent {
                        docker {
                            image 'python:3.10-slim'
                            args '-v /tmp/pip-cache:/root/.cache/pip'
                        }
                    }
                    steps {
                        dir('backend') {
                            sh '''
                                pip install -r requirements.txt coverage pytest pytest-asyncio --quiet
                                coverage run -m pytest tests/ -v --tb=short
                                coverage xml -o coverage.xml
                                coverage report --show-missing
                            '''
                        }
                    }
                    post {
                        always {
                            junit allowEmptyResults: true, testResults: 'backend/junit.xml'
                            publishCoverage adapters: [coberturaAdapter('backend/coverage.xml')]
                        }
                    }
                }

                stage('Frontend Tests') {
                    agent {
                        docker {
                            image 'node:18-alpine'
                            args '-v /tmp/npm-cache:/root/.npm'
                        }
                    }
                    steps {
                        dir('frontend') {
                            sh '''
                                npm ci --prefer-offline
                                npm run test:coverage
                                npm audit --audit-level=high || true
                            '''
                        }
                    }
                    post {
                        always {
                            publishHTML([
                                allowMissing: true,
                                alwaysLinkToLastBuild: true,
                                keepAll: true,
                                reportDir: 'frontend/coverage',
                                reportFiles: 'index.html',
                                reportName: 'Frontend Coverage'
                            ])
                        }
                    }
                }

                stage('Helm Lint') {
                    steps {
                        sh 'helm lint helm/log-analyzer/'
                        sh 'helm template log-analyzer helm/log-analyzer/ > /dev/null'
                    }
                }
            }
        }

        // ── 3. SonarQube ──────────────────────────────────────────────────────
        stage('SonarQube') {
            when { branch 'main' }
            steps {
                withSonarQubeEnv('SonarQube') {
                    sh "sonar-scanner -Dsonar.host.url=${SONAR_URL} -Dsonar.login=${SONAR_TOKEN}"
                }
                timeout(time: 5, unit: 'MINUTES') {
                    waitForQualityGate abortPipeline: true
                }
            }
        }

        // ── 4. Docker Build ───────────────────────────────────────────────────
        stage('Docker Build') {
            parallel {
                stage('Build Backend') {
                    steps {
                        sh "docker build -t ${IMAGE_BACKEND}:${TAG} -t ${IMAGE_BACKEND}:latest ./backend"
                    }
                }
                stage('Build Frontend') {
                    steps {
                        sh "docker build -t ${IMAGE_FRONTEND}:${TAG} -t ${IMAGE_FRONTEND}:latest ./frontend"
                    }
                }
            }
        }

        // ── 5. Trivy Security Scan ────────────────────────────────────────────
        stage('Trivy Scan') {
            parallel {
                stage('Scan Backend') {
                    steps {
                        sh """
                            trivy image \
                              --exit-code 1 \
                              --severity CRITICAL,HIGH \
                              --ignore-unfixed \
                              --format table \
                              ${IMAGE_BACKEND}:${TAG}
                        """
                    }
                }
                stage('Scan Frontend') {
                    steps {
                        sh """
                            trivy image \
                              --exit-code 1 \
                              --severity CRITICAL,HIGH \
                              --ignore-unfixed \
                              --format table \
                              ${IMAGE_FRONTEND}:${TAG}
                        """
                    }
                }
            }
        }

        // ── 6. Push to Registry ───────────────────────────────────────────────
        stage('Push Images') {
            when { branch 'main' }
            steps {
                withCredentials([usernamePassword(
                    credentialsId: 'registry-credentials',
                    usernameVariable: 'REGISTRY_USER',
                    passwordVariable: 'REGISTRY_PASS'
                )]) {
                    sh "echo $REGISTRY_PASS | docker login ${REGISTRY} -u $REGISTRY_USER --password-stdin"
                    sh "docker push ${IMAGE_BACKEND}:${TAG} && docker push ${IMAGE_BACKEND}:latest"
                    sh "docker push ${IMAGE_FRONTEND}:${TAG} && docker push ${IMAGE_FRONTEND}:latest"
                }
            }
        }

        // ── 7. Deploy Staging ─────────────────────────────────────────────────
        stage('Deploy Staging') {
            when { branch 'main' }
            steps {
                withCredentials([file(credentialsId: 'kubeconfig-staging', variable: 'KUBECONFIG')]) {
                    sh """
                        helm upgrade --install log-analyzer-staging helm/log-analyzer/ \
                          --namespace log-analyzer-staging \
                          --create-namespace \
                          --set image.backend.tag=${TAG} \
                          --set image.frontend.tag=${TAG} \
                          --set ingress.host=staging.log-analyzer.internal \
                          --wait \
                          --timeout 5m
                    """
                }
            }
        }

        // ── 8. Smoke Tests ────────────────────────────────────────────────────
        stage('Smoke Tests') {
            when { branch 'main' }
            steps {
                sh '''
                    STAGING_URL="http://staging.log-analyzer.internal"
                    STATUS=$(curl -s -o /dev/null -w "%{http_code}" $STAGING_URL/health)
                    if [ "$STATUS" != "200" ]; then
                        echo "Smoke test FAILED — health returned HTTP $STATUS"
                        exit 1
                    fi
                    echo "Smoke test PASSED — health: $STATUS"
                '''
            }
        }

        // ── 9. Deploy Production ──────────────────────────────────────────────
        stage('Deploy Production') {
            when {
                allOf {
                    branch 'main'
                    expression { currentBuild.resultIsBetterOrEqualTo('SUCCESS') }
                }
            }
            input {
                message 'Deploy to Production?'
                ok 'Deploy'
                submitter 'admin,lead-dev'
            }
            steps {
                withCredentials([file(credentialsId: 'kubeconfig-prod', variable: 'KUBECONFIG')]) {
                    sh """
                        helm upgrade --install log-analyzer helm/log-analyzer/ \
                          --namespace log-analyzer \
                          --create-namespace \
                          -f helm/log-analyzer/values-prod.yaml \
                          --set image.backend.tag=${TAG} \
                          --set image.frontend.tag=${TAG} \
                          --wait \
                          --timeout 10m
                    """
                }
            }
        }
    }

    post {
        failure {
            slackSend(
                channel: env.SLACK_CHANNEL,
                color: 'danger',
                message: """
:x: *Build FAILED* — Log Analyzer AI
Branch: `${env.BRANCH_NAME}` | Commit: `${env.GIT_COMMIT?.take(7)}`
Stage: `${env.STAGE_NAME ?: 'unknown'}`
<${env.BUILD_URL}|View Build #${env.BUILD_NUMBER}>
                """.trim()
            )
        }
        success {
            slackSend(
                channel: env.SLACK_CHANNEL,
                color: 'good',
                message: """
:white_check_mark: *Build SUCCESS* — Log Analyzer AI
Branch: `${env.BRANCH_NAME}` | Tag: `${TAG}`
<${env.BUILD_URL}|View Build #${env.BUILD_NUMBER}>
                """.trim()
            )
        }
        always {
            cleanWs()
        }
    }
}

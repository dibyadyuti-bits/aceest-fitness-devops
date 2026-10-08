// Jenkins BUILD pipeline for ACEest Fitness & Gym.
// Job type: Pipeline, "Pipeline script from SCM" pointing at the GitHub repo.
// Agent needs: git, python3 + python3-venv, docker (for the Docker stage).

pipeline {
    agent any

    options {
        disableConcurrentBuilds()
        buildDiscarder(logRotator(numToKeepStr: '10'))
    }

    triggers {
        // Poll GitHub every ~5 minutes; swap for a GitHub webhook if Jenkins is reachable
        pollSCM('H/5 * * * *')
    }

    environment {
        IMAGE = 'aceest-fitness'
        TAG   = "${env.BUILD_NUMBER}"
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Setup Environment') {
            steps {
                sh '''
                    rm -rf .venv
                    python3 -m venv .venv
                    . .venv/bin/activate
                    pip install -r requirements-dev.txt
                '''
            }
        }

        stage('Lint') {
            steps {
                sh '. .venv/bin/activate && python -m compileall -q aceest app.py && flake8 .'
            }
        }

        stage('Unit Tests') {
            steps {
                sh '''
                    . .venv/bin/activate
                    mkdir -p reports
                    pytest --junitxml=reports/junit.xml \
                           --cov=aceest --cov-report=xml:reports/coverage.xml
                '''
            }
            post {
                always {
                    junit 'reports/junit.xml'
                }
            }
        }

        stage('Docker Build') {
            steps {
                sh '''
                    docker build --target test -t $IMAGE:test .
                    docker run --rm $IMAGE:test
                    docker build --target runtime -t $IMAGE:$TAG -t $IMAGE:latest .
                '''
            }
        }
    }

    post {
        success {
            echo "BUILD #${env.BUILD_NUMBER} passed: image ${env.IMAGE}:${env.TAG}"
        }
        failure {
            echo "BUILD #${env.BUILD_NUMBER} failed - check the stage logs above."
        }
        always {
            deleteDir()
        }
    }
}

// ACEest Fitness & Gym - Jenkins CI/CD pipeline
//
//   Checkout -> clean venv -> lint -> unit tests -> SonarCloud analysis + quality gate
//   -> Docker build -> Pytest inside the container -> push to Docker Hub -> build artifacts
//   -> deploy to Kubernetes (chosen strategy) -> smoke test -> automatic rollback on failure
//
// Jenkins setup (README, "Jenkins setup"):
//   Plugins:      Pipeline, Git, JUnit, Credentials Binding, Timestamper
//   Credentials:  sonarcloud-token  (Secret text: SonarCloud token)
//                 dockerhub-creds   (Username + password: Docker Hub user + access token)
//                 kubeconfig        (Secret file: kubeconfig of the Minikube cluster)
//   Agent:        git, python3 + venv, docker; kubectl for the deploy stages

pipeline {
    agent any

    triggers {
        // Poll GitHub every ~5 minutes; with a reachable Jenkins, a GitHub webhook
        // (http://<jenkins>/github-webhook/ + githubPush()) builds instantly instead.
        pollSCM('H/5 * * * *')
    }

    parameters {
        choice(name: 'DEPLOY_STRATEGY',
               choices: ['none', 'rolling', 'blue-green', 'canary', 'ab-testing', 'shadow'],
               description: 'Kubernetes release strategy (polled builds use the first choice: none)')
        string(name: 'BASELINE_TAG', defaultValue: '',
               description: 'canary / ab-testing / shadow, first deploy only: image tag that keeps serving users, e.g. 1.0.0')
        string(name: 'CANARY_WEIGHT', defaultValue: '20', description: 'Percent of traffic for the canary')
        booleanParam(name: 'RUN_SONAR', defaultValue: true, description: 'SonarCloud analysis and quality gate')
        booleanParam(name: 'PUSH_IMAGE', defaultValue: true, description: 'Push the image to Docker Hub')
        booleanParam(name: 'SIMULATE_BAD_RELEASE', defaultValue: false,
                     description: 'Demo: fail the post-deploy smoke test to show the automatic rollback')
    }

    options {
        timestamps()
        disableConcurrentBuilds()
        buildDiscarder(logRotator(numToKeepStr: '15'))
    }

    environment {
        IMAGE_NAME = 'aceest-fitness'
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
                script {
                    // Parameters are null on the first run of a new job.
                    env.STRATEGY = params.DEPLOY_STRATEGY ?: 'none'
                    env.APP_VERSION = readFile('VERSION').trim()
                    env.BUILD_TAG_NAME = "${env.APP_VERSION}-b${env.BUILD_NUMBER}"
                    env.GIT_RELEASE_TAG = sh(script: 'git describe --tags --exact-match 2>/dev/null || true',
                                             returnStdout: true).trim()
                    env.DOCKER_OK = sh(script: 'docker info > /dev/null 2>&1', returnStatus: true) == 0 ? 'true' : 'false'
                    if (env.DOCKER_OK != 'true') {
                        echo 'Docker daemon not reachable by this agent: Docker stages will be skipped.'
                    }
                    currentBuild.displayName = "#${env.BUILD_NUMBER} v${env.APP_VERSION}"
                    currentBuild.description = "strategy: ${env.STRATEGY}"
                }
                sh 'rm -rf reports dist && mkdir -p reports dist'
            }
        }

        stage('Setup Environment') {
            steps {
                sh '''
                    rm -rf .venv
                    python3 -m venv .venv
                    . .venv/bin/activate
                    pip install --quiet --upgrade pip
                    pip install --quiet -r requirements-dev.txt
                '''
            }
        }

        stage('Lint') {
            steps {
                sh '''
                    . .venv/bin/activate
                    python -m compileall -q aceest app.py ACEest_Fitness.py tests
                    flake8 .
                    if command -v shellcheck > /dev/null; then
                        shellcheck k8s/release.sh
                    else
                        echo "shellcheck not installed on this agent - skipped (GitHub Actions runs it)"
                    fi
                '''
            }
        }

        stage('Unit Tests') {
            steps {
                sh '''
                    . .venv/bin/activate
                    pytest --junitxml=reports/junit.xml \
                           --cov --cov-report=term --cov-report=xml:reports/coverage.xml
                '''
            }
        }

        stage('SonarCloud Analysis & Quality Gate') {
            when { expression { params.RUN_SONAR != false } }
            steps {
                withCredentials([string(credentialsId: 'sonarcloud-token', variable: 'SONAR_TOKEN')]) {
                    // pysonar is SonarSource's scanner from PyPI: no Java or Docker needed on the
                    // agent. sonar.qualitygate.wait=true (sonar-project.properties) makes it fail
                    // the build when the quality gate fails.
                    sh '''
                        . .venv/bin/activate
                        pip install --quiet pysonar
                        pysonar --sonar-project-version "$APP_VERSION"
                    '''
                }
            }
            post {
                always {
                    // Keep the quality-gate result with the build as the SonarCloud report.
                    sh '''
                        curl -fsS -o reports/sonarcloud-quality-gate.json \
                          "https://sonarcloud.io/api/qualitygates/project_status?projectKey=dibyadyuti-bits_aceest-fitness-devops" || true
                        curl -fsS -o reports/sonarcloud-measures.json \
                          "https://sonarcloud.io/api/measures/component?component=dibyadyuti-bits_aceest-fitness-devops&metricKeys=alert_status,bugs,vulnerabilities,code_smells,coverage,duplicated_lines_density,ncloc" || true
                    '''
                }
            }
        }

        stage('Docker Build & Container Tests') {
            when { environment name: 'DOCKER_OK', value: 'true' }
            steps {
                sh '''
                    # Pytest inside the test image
                    docker build --target test -t "$IMAGE_NAME:test" .
                    docker run --rm "$IMAGE_NAME:test"

                    # Runtime image with the release version baked in
                    docker build --target runtime --build-arg APP_VERSION="$APP_VERSION" \
                        -t "$IMAGE_NAME:$BUILD_TAG_NAME" .

                    # The runtime container must start and report the right version
                    name="aceest-ci-$BUILD_NUMBER"
                    docker rm -f "$name" > /dev/null 2>&1 || true
                    docker run -d --name "$name" "$IMAGE_NAME:$BUILD_TAG_NAME"
                    ok=""
                    for i in $(seq 1 15); do
                        if docker exec "$name" python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:5000/version').read().decode())" \
                                > reports/container-version.json 2> /dev/null; then
                            ok=1; break
                        fi
                        sleep 2
                    done
                    docker rm -f "$name" > /dev/null
                    [ -n "$ok" ] || { echo "runtime container did not start"; exit 1; }
                    cat reports/container-version.json
                    grep -q "\\"version\\":\\"$APP_VERSION\\"" reports/container-version.json
                '''
            }
        }

        stage('Push to Docker Hub') {
            when {
                allOf {
                    environment name: 'DOCKER_OK', value: 'true'
                    expression { params.PUSH_IMAGE != false }
                }
            }
            steps {
                withCredentials([usernamePassword(credentialsId: 'dockerhub-creds',
                                                  usernameVariable: 'DOCKERHUB_USER',
                                                  passwordVariable: 'DOCKERHUB_TOKEN')]) {
                    sh '''
                        echo "$DOCKERHUB_TOKEN" | docker login -u "$DOCKERHUB_USER" --password-stdin
                        repo="$DOCKERHUB_USER/$IMAGE_NAME"
                        # Every build: <version>-b<build>, <version> and latest; plus the git tag if any
                        for tag in "$BUILD_TAG_NAME" "$APP_VERSION" latest $GIT_RELEASE_TAG; do
                            docker tag "$IMAGE_NAME:$BUILD_TAG_NAME" "$repo:$tag"
                            docker push "$repo:$tag"
                        done
                        echo "$repo" > reports/image-repo.txt
                    '''
                }
            }
            post {
                always { sh 'docker logout > /dev/null 2>&1 || true' }
            }
        }

        stage('Build Artifacts') {
            steps {
                sh '''
                    git archive --format=tar.gz --prefix="aceest-fitness-$APP_VERSION/" \
                        -o "dist/aceest-fitness-$BUILD_TAG_NAME-src.tar.gz" HEAD
                    {
                        echo "version=$APP_VERSION"
                        echo "build=$BUILD_NUMBER"
                        echo "commit=$(git rev-parse HEAD)"
                        echo "git_tag=${GIT_RELEASE_TAG:-none}"
                        echo "image=$(cat reports/image-repo.txt 2> /dev/null || echo "$IMAGE_NAME"):$BUILD_TAG_NAME"
                    } > "dist/aceest-fitness-$BUILD_TAG_NAME-build-info.txt"
                    cat dist/*-build-info.txt
                '''
            }
        }

        stage('Deploy to Kubernetes') {
            when { expression { env.STRATEGY != 'none' } }
            steps {
                withCredentials([file(credentialsId: 'kubeconfig', variable: 'KUBECONFIG'),
                                 usernamePassword(credentialsId: 'dockerhub-creds',
                                                  usernameVariable: 'DOCKERHUB_USER',
                                                  passwordVariable: 'DOCKERHUB_TOKEN')]) {
                    script {
                        try {
                            sh '''
                                repo="$DOCKERHUB_USER/$IMAGE_NAME"
                                baseline=""
                                if [ -n "$BASELINE_TAG" ]; then baseline="$repo:$BASELINE_TAG"; fi
                                EXPECTED_VERSION="$APP_VERSION" CANARY_WEIGHT="$CANARY_WEIGHT" \
                                    bash k8s/release.sh deploy "$STRATEGY" "$repo:$BUILD_TAG_NAME" $baseline
                            '''
                        } catch (err) {
                            // Blue-green only switches traffic after the new colour passed its
                            // smoke test, so a failure here never reached users.
                            if (env.STRATEGY != 'blue-green') {
                                sh 'bash k8s/release.sh rollback "$STRATEGY"'
                            }
                            error("Deployment failed (${err}): ${env.STRATEGY} rolled back to the last stable version")
                        }
                    }
                }
            }
        }

        stage('Smoke Test & Rollback') {
            when { expression { env.STRATEGY != 'none' } }
            steps {
                withCredentials([file(credentialsId: 'kubeconfig', variable: 'KUBECONFIG')]) {
                    script {
                        def expected = params.SIMULATE_BAD_RELEASE ? '0.0.0-bad-release' : env.APP_VERSION
                        try {
                            withEnv(["EXPECTED=${expected}"]) {
                                // Output to a file first so the script's exit code is not lost in a pipe.
                                sh '''
                                    rc=0
                                    bash k8s/release.sh smoke "$STRATEGY" "$EXPECTED" > reports/smoke-test.txt 2>&1 || rc=$?
                                    cat reports/smoke-test.txt
                                    exit $rc
                                '''
                            }
                        } catch (err) {
                            sh '''
                                rc=0
                                bash k8s/release.sh rollback "$STRATEGY" > reports/rollback.txt 2>&1 || rc=$?
                                cat reports/rollback.txt
                                exit $rc
                            '''
                            error("Smoke test failed: ${env.STRATEGY} rolled back to the last stable version")
                        } finally {
                            sh 'bash k8s/release.sh status "$STRATEGY" > reports/k8s-status.txt 2>&1 || true'
                        }
                    }
                }
            }
        }
    }

    post {
        always {
            junit allowEmptyResults: true, testResults: 'reports/junit.xml'
            archiveArtifacts artifacts: 'reports/**, dist/**', allowEmptyArchive: true, fingerprint: true
        }
        success {
            echo "Build ${env.BUILD_NUMBER} (v${env.APP_VERSION}) passed; strategy: ${env.STRATEGY}."
        }
        failure {
            echo "Build ${env.BUILD_NUMBER} failed - check the stage logs above."
        }
        cleanup {
            deleteDir()
        }
    }
}

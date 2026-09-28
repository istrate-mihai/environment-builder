// Environment Builder pipeline:
// tests -> build image -> push to Docker Hub -> validate config -> provision EC2 -> install -> verify
//
// Jenkins credentials used:
//   dockerhub-creds  (Username/password) - Docker Hub user + access token
//   aws-creds        (Username/password) - AWS access key ID + secret access key
//   env-builder-ssh  (SSH private key)   - key for user "ubuntu" on the EC2 server
pipeline {
    agent any

    parameters {
        string(name: 'CONFIG_NAME', defaultValue: 'environment.yml',
               description: 'Config file inside config/ (e.g. environment.yml or examples/full.yml)')
        booleanParam(name: 'PROVISION', defaultValue: true,
                     description: 'Create/update the EC2 server with Terraform')
        string(name: 'TARGET_HOST', defaultValue: '',
               description: 'IP of an existing server (only used when PROVISION is off)')
        booleanParam(name: 'DESTROY_AFTER', defaultValue: false,
                     description: 'Run terraform destroy at the end (saves AWS costs)')
    }

    environment {
        IMAGE              = 'your-dockerhub-username/env-builder-validator'
        TAG                = "${env.BUILD_NUMBER}"
        AWS_DEFAULT_REGION = 'eu-central-1'
        ANSIBLE_FORCE_COLOR = 'true'
    }

    options {
        timestamps()
        disableConcurrentBuilds()
        timeout(time: 45, unit: 'MINUTES')
        buildDiscarder(logRotator(numToKeepStr: '15'))
    }

    stages {
        stage('Unit tests') {
            steps {
                sh '''
                    docker run --rm -v "$WORKSPACE/validator:/src" -w /src python:3.12-slim \
                        sh -c "pip install -q -r requirements.txt -r requirements-dev.txt && python -m pytest -q -p no:cacheprovider"
                '''
            }
        }

        stage('Build image') {
            steps {
                sh 'docker build -t "$IMAGE:$TAG" -t "$IMAGE:latest" .'
            }
        }

        stage('Push to Docker Hub') {
            steps {
                withCredentials([usernamePassword(credentialsId: 'dockerhub-creds',
                                                  usernameVariable: 'DH_USER', passwordVariable: 'DH_TOKEN')]) {
                    sh '''
                        echo "$DH_TOKEN" | docker login -u "$DH_USER" --password-stdin
                        docker push "$IMAGE:$TAG"
                        docker push "$IMAGE:latest"
                    '''
                }
            }
            post {
                always { sh 'docker logout || true' }
            }
        }

        stage('Validate config') {
            steps {
                // Non-zero exit here stops the pipeline: nothing gets installed.
                sh '''
                    rm -rf output/*.yml output/*.conf output/*.ini
                    mkdir -p output
                    docker run --rm --user "$(id -u):$(id -g)" \
                        -v "$WORKSPACE/config:/config:ro" \
                        -v "$WORKSPACE/output:/output" \
                        "$IMAGE:$TAG" --config "/config/$CONFIG_NAME" --out-dir /output
                '''
            }
        }

        stage('Provision server (Terraform)') {
            when { expression { params.PROVISION } }
            steps {
                withCredentials([
                    usernamePassword(credentialsId: 'aws-creds',
                                     usernameVariable: 'AWS_ACCESS_KEY_ID', passwordVariable: 'AWS_SECRET_ACCESS_KEY'),
                    sshUserPrivateKey(credentialsId: 'env-builder-ssh', keyFileVariable: 'SSH_KEY')
                ]) {
                    dir('terraform') {
                        sh '''
                            ssh-keygen -y -f "$SSH_KEY" > env-builder.pub
                            MY_IP="$(curl -fsS https://checkip.amazonaws.com)"
                            terraform init -input=false
                            terraform apply -auto-approve -input=false \
                                -var "public_key_path=env-builder.pub" \
                                -var "allowed_ssh_cidr=${MY_IP}/32"
                            terraform output -raw public_ip > ../output/target_host
                        '''
                    }
                }
            }
        }

        stage('Use existing server') {
            when { expression { !params.PROVISION } }
            steps {
                script {
                    if (!params.TARGET_HOST?.trim()) {
                        error('TARGET_HOST is required when PROVISION is off')
                    }
                }
                sh 'echo "$TARGET_HOST" > output/target_host'
            }
        }

        stage('Install (Ansible)') {
            steps {
                sh 'printf "[target]\\n%s ansible_user=ubuntu\\n" "$(cat output/target_host)" > output/inventory.ini'
                withCredentials([sshUserPrivateKey(credentialsId: 'env-builder-ssh', keyFileVariable: 'SSH_KEY')]) {
                    sh 'ansible-playbook --private-key "$SSH_KEY" ansible/site.yml'
                }
            }
        }

        stage('Verify') {
            steps {
                withCredentials([sshUserPrivateKey(credentialsId: 'env-builder-ssh', keyFileVariable: 'SSH_KEY')]) {
                    sh 'ansible-playbook --private-key "$SSH_KEY" ansible/verify.yml'
                }
            }
        }
    }

    post {
        always {
            archiveArtifacts artifacts: 'output/*', allowEmptyArchive: true
            script {
                if (params.PROVISION && params.DESTROY_AFTER) {
                    withCredentials([
                        usernamePassword(credentialsId: 'aws-creds',
                                         usernameVariable: 'AWS_ACCESS_KEY_ID', passwordVariable: 'AWS_SECRET_ACCESS_KEY'),
                        sshUserPrivateKey(credentialsId: 'env-builder-ssh', keyFileVariable: 'SSH_KEY')
                    ]) {
                        dir('terraform') {
                            sh '''
                                ssh-keygen -y -f "$SSH_KEY" > env-builder.pub
                                terraform destroy -auto-approve -input=false \
                                    -var "public_key_path=env-builder.pub" -var "allowed_ssh_cidr=0.0.0.0/32"
                            '''
                        }
                    }
                }
            }
        }
        success { echo 'Server configured and verified.' }
        failure { echo 'Pipeline failed - check the stage logs above.' }
    }
}

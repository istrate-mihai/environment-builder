# Environment Builder

Configurează automat un server Ubuntu în AWS pe baza unui fișier YAML în care declari ce tehnologii vrei instalate.

Flux: **validare (Python/Docker) → server EC2 (Terraform) → instalare (Ansible) → verificare (Bash)**, totul rulat de un pipeline Jenkins.

## Structura

```
config/              fișierul de configurare + exemple
validator/           validate.py, supported.yml (lista tehnologiilor), teste
scripts/verify.sh    verificarea după instalare
ansible/             site.yml (instalare), verify.yml, câte un rol per tehnologie
terraform/           EC2, security group, key pair
k8s/                 Deployment + Service pentru minikube (extra)
Dockerfile, docker-compose.yml, Jenkinsfile
```

## Tehnologii suportate

Lista e definită într-un singur loc: `validator/supported.yml`.

| Tehnologie | Versiuni | Implicit |
|---|---|---|
| docker | latest | latest |
| python | 3.10, 3.11, 3.12, 3.13 | 3.12 |
| nodejs | 20, 22, 24 | 22 |
| java | 17, 21 | 21 |
| mysql | 8.0 | 8.0 |
| nginx | latest | latest |

## Fișierul de configurare

`config/environment.yml`:

```yaml
technologies:
  - name: docker
  - name: python
    version: "3.12"
  - name: nodejs
    version: "22"
```

- `version` e opțional; dacă lipsește se folosește versiunea implicită.
- Versiunile cu zecimale se scriu între ghilimele (`"3.10"`), altfel YAML le citește ca număr (`3.1`).
- Exemple: `config/examples/full.yml` (toate tehnologiile), `config/examples/invalid.yml` (erori, pentru demo).

## Cerințe

- Docker + Docker Compose
- Python 3.10+ (doar pentru rulare fără Docker)
- Ansible 2.15+, Terraform 1.6+
- Cont AWS și cont Docker Hub

## Rulare

### 1. Validare locală

```bash
pip install -r validator/requirements.txt
python validator/validate.py --config config/environment.yml --out-dir output
```

Dacă fișierul e valid se generează `output/install_vars.yml` (variabile Ansible) și `output/verify.conf` (lista pentru verify.sh). Dacă nu, se afișează toate erorile și scriptul iese cu codul 1.

Teste: `cd validator && pip install -r requirements-dev.txt && pytest`

### 2. Docker

```bash
cp .env.example .env          # completează DOCKERHUB_USER
docker compose build
docker compose run --rm validator
docker compose run --rm validator --config /config/examples/invalid.yml --out-dir /output
```

Fișierul de configurare nu e în imagine: folderul `config/` e montat ca volum.

Publicare pe Docker Hub:

```bash
docker login
docker compose push
```

### 3. Server AWS (Terraform)

```bash
ssh-keygen -t ed25519 -f ~/.ssh/env-builder -N ""
cd terraform
cp terraform.tfvars.example terraform.tfvars    # pune IP-ul tău în allowed_ssh_cidr
terraform init
terraform apply
```

Se creează o instanță EC2 Ubuntu 24.04 (t3.small), un security group care permite SSH doar de la IP-ul tău și key pair-ul SSH. `terraform output public_ip` afișează IP-ul.

### 4. Instalare și verificare (Ansible)

```bash
printf "[target]\n%s ansible_user=ubuntu\n" "$(terraform -chdir=terraform output -raw public_ip)" > output/inventory.ini
ansible-playbook --private-key ~/.ssh/env-builder ansible/site.yml
ansible-playbook --private-key ~/.ssh/env-builder ansible/verify.yml
```

Se instalează doar tehnologiile din `install_vars.yml`, fiecare prin rolul ei. `verify.yml` rulează `scripts/verify.sh` pe server și afișează un tabel OK/FAIL.

### 5. Jenkins (tot fluxul automat)

Pe agentul Jenkins trebuie să existe: Docker, Ansible, Terraform, `ssh-keygen`, `curl`. Userul `jenkins` trebuie să fie în grupul `docker`. Presupun că Jenkins rulează direct pe mașină, nu într-un container.

Credentials (Manage Jenkins → Credentials):

| ID | Tip | Conținut |
|---|---|---|
| `dockerhub-creds` | Username with password | user Docker Hub + access token |
| `aws-creds` | Username with password | Access Key ID + Secret Access Key |
| `env-builder-ssh` | SSH Username with private key | user `ubuntu` + cheia privată `~/.ssh/env-builder` |

Plugin-uri: Pipeline, Git, Credentials Binding, SSH Credentials, Timestamper.

În `Jenkinsfile` schimbă `IMAGE` cu userul tău de Docker Hub, apoi creează un job **Pipeline from SCM** pe acest repo.

Etape: Unit tests → Build image → Push to Docker Hub → Validate config → Provision server → Install → Verify.
Dacă validarea eșuează, pipeline-ul se oprește și nu se instalează nimic.

Parametri: `CONFIG_NAME` (fișierul din `config/`), `PROVISION` (creează serverul cu Terraform), `TARGET_HOST` (server existent), `DESTROY_AFTER` (șterge serverul la final).

## Extra

### Tehnologie nouă (nginx)

Adăugarea unei tehnologii înseamnă doi pași:

1. o intrare în `validator/supported.yml` (versiuni, comanda de verificare, textul așteptat);
2. un rol `ansible/roles/<nume>/tasks/main.yml`.

Validarea, instalarea și verificarea o preiau automat. Așa a fost adăugat `nginx`.

### Minikube

Aceeași imagine rulează în modul HTTP (`server.py`):

```bash
minikube start
kubectl apply -f k8s/          # după ce ai pus imaginea ta în deployment.yaml
curl -X POST --data-binary @config/environment.yml "$(minikube service env-builder-validator --url)/validate"
```

Răspunde cu `200` și lista tehnologiilor dacă config-ul e valid, `422` și lista erorilor dacă nu.

## Curățenie

```bash
terraform -chdir=terraform destroy
```

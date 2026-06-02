# Deploying DeepNotes to a VPS

A single `docker compose up` command is all you need. Steps below are for a fresh Ubuntu 22.04 server (Hetzner, DigitalOcean, Linode — any provider works).

## Recommended server size

| Provider | Plan | RAM | Cost |
|---|---|---|---|
| Hetzner | CX22 | 4 GB | ~€4/mo |
| DigitalOcean | Basic Droplet | 4 GB | $24/mo |
| Linode | Shared 4GB | 4 GB | $24/mo |

2 GB RAM works but will be slow during ingestion. 4 GB is comfortable.

## 1 — Provision the server

Create an Ubuntu 22.04 LTS droplet/server. Note its public IP address.

## 2 — Install Docker

SSH into the server and run:

```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
newgrp docker          # apply group change in the current shell
docker compose version # should print v2.x.x
```

## 3 — Clone the repo

```bash
git clone https://github.com/YOUR_USERNAME/DeepNotes.git
cd DeepNotes
```

## 4 — Create your .env file

```bash
cp .env.example .env
nano .env              # paste your Gemini API key
```

Get a free Gemini API key at https://aistudio.google.com/apikey.

## 5 — Open firewall ports

Allow ports 3100 (frontend) and 8100 (backend API) through your firewall:

```bash
# Ubuntu ufw
sudo ufw allow 3100/tcp
sudo ufw allow 8100/tcp
sudo ufw enable
```

If your provider has a cloud-level firewall panel (DigitalOcean, Hetzner), also open those same two ports there.

## 6 — Build and start

```bash
docker compose up -d --build
```

The first build takes **10–20 minutes** (downloading Python ML libraries).  
The first time you upload a PDF or DOCX, ingestion takes an extra **3–5 minutes** while Docling downloads its layout models (~1 GB, cached afterward).

Watch logs:

```bash
docker compose logs -f
```

## 7 — Access the app

Open your browser and go to:

```
http://YOUR_SERVER_IP:3100
```

The frontend will automatically connect to the backend at `:8100` on the same host.

## Updating

```bash
git pull
docker compose up -d --build
```

Data (notebooks, sources, vectors) is stored in Docker named volumes and survives rebuilds.

## Stopping / restarting

```bash
docker compose down      # stop; data preserved in volumes
docker compose up -d     # restart without rebuilding
```

## Useful commands

```bash
# View running containers
docker compose ps

# Follow all logs
docker compose logs -f

# Follow only backend logs
docker compose logs -f backend

# Open a shell inside the backend container
docker compose exec backend bash
```

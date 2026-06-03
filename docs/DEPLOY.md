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

Caddy serves the whole app over HTTPS, so you only need the standard web ports —
80 (HTTP, used for the Let's Encrypt challenge and a redirect to HTTPS) and 443 (HTTPS):

```bash
# Ubuntu ufw
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw allow OpenSSH       # keep SSH open
sudo ufw enable
```

If your provider has a cloud-level firewall panel (DigitalOcean, Hetzner), open the same
two ports there. Ports 3100/8100 are **not** exposed publicly any more — Caddy reaches the
frontend and backend over Docker's internal network.

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

## 7 — Access the app (HTTPS)

The app is served over HTTPS by Caddy, which provisions a real, browser-trusted
certificate automatically. Open:

```
https://2.24.160.117.sslip.io
```

`sslip.io` is a free wildcard-DNS service: `2.24.160.117.sslip.io` resolves to the IP
embedded in it (`2.24.160.117`) with no DNS setup. The first load may take a few seconds
while Caddy obtains the certificate.

**Using your own domain instead:** point an `A` record at the server's IP, then edit the
first line of `Caddyfile` (replace `2.24.160.117.sslip.io` with your domain) and run
`docker compose up -d`. Caddy will issue a certificate for it automatically.

The frontend talks to the backend same-origin via `/api` (Caddy routes `/api/*` to the
backend), so there is nothing else to configure.

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

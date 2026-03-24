# EC2 Setup Guide

This documents the full process of moving the Wordle bot from a laptop to an AWS EC2 instance, including CI/CD so every push to `main` auto-deploys.

## Overview

| Where | What runs |
|---|---|
| Laptop (was) | `npm start` or `pm2 start bot.js` — stopped when laptop closes |
| EC2 (now) | `pm2` keeps bot running 24/7, survives reboots |
| GitHub Actions | On every push to `main`, SSHes into EC2 and restarts the bot with latest code |

## Two SSH Keys You Need

Two separate SSH keys are used — do not mix them up:

| Key | Purpose | Where private key lives | Where public key goes |
|---|---|---|---|
| `github_deploy_key` | EC2 → GitHub (to `git pull`) | EC2 `~/.ssh/` | GitHub repo Deploy keys |
| `github_actions_key` | GitHub Actions runner → EC2 (to deploy) | GitHub secret `EC2_SSH_KEY` | EC2 `~/.ssh/authorized_keys` |

---

## Instance Specs

- **AMI**: Ubuntu 24.04 LTS
- **Instance type**: t3.small (2 vCPU, 2GB RAM — Chromium/Puppeteer needs the RAM)
- **Storage**: 20GB gp3
- **Security group**: SSH inbound (port 22) from your IP only — the bot makes outbound connections only, no inbound ports needed

---

## 1. Connect to EC2

```bash
ssh -i ~/.ssh/your-key.pem ubuntu@<EC2_IP>
```

Tip: add a shortcut to `~/.ssh/config` on your local machine so you can just run `ssh aws`:
```
Host aws
  User ubuntu
  HostName <EC2_IP>
  IdentityFile ~/.ssh/your-key.pem
```

---

## 2. Install System Dependencies (on EC2)

```bash
# Update package lists first
sudo apt-get update

# Node.js 20
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt-get install -y nodejs

# Chromium libs required by Puppeteer
# Note: Ubuntu 24.04 uses t64 suffix variants — use these exact package names
sudo apt-get install -y ca-certificates fonts-liberation libasound2t64 libatk-bridge2.0-0t64 libatk1.0-0t64 libc6 libcairo2 libcups2t64 libdbus-1-3 libexpat1 libfontconfig1 libgbm1 libgcc-s1 libglib2.0-0t64 libgtk-3-0t64 libnspr4 libnss3 libpango-1.0-0 libpangocairo-1.0-0 libstdc++6 libx11-6 libx11-xcb1 libxcb1 libxcomposite1 libxcursor1 libxdamage1 libxext6 libxfixes3 libxi6 libxrandr2 libxrender1 libxss1 libxtst6 lsb-release wget xdg-utils

# Python 3 + venv
sudo apt-get install -y python3 python3-pip python3-venv

# pm2 (global process manager)
sudo npm install -g pm2
```

---

## 3. Set Up GitHub Deploy Key (EC2 → GitHub)

This lets EC2 run `git pull` from your private repo.

```bash
# On EC2 — generate the key
ssh-keygen -t ed25519 -C "ec2-deploy" -f ~/.ssh/github_deploy_key -N ""
cat ~/.ssh/github_deploy_key.pub   # copy this output
```

Add the public key to GitHub: **repo → Settings → Deploy keys → Add deploy key**
- Title: `EC2 Deploy Key`
- Paste the public key
- Leave "Allow write access" unchecked

Configure SSH on EC2 to use this key for GitHub:
```bash
cat >> ~/.ssh/config << 'EOF'
Host github.com
  IdentityFile ~/.ssh/github_deploy_key
  IdentitiesOnly yes
EOF
```

Test it:
```bash
ssh -T git@github.com
# Expected: Hi Terence411/wordle! You've successfully authenticated...
```

---

## 4. Clone Repo and Install Dependencies (on EC2)

```bash
git clone git@github.com:Terence411/wordle.git /home/ubuntu/projects/wordle
cd /home/ubuntu/projects/wordle

# Node dependencies
npm install

# Python dependencies — use a venv, bot.js spawns ./venv/bin/python3
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
deactivate
```

---

## 5. Upload Firebase Credentials (from local machine)

`firebase-key.json` contains sensitive credentials and is never committed to git. Upload it once:

```bash
# Run this on your LOCAL machine
scp -i ~/.ssh/your-key.pem /path/to/firebase-key.json ubuntu@<EC2_IP>:/home/ubuntu/projects/wordle/
```

This file is not touched by future deploys — it stays on the server permanently.

---

## 6. First Run and WhatsApp QR Scan

The bot needs to be linked to a WhatsApp account once. The session is then saved and persists across all future restarts.

Start the bot on EC2:
```bash
cd /home/ubuntu/projects/wordle
pm2 start bot.js --name wordle-bot
pm2 logs wordle-bot
```

Wait until you see `QR code saved to whatsapp-qr.png`. Then on your **local machine**, download it:
```bash
scp -i ~/.ssh/your-key.pem ubuntu@<EC2_IP>:/home/ubuntu/projects/wordle/whatsapp-qr.png ~/whatsapp-qr.png
```

Open the image and scan it: **WhatsApp → Settings → Linked Devices → Link a Device**

Watch the logs — when you see `WhatsApp Bot Ready!` the bot is connected. The QR image is deleted automatically. The session is saved to `.wwebjs_auth/` on EC2 and persists across all restarts — you only need to scan once.

---

## 7. Configure pm2 to Auto-Start on Reboot

Without this, pm2 stops if the EC2 instance reboots.

```bash
pm2 startup
# It prints a command like: sudo env PATH=... pm2 startup systemd -u ubuntu --hp /home/ubuntu
# Copy and run that exact command, then:
pm2 save
```

---

## 8. CI/CD: GitHub Actions SSH Key (GitHub Actions → EC2)

This key lets the GitHub Actions runner SSH into EC2 to deploy. It is separate from the deploy key.

On your **local machine**:
```bash
ssh-keygen -t ed25519 -C "github-actions" -f ~/.ssh/github_actions_key -N ""
```

Add the **public key** to EC2:
```bash
# Print on local machine, then paste into EC2
cat ~/.ssh/github_actions_key.pub

# On EC2:
echo "<paste public key here>" >> ~/.ssh/authorized_keys
```

---

## 9. GitHub Secrets

Go to: **repo → Settings → Secrets and variables → Actions → New repository secret**

| Secret | Value |
|---|---|
| `EC2_HOST` | EC2 public IP or hostname (e.g. `ec2-44-204-62-187.compute-1.amazonaws.com`) |
| `EC2_USER` | `ubuntu` |
| `EC2_SSH_KEY` | Full contents of `~/.ssh/github_actions_key` (the **private** key, including BEGIN/END lines) |
| `EC2_DEPLOY_PATH` | `/home/ubuntu/projects/wordle` |

---

## How CI/CD Works

The workflow file `.github/workflows/deploy.yml` triggers on every push to `main`:

1. GitHub Actions runner SSHes into EC2 using `EC2_SSH_KEY`
2. Runs `git pull origin main` to fetch latest code
3. Runs `npm install` and `pip install` in case dependencies changed
4. Runs `pm2 restart wordle-bot` to reload the bot with the new code

The WhatsApp session and `firebase-key.json` are untouched — only the bot code is updated.

To verify a deploy worked:
- **GitHub → Actions** — workflow should show green
- On EC2: `pm2 status` — check the restart timestamp updated
- On EC2: `pm2 logs wordle-bot` — confirm no startup errors

---

## What Is and Isn't Affected by Deploys

| Item | Location | Touched by deploy? |
|---|---|---|
| Bot code | Pulled from GitHub | Yes — this is the point |
| WhatsApp session | `.wwebjs_auth/` on EC2 | No |
| Firebase credentials | `firebase-key.json` on EC2 | No |
| Firestore data | Firebase cloud | No |
| Python venv | EC2 | Only if `requirements.txt` changed |

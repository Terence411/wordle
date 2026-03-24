# EC2 Setup Guide

One-time setup to deploy the Wordle bot on an AWS EC2 instance.

## Instance Specs

- **AMI**: Ubuntu 24.04 LTS
- **Instance type**: t3.small (2 vCPU, 2GB RAM)
- **Storage**: 20GB gp3
- **Security group**: SSH inbound (port 22) from your IP only

## 1. Connect to EC2

```bash
ssh -i ~/.ssh/your-key.pem ubuntu@<EC2_IP>
```

Tip: add an alias to `~/.ssh/config` on your local machine:
```
Host aws
  User ubuntu
  HostName <EC2_IP>
  IdentityFile ~/.ssh/your-key.pem
```
Then connect with just `ssh aws`.

## 2. Install System Dependencies

```bash
# Node.js 20
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt-get install -y nodejs

# Chromium libs required by Puppeteer (Ubuntu 24.04 t64 variants)
sudo apt-get install -y ca-certificates fonts-liberation libasound2t64 libatk-bridge2.0-0t64 libatk1.0-0t64 libc6 libcairo2 libcups2t64 libdbus-1-3 libexpat1 libfontconfig1 libgbm1 libgcc-s1 libglib2.0-0t64 libgtk-3-0t64 libnspr4 libnss3 libpango-1.0-0 libpangocairo-1.0-0 libstdc++6 libx11-6 libx11-xcb1 libxcb1 libxcomposite1 libxcursor1 libxdamage1 libxext6 libxfixes3 libxi6 libxrandr2 libxrender1 libxss1 libxtst6 lsb-release wget xdg-utils

# Python 3 + venv
sudo apt-get install -y python3 python3-pip python3-venv

# pm2
sudo npm install -g pm2
```

## 3. Set Up GitHub Deploy Key

Generate a deploy key so EC2 can pull from the private repo:

```bash
ssh-keygen -t ed25519 -C "ec2-deploy" -f ~/.ssh/github_deploy_key -N ""
cat ~/.ssh/github_deploy_key.pub   # copy this output
```

Add the public key to GitHub: **repo → Settings → Deploy keys → Add deploy key** (read-only, no write access needed).

Configure SSH on EC2 to use it:
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

## 4. Clone Repo and Install Dependencies

```bash
git clone git@github.com:Terence411/wordle.git /home/ubuntu/projects/wordle
cd /home/ubuntu/projects/wordle

# Node dependencies
npm install

# Python dependencies (in venv)
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## 5. Upload Firebase Credentials

`firebase-key.json` is never committed to git. Upload it once from your local machine:

```bash
scp -i ~/.ssh/your-key.pem /path/to/firebase-key.json ubuntu@<EC2_IP>:/home/ubuntu/projects/wordle/
```

## 6. First Run and WhatsApp QR Scan

Start the bot on EC2:
```bash
cd /home/ubuntu/projects/wordle
pm2 start bot.js --name wordle-bot
pm2 logs wordle-bot
```

Wait until you see `QR code saved to whatsapp-qr.png`, then download it to your local machine:
```bash
scp -i ~/.ssh/your-key.pem ubuntu@<EC2_IP>:/home/ubuntu/projects/wordle/whatsapp-qr.png ~/whatsapp-qr.png
```

Open the image and scan it: **WhatsApp → Settings → Linked Devices → Link a Device**

When you see `WhatsApp Bot Ready!` in the logs, the bot is connected. The QR image is deleted automatically. The session is saved to `.wwebjs_auth/` and persists across restarts — you only need to scan once.

## 7. Configure pm2 Auto-Start on Reboot

```bash
pm2 startup
# Run the command it outputs (looks like: sudo env PATH=... pm2 startup systemd ...)
pm2 save
```

## 8. GitHub Actions CI/CD Setup

Every push to `main` auto-deploys via `.github/workflows/deploy.yml`. It requires 4 GitHub secrets and a separate SSH key for the GitHub Actions runner.

### Create the GitHub Actions SSH key

On your **local machine**:
```bash
ssh-keygen -t ed25519 -C "github-actions" -f ~/.ssh/github_actions_key -N ""
```

Add the **public key** to EC2's authorized keys:
```bash
# On EC2
echo "<paste public key content>" >> ~/.ssh/authorized_keys
```

### Add GitHub Secrets

Go to: **repo → Settings → Secrets and variables → Actions → New repository secret**

| Secret | Value |
|---|---|
| `EC2_HOST` | EC2 public IP or hostname |
| `EC2_USER` | `ubuntu` |
| `EC2_SSH_KEY` | Contents of `~/.ssh/github_actions_key` (the private key) |
| `EC2_DEPLOY_PATH` | `/home/ubuntu/projects/wordle` |

### Verify

Push any change to `main`, then:
- Check **GitHub → Actions** — workflow should show green
- On EC2: `pm2 status` — restart timestamp should update
- On EC2: `pm2 logs wordle-bot` — no errors

## What Is and Isn't Affected by Deploys

| Item | Location | Touched by deploy? |
|---|---|---|
| WhatsApp session | `.wwebjs_auth/` on EC2 | No |
| Firebase credentials | `firebase-key.json` on EC2 | No |
| Firestore data | Firebase cloud | No |
| Bot code | Pulled from GitHub | Yes |

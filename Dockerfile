# Use official Node.js 22 on Debian Bullseye
FROM node:22-bullseye

# Install Python 3, pip, and Chromium dependencies for Puppeteer
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    gconf-service \
    libasound2 \
    libatk1.0-0 \
    libc6 \
    libcairo2 \
    libcups2 \
    libdbus-1-3 \
    libexpat1 \
    libfontconfig1 \
    libgcc1 \
    libgconf-2-4 \
    libgdk-pixbuf2.0-0 \
    libglib2.0-0 \
    libgtk-3-0 \
    libnspr4 \
    libpango-1.0-0 \
    libx11-6 \
    libx11-xcb1 \
    libxcb1 \
    libxcomposite1 \
    libxcursor1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxi6 \
    libxrandr2 \
    libxrender1 \
    libxss1 \
    libxtst6 \
    ca-certificates \
    fonts-liberation \
    libnss3 \
    lsb-release \
    wget \
    xdg-utils \
    --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy package files and install Node.js dependencies
COPY package*.json ./
RUN npm install

# Copy Python dependencies
COPY requirements.txt ./
RUN pip3 install -r requirements.txt

# Copy all project files
COPY . .

# Persist WhatsApp session in a volume
VOLUME ["/app/.wwebjs_auth"]

# Start bot
CMD ["npm", "start"]


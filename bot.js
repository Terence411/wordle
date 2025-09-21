const { Client, LocalAuth } = require('whatsapp-web.js');
const QRCode = require('qrcode'); // use this package for image QR codes
const { spawn } = require('child_process');

const express = require('express');
const path = require('path');
const app = express();

// const client = new Client();
const client = new Client({
    authStrategy: new LocalAuth({ clientId: "wordle-bot" }),
    puppeteer: {
        args: ['--no-sandbox', '--disable-setuid-sandbox']
    }
});

const GROUP_NAME = "Wordle Group";

client.on('qr', qr => {
    // Generate QR code image and save it
    QRCode.toFile('whatsapp-qr.png', qr, { width: 300 }, err => {
        if (err) console.error('Failed to save QR code image:', err);
        else console.log('QR code saved to whatsapp-qr.png. Scan it with WhatsApp!');
    });
});

app.get('/qr', (req, res) => {
    res.sendFile(path.join(__dirname, 'whatsapp-qr.png'));
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => console.log(`QR server running on port ${PORT}`));

client.on('ready', () => console.log('WhatsApp Bot Ready!'));

client.on('message', async message => {
    const chat = await message.getChat();

    // Only process messages from the target group
    if (chat.name !== GROUP_NAME) return;

    if (message.body.startsWith("Wordle")) {
        const sender = message._data.notifyName || message._data.senderName;
        console.log(`Detected Wordle from ${sender}`);

        // Encode multi-line message to base64
        const encodedMsg = Buffer.from(message.body).toString('base64');

        // Spawn Python script
        const python = spawn('python3', ['python/wordle.py', sender, encodedMsg]);

        let output = "";
        python.stdout.on('data', data => output += data.toString());
        python.stderr.on('data', data => console.error(data.toString()));

        python.on('close', () => {
            // Extract leaderboard between our markers
            const match = output.match(/---Leaderboard Start---\n([\s\S]*?)\n---Leaderboard End---/);
            if (match) {
                const leaderboardText = match[1];
                // Send leaderboard back to the group in a code block
                chat.sendMessage("```\n" + leaderboardText + "\n```");
            } else {
                console.log("Leaderboard markers not found in Python output.");
            }
        });
    }
});

client.initialize();

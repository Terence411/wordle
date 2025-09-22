const { Client, LocalAuth } = require('whatsapp-web.js');
const QRCode = require('qrcode'); // use this package for image QR codes
const { spawn } = require('child_process');

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
            const match = output.match(/---Message Start---\n([\s\S]*?)\n---Message End---/);
            if (match) {
                const messageContent = match[1];
                // Send message back to the group in a code block
                chat.sendMessage("```" + messageContent + "```");
            } else {
                console.log("Leaderboard markers not found in Python output.");
            }
        });
    }
});

client.initialize();

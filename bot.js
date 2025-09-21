const { Client } = require('whatsapp-web.js');
const qrcode = require('qrcode-terminal');
const { spawn } = require('child_process');

// const client = new Client();
const client = new Client({
    authStrategy: new LocalAuth() // saves session in .wwebjs_auth
});
const GROUP_NAME = "Wordle Group";

client.on('qr', qr => qrcode.generate(qr, { small: true }));
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
        const python = spawn('python3', ['wordle.py', sender, encodedMsg]);

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

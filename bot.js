const { Client, LocalAuth } = require('whatsapp-web.js');
const QRCode = require('qrcode'); // use this package for image QR codes
const { spawn } = require('child_process');
const fs = require('fs');
const schedule = require('node-schedule');

// const client = new Client();
const client = new Client({
    authStrategy: new LocalAuth({ clientId: "wordle-bot" }),
    puppeteer: {
        args: ['--no-sandbox', '--disable-setuid-sandbox']
    }
});

const GROUP_NAME = "Wordle Group";

const log = (msg) => console.log(`${new Date().toISOString().replace('T', ' ').slice(0, 19)} ${msg}`);

let qrGenerated = false;

client.on('qr', qr => {
    // if qr is already qrGenerated, then return
    if (qrGenerated) return;

    QRCode.toFile('whatsapp-qr.png', qr, { width: 300 }, err => {
        if (err) console.error('Failed to save QR code image:', err);
        else {
            log('QR code saved to whatsapp-qr.png. Scan it with WhatsApp!');
            qrGenerated = true;
        }
    });
});

client.on('ready', () => {
    log('WhatsApp Bot Ready!');
    fs.unlink('whatsapp-qr.png', err => {
        if (err && err.code !== 'ENOENT') console.error('Failed to delete QR code:', err);
    });
});

client.on('message', async message => {
    try {
        const chat = await message.getChat();

        // Only process messages from the target group
        if (chat.name !== GROUP_NAME) return;

        if (message.body.startsWith("Wordle")) {
            const sender = message._data.notifyName || message._data.senderName;
            log(`Detected Wordle from ${sender}`);

            // Encode multi-line message to base64
            const encodedMsg = Buffer.from(message.body).toString('base64');

            // Spawn Python script using venv interpreter
            const python = spawn('./venv/bin/python3', ['wordle_firebase.py', sender, encodedMsg]);

            let output = "";
            python.stdout.on('data', data => output += data.toString());
            python.stderr.on('data', data => console.log(data.toString()));

            python.on('close', () => {
                const reactionMatch = output.match(/---Reaction---\n([\s\S]*?)\n---End Reaction---/);
                const messageMatch = output.match(/---Message Start---\n([\s\S]*?)\n---Message End---/);

                if (reactionMatch) {
                    message.react(reactionMatch[1].trim()).catch(err =>
                        console.error('Failed to react:', err)
                    );
                } else if (messageMatch) {
                    chat.sendMessage("```" + messageMatch[1] + "```").catch(err =>
                        console.error('Failed to send message:', err)
                    );
                } else {
                    log("No output markers found in Python output.");
                }
            });
        }
    } catch (err) {
        console.error('Error handling message:', err);
    }
});

// Every Sunday at 23:59 — send the weekly leaderboard automatically
schedule.scheduleJob('59 23 * * 0', async () => {
    log('Running scheduled weekly leaderboard...');

    if (!client.info) {
        console.error('Scheduled job: client not ready.');
        return;
    }

    const chats = await client.getChats();
    const group = chats.find(c => c.name === GROUP_NAME);

    if (!group) {
        console.error(`Scheduled job: "${GROUP_NAME}" not found.`);
        return;
    }

    const encodedMsg = Buffer.from('Wordle Leaderboard Current').toString('base64');
    const python = spawn('./venv/bin/python3', ['wordle_firebase.py', 'Bot', encodedMsg]);

    let output = "";
    python.stdout.on('data', data => output += data.toString());
    python.stderr.on('data', data => console.error(data.toString()));

    python.on('close', () => {
        const match = output.match(/---Message Start---\n([\s\S]*?)\n---Message End---/);
        if (match) {
            group.sendMessage("```" + match[1] + "```");
        } else {
            log("Scheduled job: no output from Python.");
        }
    });
});

// Prevent unhandled rejections from crashing the process
process.on('unhandledRejection', (reason, promise) => {
    console.error('Unhandled rejection at:', promise, 'reason:', reason);
});

client.initialize();

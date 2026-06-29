require('dotenv').config({ path: '../.env' });

const { Client, LocalAuth } = require('whatsapp-web.js');
const qrcode = require('qrcode-terminal');
const express = require('express');
const axios = require('axios');

const PYTHON_URL = process.env.PYTHON_URL || 'http://localhost:8000';
const PORT = parseInt(process.env.BRIDGE_PORT || '3000');

// Modo test: si ALLOWED_PHONES tiene números, solo responde a esos
const ALLOWED_PHONES = process.env.ALLOWED_PHONES
    ? process.env.ALLOWED_PHONES.split(',').map(p => p.trim()).filter(Boolean)
    : [];

// ── Helpers de formato ──────────────────────────────────────────────────────

// "521234567890@c.us"  →  "+521234567890"
function waIdToPhone(waId) {
    return '+' + waId.replace(/@c\.us$/, '').replace(/@s\.whatsapp\.net$/, '');
}

// "+521234567890"  →  "521234567890@c.us"
function phoneToWaId(phone) {
    return phone.replace(/^\+/, '') + '@c.us';
}

// ── WhatsApp client ─────────────────────────────────────────────────────────

// @lid propio: se aprende en el primer mensaje a uno mismo
let selfLid = null;

const client = new Client({
    authStrategy: new LocalAuth({ dataPath: './.wwebjs_auth' }),
    puppeteer: {
        headless: true,
        executablePath: 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
        args: ['--no-sandbox', '--disable-setuid-sandbox'],
    },
});

client.on('qr', (qr) => {
    console.log('\n📱 Escanea este QR con tu WhatsApp (solo la primera vez):\n');
    qrcode.generate(qr, { small: true });
});

client.on('authenticated', () => {
    console.log('✅ WhatsApp autenticado. La sesión se guardó en .wwebjs_auth/');
});

client.on('ready', async () => {
    console.log(`✅ WhatsApp listo. Escuchando mensajes → ${PYTHON_URL}`);
    // Intentar detectar el @lid de Mensajes guardados buscando en los chats
    try {
        const chats = await client.getChats();
        for (const chat of chats) {
            if (chat.id._serialized.endsWith('@lid')) {
                try {
                    const contact = await chat.getContact();
                    if (contact?.isMe) {
                        selfLid = chat.id._serialized;
                        console.log(`[INFO] Self @lid detectado en chats: ${selfLid}`);
                        break;
                    }
                } catch(_) {}
            }
        }
    } catch(e) { console.log('[WARN] No se pudo detectar self @lid en chats:', e.message); }
});

client.on('disconnected', (reason) => {
    console.warn('⚠️  WhatsApp desconectado:', reason);
});

async function processMessage(msg, chatId) {
    const phone = waIdToPhone(chatId);

    if (ALLOWED_PHONES.length > 0 && !ALLOWED_PHONES.includes(phone)) {
        console.log(`⛔ Ignorado (modo test): ${phone}`);
        return;
    }

    console.log(`📨 ${phone}: ${msg.body.substring(0, 60)}`);

    try {
        const params = new URLSearchParams({ From: phone, Body: msg.body });
        const res = await axios.post(
            `${PYTHON_URL}/webhook/whatsapp`,
            params.toString(),
            { headers: { 'Content-Type': 'application/x-www-form-urlencoded' } }
        );

        const reply = res.data?.reply;
        if (reply) {
            await client.sendMessage(chatId + '@c.us', reply);
            console.log(`📤 Respuesta enviada a ${phone}`);
        }
    } catch (err) {
        console.error(`❌ Error procesando mensaje de ${phone}:`, err.message);
    }
}

// Mensajes entrantes de otros
client.on('message', async (msg) => {
    if (msg.isGroupMsg || msg.from === 'status@broadcast' || msg.fromMe) return;
    await processMessage(msg, msg.from.replace('@c.us', ''));
});

// Mensajes enviados a uno mismo (modo test: escribirte en Mensajes guardados)
client.on('message_create', async (msg) => {
    // Aprender selfLid: en Mensajes guardados los mensajes del bot aparecen con from === to (@lid)
    if (msg.fromMe && msg.from === msg.to && msg.from?.endsWith('@lid')) {
        if (!selfLid) {
            selfLid = msg.from;
            console.log(`[INFO] Self @lid aprendido de Mensajes guardados: ${selfLid}`);
        }
        return; // son respuestas del bot, no procesar
    }

    if (!msg.fromMe) return;

    const myId = client.info?.wid?.user;
    if (!myId) return;

    // Solo procesar mensajes que vienen de mi número @c.us y van al selfLid conocido
    const fromIsMe = msg.from === `${myId}@c.us` || msg.from === `${myId}@s.whatsapp.net`;
    const toIsSelf = msg.to === `${myId}@c.us` || (selfLid && msg.to === selfLid);

    console.log(`[DBG] from=${msg.from} to=${msg.to} fromIsMe=${fromIsMe} toIsSelf=${toIsSelf} selfLid=${selfLid}`);
    if (!fromIsMe || !toIsSelf) return;

    await processMessage(msg, myId);
});

client.initialize();

// ── Express — endpoint para recordatorios proactivos ────────────────────────

const app = express();
app.use(express.json());

// POST /send  { "to": "+521234567890", "message": "texto" }
app.post('/send', async (req, res) => {
    const { to, message } = req.body;

    if (!to || !message) {
        return res.status(400).json({ error: 'Se requieren "to" y "message"' });
    }

    const waId = phoneToWaId(to);
    console.log(`📤 Recordatorio → ${to}`);

    try {
        await client.sendMessage(waId, message);
        res.json({ success: true });
    } catch (err) {
        console.error(`❌ Error enviando a ${to}:`, err.message);
        res.status(500).json({ success: false, error: err.message });
    }
});

app.get('/health', (_req, res) => {
    const state = client.info ? 'ready' : 'connecting';
    res.json({ status: state });
});

app.listen(PORT, () => {
    console.log(`🌉 Bridge escuchando en puerto ${PORT}`);
});

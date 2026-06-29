# Beauty Scheduler — Guía de arranque

Bot de WhatsApp para agendación automática de citas (peluquerías, estéticas y similares).

## Arquitectura

```
Cliente WhatsApp
      ↕
whatsapp-bridge/   ← Node.js  (conecta tu número de WhatsApp)
      ↕  HTTP
main.py            ← Python / FastAPI  (lógica del bot + base de datos)
      ↕  API
Gemini 1.5 Flash   ← IA gratuita de Google (responde preguntas libres)
```

---

## Requisitos

- **Python 3.10+**
- **Node.js 18+** — [nodejs.org](https://nodejs.org)
- Cuenta de Google (para la key de Gemini, gratis)

---

## 1. Configurar el `.env`

El archivo `.env` ya está creado. Comprueba que tenga estos valores:

```env
GEMINI_API_KEY=AIzaSy...   ← debe empezar por AIzaSy (no AQ.)
BUSINESS_NAME=Prueba Negocio
BUSINESS_TIMEZONE=Europe/Madrid
BUSINESS_OPEN_TIME=00:00
BUSINESS_CLOSE_TIME=23:59
BUSINESS_WORKING_DAYS=0,1,2,3,4,5,6
BRIDGE_URL=http://localhost:3000
APP_PORT=8000
```

> **¿De dónde sale la key de Gemini?**
> 1. Ve a [aistudio.google.com](https://aistudio.google.com)
> 2. Botón **"Get API key"** → **"Create API key"**
> 3. Copia el valor — debe empezar por `AIzaSy...`

---

## 2. Personalizar servicios (opcional)

Edita `data/services.json` con los servicios reales del negocio antes de arrancar por primera vez. Se cargan automáticamente al iniciar.

```json
[
  {
    "name": "Corte de cabello",
    "description": "Corte personalizado",
    "duration_minutes": 45,
    "price": 25
  }
]
```

> `price` en la moneda que quieras — es solo un número que se muestra al cliente.

---

## 3. Arrancar — Terminal 1: Python (el bot)

```powershell
cd c:\Users\dredo\Documents\beauty-scheduler
.venv\Scripts\python.exe main.py
```

Deberías ver:
```
INFO: Starting Prueba Negocio Bot...
INFO: Uvicorn running on http://0.0.0.0:8000
```

---

## 4. Arrancar — Terminal 2: Bridge WhatsApp (Node.js)

```powershell
cd c:\Users\dredo\Documents\beauty-scheduler\whatsapp-bridge
npm install        # solo la primera vez (~2 min, descarga Chromium)
npm start
```

La **primera vez** aparece un QR en la terminal. Escanéalo con tu WhatsApp (igual que WhatsApp Web). La sesión queda guardada en `.wwebjs_auth/` y no necesitas volver a escanear.

```
📱 Escanea este QR con tu WhatsApp (solo la primera vez):

[QR aquí]

✅ WhatsApp autenticado.
✅ WhatsApp listo. Escuchando mensajes → http://localhost:8000
```

---

## 5. Probar sin WhatsApp (más rápido)

Con solo la Terminal 1 activa (Python), puedes simular mensajes directamente:

```powershell
function Send-BotMessage($texto) {
    $r = Invoke-WebRequest -Uri "http://localhost:8000/webhook/whatsapp" `
        -Method POST `
        -ContentType "application/x-www-form-urlencoded" `
        -Body "From=%2B34650683914&Body=$([uri]::EscapeDataString($texto))"
    ($r.Content | ConvertFrom-Json).reply
}

Send-BotMessage "hola"     # → menú principal
Send-BotMessage "1"        # → agendar cita → lista de servicios
Send-BotMessage "1"        # → fechas disponibles
Send-BotMessage "1"        # → horas disponibles
Send-BotMessage "1"        # → confirmación
Send-BotMessage "si"       # → cita agendada ✅
Send-BotMessage "2"        # → ver mis citas
Send-BotMessage "4"        # → modo IA (requiere GEMINI_API_KEY válida)
Send-BotMessage "menu"     # → volver al menú en cualquier momento
```

---

## Estructura del proyecto

```
beauty-scheduler/
├── main.py                        ← Servidor + scheduler de recordatorios
├── .env                           ← Credenciales (nunca subir a git)
├── data/services.json             ← Servicios del negocio (seed inicial)
├── src/
│   ├── config.py                  ← Variables de entorno
│   ├── ai/assistant.py            ← IA con Gemini 1.5 Flash (gratis)
│   ├── api/
│   │   ├── webhook.py             ← Webhook activo (bridge)
│   │   └── webhook_twilio.py      ← Backup por si usas Twilio
│   ├── bot/
│   │   ├── conversation.py        ← Máquina de estados del bot
│   │   └── templates.py           ← Mensajes en español
│   ├── models/                    ← Base de datos SQLAlchemy
│   └── scheduling/                ← Disponibilidad y gestión de citas
└── whatsapp-bridge/
    ├── index.js                   ← Bridge Node.js ↔ Python
    └── package.json
```

---

## Flujo de la conversación

```
hola / menu / inicio  →  Menú principal
  1  →  Agendar cita  →  servicio → fecha → hora → confirmación
  2  →  Ver mis citas
  3  →  Cancelar una cita
  4  →  Chat libre con IA (Gemini)
```

---

## Para producción

- Cambia `DATABASE_URL` a PostgreSQL
- Despliega en Railway, Render o un VPS con IP pública
- El bridge Node.js debe correr en el mismo servidor
- El número de WhatsApp conectado al bridge es el número de atención del negocio

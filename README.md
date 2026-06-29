# Beauty Scheduler — Bot de WhatsApp para citas

Bot de agendación automática de citas por WhatsApp para peluquerías, estéticas y centros de belleza.

Tus clientes escriben al WhatsApp del negocio y el bot les guía paso a paso para agendar, ver o cancelar citas. Tú lo gestionas todo desde un panel de administración web.

## Funcionalidades

**Bot WhatsApp**
- Flujo conversacional completo: agendar, ver y cancelar citas
- Horarios disponibles agrupados por mañana/tarde
- Detección automática de conflictos (dos clientes, mismo hueco)
- Recordatorios automáticos 24h antes por WhatsApp
- Chat con IA (Gemini) para preguntas libres sobre servicios
- Clientes vetados reciben mensaje personalizable
- Todos los mensajes del bot editables desde el panel

**Panel de Administración**
- Agenda visual con FullCalendar (día/semana/mes)
- Dashboard con estadísticas y facturación del mes
- CRUD de citas, clientes, servicios y horarios
- Horarios con descansos (ej. hora de comer) y bloqueos puntuales
- Sistema de roles: superadmin / admin / viewer
- Configuración de visibilidad de secciones por rol
- Gestión de usuarios administradores
- Feed iCal para sincronizar con Google Calendar, Apple Calendar y Outlook
- Icono del negocio personalizable

## Arquitectura

```
Cliente WhatsApp
      |
whatsapp-bridge/    Node.js (whatsapp-web.js, gratuito)
      | HTTP
main.py             Python / FastAPI (lógica + BD)
      | API
Gemini 1.5 Flash    IA de Google (gratis)
```

## Requisitos

- **Python 3.10+**
- **Node.js 18+**
- Cuenta de Google para la API key de Gemini (gratis): [aistudio.google.com](https://aistudio.google.com)

## Instalación

```bash
# 1. Clonar
git clone https://github.com/tu-usuario/beauty-scheduler.git
cd beauty-scheduler

# 2. Backend Python
python -m venv .venv
.venv/Scripts/activate  # Windows
# source .venv/bin/activate  # Linux/Mac
pip install -r requirements.txt

# 3. Bridge WhatsApp
cd whatsapp-bridge
npm install
cd ..

# 4. Configurar
cp .env.example .env
# Edita .env con tus datos (API key, nombre del negocio, etc.)

# 5. Personalizar servicios (opcional)
# Edita data/services.json antes del primer arranque
```

## Arranque

### Desarrollo (dos terminales)

**Terminal 1 — Servidor Python:**
```bash
python main.py
```

**Terminal 2 — Bridge WhatsApp:**
```bash
cd whatsapp-bridge
npm start
```

La primera vez aparece un QR en la terminal. Escanea con WhatsApp (igual que WhatsApp Web). La sesion queda guardada.

### Produccion (PM2, sin terminales)

```bash
npm install -g pm2
pm2 start pm2.config.js
pm2 save
pm2 startup  # arranca automaticamente con el sistema
```

## Acceso al panel

Abre `http://localhost:8001/admin`

Usuario por defecto: `admin` / `admin1234` (cambiar en `.env`)

## Estructura del proyecto

```
beauty-scheduler/
├── main.py                         Servidor + scheduler de recordatorios
├── .env                            Credenciales (no se sube a git)
├── .env.example                    Plantilla de configuracion
├── pm2.config.js                   Configuracion PM2 (produccion)
├── migrate.py                      Migraciones de BD
├── data/
│   ├── services.json               Servicios iniciales (seed)
│   ├── messages.json               Mensajes del bot (editables desde panel)
│   └── role_visibility.json        Visibilidad de secciones por rol
├── src/
│   ├── config.py                   Variables de entorno
│   ├── ai/assistant.py             IA con Gemini 1.5 Flash
│   ├── api/
│   │   ├── admin.py                API del panel (citas, clientes, etc.)
│   │   ├── webhook.py              Webhook del bridge
│   │   └── webhook_twilio.py       Webhook alternativo para Twilio
│   ├── bot/
│   │   ├── conversation.py         Maquina de estados del bot
│   │   ├── templates.py            Plantillas de mensajes
│   │   ├── messages.py             Sistema de mensajes editables
│   │   └── business_config.py      Config del negocio (emoji, etc.)
│   ├── models/                     Modelos SQLAlchemy
│   │   ├── appointment.py          Citas
│   │   ├── client.py               Clientes
│   │   ├── service.py              Servicios
│   │   ├── business_hours.py       Horarios con descansos
│   │   ├── time_block.py           Bloqueos puntuales
│   │   ├── admin_user.py           Usuarios del panel
│   │   └── conversation.py         Estado de conversacion
│   └── scheduling/
│       ├── appointment_service.py  Logica de citas
│       └── availability.py         Calculo de disponibilidad
├── static/admin.html               Panel de administracion (SPA)
├── whatsapp-bridge/
│   ├── index.js                    Bridge Node.js <-> Python
│   └── package.json
└── tests/
```

## Flujo del bot

```
hola / menu / inicio  ->  Menu principal
  1  ->  Agendar cita  ->  servicio -> fecha -> hora -> confirmacion
  2  ->  Ver mis citas
  3  ->  Cancelar una cita
  4  ->  Chat libre con IA (Gemini)
```

## Tecnologias

- **Backend:** Python, FastAPI, SQLAlchemy, APScheduler
- **BD:** SQLite (WAL mode) / PostgreSQL
- **WhatsApp:** whatsapp-web.js (Node.js)
- **IA:** Google Gemini 1.5 Flash
- **Frontend:** Bootstrap 5.3, FullCalendar v6
- **Auth:** HMAC-SHA256 tokens, PBKDF2 passwords

## Produccion

- Cambia `ADMIN_SECRET` y `CALENDAR_KEY` en `.env`
- Para alto volumen, cambia `DATABASE_URL` a PostgreSQL
- El servidor debe tener IP publica (o usar ngrok) para Google Calendar
- El numero de WhatsApp conectado al bridge es el numero de atencion

## Licencia

MIT

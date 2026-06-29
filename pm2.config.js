module.exports = {
  apps: [
    {
      name: "beauty-api",
      script: ".venv/Scripts/python.exe",
      args: "main.py",
      cwd: __dirname,
      interpreter: "none",
      autorestart: true,
      watch: false,
      max_restarts: 10,
      restart_delay: 3000,
      env: {
        APP_PORT: "8001"
      },
      log_file: "logs/api.log",
      error_file: "logs/api-error.log",
      time: true,
    },
    {
      name: "beauty-bridge",
      script: "whatsapp-bridge/index.js",
      cwd: __dirname,
      interpreter: "node",
      autorestart: true,
      watch: false,
      max_restarts: 10,
      restart_delay: 5000,
      log_file: "logs/bridge.log",
      error_file: "logs/bridge-error.log",
      time: true,
    }
  ]
};

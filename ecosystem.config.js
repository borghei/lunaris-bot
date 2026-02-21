module.exports = {
  apps: [
    {
      name: "lunaris",
      script: "venv/bin/python",
      args: "run.py",
      cwd: "/path/to/lunaris-bot",
      autorestart: true,
      max_restarts: 15,
      min_uptime: "10s",
      restart_delay: 5000,
      max_memory_restart: "256M",
      log_date_format: "YYYY-MM-DD HH:mm:ss Z",
      error_file: "logs/pm2-error.log",
      out_file: "logs/pm2-out.log",
      env: {
        PYTHONUNBUFFERED: "1",
      },
    },
  ],
};

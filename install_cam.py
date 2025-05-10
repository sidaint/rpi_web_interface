import os
import subprocess
from pathlib import Path

def run(cmd, check=True, shell=False):
    print(f"🔧 Running: {' '.join(cmd) if isinstance(cmd, list) else cmd}")
    subprocess.run(cmd, check=check, shell=shell)

def apt_install(packages):
    run(["sudo", "apt", "update"])
    run(["sudo", "apt", "install", "-y"] + packages)

def setup_venv():
    run(["python3", "-m", "venv", "space_rpi_cam_env", "--system-site-packages"])
    python = "./space_rpi_cam_env/bin/python"
    run([python, "-m", "pip", "install", "--upgrade", "pip"])
    run([python, "-m", "pip", "install", "flask", "pillow", "setproctitle"])

def create_dirs():
    os.makedirs("photos", exist_ok=True)
    os.makedirs("videos", exist_ok=True)

def create_service():
    service_content = f"""[Unit]
Description=Space RPi Cam Web UI
After=network.target

[Service]
User={os.getenv('USER')}
WorkingDirectory={str(Path.cwd())}
ExecStart={str(Path.cwd())}/space_rpi_cam_env/bin/python {str(Path.cwd())}/app.py
Restart=always
Environment=FLASK_ENV=production
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
"""
    service_path = "/etc/systemd/system/space_rpi_cam.service"
    temp_path = "space_rpi_cam.service"

    with open(temp_path, "w") as f:
        f.write(service_content)

    run(["sudo", "mv", temp_path, service_path])
    run(["sudo", "systemctl", "daemon-reexec"])
    run(["sudo", "systemctl", "daemon-reload"])
    run(["sudo", "systemctl", "enable", "space_rpi_cam"])
    run(["sudo", "systemctl", "start", "space_rpi_cam"])

def main():
    print("🚀 Starting Space RPi Cam installation")

    apt_install([
        "python3-venv", "python3-picamera2", "python3-libcamera", "libcap-dev",
        "ffmpeg", "python3-dev", "gcc"
    ])

    setup_venv()
    create_dirs()
    create_service()

    print("✅ Installation complete.")
    print("➡️ Visit http://<your-pi-ip>:5000 in a browser.")

if __name__ == "__main__":
    main()


# 🚀 Space RPi Cam – Raspberry Pi Camera Web Interface

**Space RPi Cam** is a lightweight, full-featured web interface for Raspberry Pi camera modules. It offers live preview, photo capture, timelapse scheduling, and video recording — all through a responsive, password-protected UI.

Built with Python (Flask) and designed for low-resource devices like the Raspberry Pi Zero 2W.

---

## 🌟 Features

**Take photos** at high resolution
**Record videos** with toggle button
**Timelapse mode** with configurable intervals and durations
**Scheduled timelapse** from any start to end time (spanning midnight supported)
**Photo & video gallery** with folders, thumbnails, and individual downloads
**Dynamic camera settings**: resolution, white balance, rotation
**Password-protected web interface** (credentials stored in editable `credentials.json`)
**Live disk usage monitor** with free space indicator
**Manual video creation** from timelapse folders
**Hotspot fallback** (auto Wi-Fi AP if no network found) *(optional)*
**Live feed toggle** to save CPU resources

---

## Hardware Requirements

- Raspberry Pi (Zero 2W or newer recommended)
- Raspberry Pi Camera Module (compatible with AI camera)
- microSD card (at least 8GB)
- Internet or local Wi-Fi (optional for remote access)

---

## Installation

1. Clone the repository:

   ```bash
   git clone https://github.com/yourusername/space_rpi_cam.git
   cd space_rpi_cam
   ```

3. Set executable permissions and install as a service:

   ```bash
   sudo python3 install_cam.py
   ```

4. Start the web interface:

   ```bash
   sudo systemctl start space_rpi_cam
   sudo systemctl enable space_rpi_cam  # (optional, auto start on boot)
   ```

---

## Login Credentials

Stored in `credentials.json`. Default:

```json
{
  "username": "admin",
  "password": "admin"
}
```

Change from the **"Account"** section in the UI or by editing the file via SSH.

---

## Accessing the Interface

Once running, access the interface in your browser:

```bash
http://<your_pi_ip>:5000
```

## Folder Structure

- `photos/` — All photos and timelapse folders
- `videos/` — All recorded videos
- `templates/` — HTML templates
- `static/` — CSS
- `app.py` — Main Flask application
- `camera.py` — Camera controls and logic
- `install_cam.py` — Installer that creates the systemd service and installs everything required
- `credentials.json` — Web UI login credentials

---

## License

MIT License. Free for personal and commercial use.

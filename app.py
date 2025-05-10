# space_rpi_cam/app.py
from flask import Flask, render_template, Response, request, redirect, url_for, send_from_directory, jsonify, session
from camera import CameraHandler
import threading, os, subprocess, json, shutil
from functools import wraps
from datetime import datetime, timedelta

import setproctitle
setproctitle.setproctitle("space_rpi_cam")

app = Flask(__name__)
app.secret_key = 'j3m%R^u8z1LkP#b29Xd7!vGq*A4sYwE0'

CREDENTIALS_FILE = 'credentials.json'
if os.path.exists(CREDENTIALS_FILE):
    with open(CREDENTIALS_FILE) as f:
        CREDS = json.load(f)
else:
    CREDS = {"username": "admin", "password": "admin"}

scheduled_tasks = []
scheduled_timelapse_start = None
scheduled_timelapse_end = None

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

camera_handler = CameraHandler()

@app.route('/schedule_timelapse', methods=['POST'])
@login_required
def schedule_timelapse():
    global scheduled_timelapse_start, scheduled_timelapse_end
    start_str = request.form.get('start_time')
    end_str = request.form.get('end_time')
    try:
        now = datetime.now()
        start_time = datetime.strptime(start_str, '%H:%M').replace(year=now.year, month=now.month, day=now.day)
        end_time = datetime.strptime(end_str, '%H:%M').replace(year=now.year, month=now.month, day=now.day)

        if start_time <= now:
            start_time += timedelta(days=1)
        if end_time <= start_time:
            end_time += timedelta(days=1)

        scheduled_timelapse_start = start_time
        scheduled_timelapse_end = end_time

        delay_start = (start_time - now).total_seconds()
        duration = (end_time - start_time).total_seconds()

        def start():
            camera_handler.start_timelapse()
            t2 = threading.Timer(duration, stop_timelapse)
            t2.start()
            scheduled_tasks.append(t2)

        t1 = threading.Timer(delay_start, start)
        t1.start()
        scheduled_tasks.append(t1)

        return redirect(url_for('index'))

    except Exception as e:
        return str(e), 500

@app.route('/reset_password', methods=['POST'])
@login_required
def reset_password():
    new_user = request.form.get('username')
    new_pass = request.form.get('password')
    if new_user and new_pass:
        with open(CREDENTIALS_FILE, 'w') as f:
            json.dump({'username': new_user, 'password': new_pass}, f)
        return redirect(url_for('logout'))
    return "Invalid input", 400

@app.route('/toggle_feed')
@login_required
def toggle_feed():
    if camera_handler.is_feed_enabled():
        camera_handler.disable_feed()
    else:
        camera_handler.enable_feed()
    return redirect(url_for('index'))

@app.route('/')
@login_required
def index():
    total, used, free = shutil.disk_usage(".")
    disk_percent = round((used / total) * 100)
    disk_free = f"{free // (1024 ** 2)} MB"
    disk_total = f"{total // (1024 ** 2)} MB"

    timelapse_badge_text = ""
    now = datetime.now()

    if camera_handler.is_timelapse_running():
        if scheduled_timelapse_end:
            timelapse_badge_text = f"Timelapse until {scheduled_timelapse_end.strftime('%H:%M')}"
        else:
            # Calculate expected end based on duration_minutes
            duration = camera_handler.get_settings().get("duration_minutes", 0)
            if duration:
                expected_end = now + timedelta(minutes=duration)
                timelapse_badge_text = f"Timelapse until {expected_end.strftime('%H:%M')}"
            else:
                timelapse_badge_text = "Timelapse running"
    elif scheduled_timelapse_start:
        mins = int((scheduled_timelapse_start - now).total_seconds() // 60)
        if mins > 0:
            timelapse_badge_text = f"Timelapse scheduled for {scheduled_timelapse_start.strftime('%H:%M')}"


    return render_template(
        'index.html',
        settings=camera_handler.get_settings(),
        resolutions=camera_handler.get_available_resolutions(),
        recording=camera_handler.is_recording(),
        timelapse=camera_handler.is_timelapse_running(),
        current_time=now.strftime("%Y-%m-%d %H:%M:%S"),
        disk_percent=disk_percent,
        disk_free=disk_free,
        disk_total=disk_total,
        live_feed_enabled=camera_handler.is_feed_enabled(),
        timelapse_badge_text=timelapse_badge_text,
        scheduled_timelapse_start=scheduled_timelapse_start,
        scheduled_timelapse_end=scheduled_timelapse_end,
    )

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        user = request.form.get('username')
        pwd = request.form.get('password')
        if user == CREDS['username'] and pwd == CREDS['password']:
            session['logged_in'] = True
            return redirect(url_for('index'))
        else:
            error = 'Invalid credentials'
    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/video_feed')
@login_required
def video_feed():
    return Response(camera_handler.gen_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/take_photo')
@login_required
def take_photo():
    camera_handler.take_photo()
    return redirect(url_for('index'))

@app.route('/toggle_recording')
@login_required
def toggle_recording():
    if camera_handler.is_recording():
        camera_handler.stop_recording()
    else:
        camera_handler.start_recording()
    return redirect(url_for('index'))

@app.route('/start_timelapse')
@login_required
def start_timelapse():
    camera_handler.start_timelapse()
    return redirect(url_for('index'))

@app.route('/update_settings', methods=['POST'])
@login_required
def update_settings():
    preview_res = request.form.get('preview_res')
    photo_res = request.form.get('photo_res')
    white_balance = request.form.get('white_balance')
    interval = request.form.get('interval')
    duration_minutes = request.form.get('duration_minutes')
    rotation = request.form.get('rotation')
    camera_handler.update_settings(preview_res, photo_res, white_balance, interval, duration_minutes, rotation)
    return redirect(url_for('index'))

@app.route('/stop_timelapse')
@login_required
def stop_timelapse():
    global scheduled_timelapse_start, scheduled_timelapse_end
    camera_handler.stop_timelapse()
    for t in scheduled_tasks:
        t.cancel()
    scheduled_tasks.clear()
    scheduled_timelapse_start = None
    scheduled_timelapse_end = None
    return redirect(url_for('index'))

@app.route('/gallery/photos')
@login_required
def gallery_photos():
    base_dir = 'photos'
    folders = []
    photo_files = []

    # Find all folders in 'photos'
    for entry in os.listdir(base_dir):
        full_path = os.path.join(base_dir, entry)
        if os.path.isdir(full_path):
            folders.append(entry)
        elif entry.endswith('.jpg'):
            photo_files.append(entry)

    return render_template('gallery.html', files=photo_files, folders=sorted(folders), type='photo', current_folder=None)

@app.route('/gallery/photos/<folder>')
@login_required
def gallery_photos_folder(folder):
    folder_path = os.path.join('photos', folder)
    photo_files = []
    if os.path.exists(folder_path):
        for file in sorted(os.listdir(folder_path)):
            if file.endswith('.jpg'):
                photo_files.append(os.path.join(folder, file))  # Relative path for linking

    return render_template('gallery.html', files=photo_files, folders=[], type='photo', current_folder=folder)


@app.route('/gallery/videos')
@login_required
def gallery_videos():
    video_files = []
    for root, dirs, files in os.walk('videos'):
        for file in sorted(files):
            if file.endswith(('.mp4', '.h264')):
                path = os.path.join(root, file)
                rel_path = os.path.relpath(path, 'videos')
                video_files.append(rel_path)
    for root, dirs, files in os.walk('photos'):
        for file in sorted(files):
            if file.endswith('.mp4'):
                path = os.path.join(root, file)
                rel_path = os.path.relpath(path, 'photos')
                video_files.append('../photos/' + rel_path)
    return render_template('gallery.html', files=video_files, type='video')

@app.route('/media/photos/<path:filename>')
@login_required
def media_photos(filename):
    return send_from_directory('photos', filename, as_attachment=True)

@app.route('/media/videos/<path:filename>')
@login_required
def media_videos(filename):
    return send_from_directory('videos', filename, as_attachment=True)

@app.route('/recording_status')
@login_required
def recording_status():
    return jsonify({
        "recording": camera_handler.is_recording(),
        "timelapse": camera_handler.is_timelapse_running(),
        "duration": camera_handler.get_recording_duration()
    })

@app.route('/convert_timelapse/<folder>')
@login_required
def convert_timelapse(folder):
    def run_ffmpeg(folder):
        input_path = os.path.join('photos', folder)
        output_path = os.path.join('photos', folder + '.mp4')
        if not os.path.exists(input_path) or not os.path.isdir(input_path):
            return
        image_files = [f for f in os.listdir(input_path) if f.endswith('.jpg')]
        if len(image_files) < 2:
            return
        if os.path.exists(output_path):
            return
        subprocess.run([
            "ffmpeg", "-y", "-framerate", "10",
            "-pattern_type", "glob", "-i", os.path.join(input_path, "img_*.jpg"),
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            output_path
        ])
    threading.Thread(target=run_ffmpeg, args=(folder,), daemon=True).start()
    return ('', 204)

@app.route('/account', methods=['GET', 'POST'])
@login_required
def account():
    message = None
    error = None
    if request.method == 'POST':
        new_user = request.form.get('username')
        new_pass = request.form.get('password')
        if new_user and new_pass:
            try:
                with open(CREDENTIALS_FILE, 'w') as f:
                    json.dump({"username": new_user, "password": new_pass}, f)
                message = "Credentials updated! Please log in again."
                session.clear()
                return redirect(url_for('login'))
            except Exception as e:
                error = f"Failed to save credentials: {str(e)}"
        else:
            error = "Both fields are required."
    return render_template("account.html", current_user=CREDS.get("username", "admin"), message=message, error=error)

@app.route('/delete/<media_type>/<path:filename>', methods=['POST'])
@login_required
def delete_media(media_type, filename):
    base_dir = 'photos' if media_type == 'photo' else 'videos'
    path = os.path.join(base_dir, filename)
    if os.path.exists(path):
        if os.path.isdir(path):  # Delete timelapse folder
            shutil.rmtree(path)
            mp4 = path + '.mp4'
            if os.path.exists(mp4):
                os.remove(mp4)
        else:
            os.remove(path)
    return '', 204

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)

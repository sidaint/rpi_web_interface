# motioneye_clone/app.py
from flask import Flask, render_template, Response, request, redirect, url_for, send_from_directory, jsonify, session
from camera import CameraHandler
import threading, os, subprocess, json, shutil
from functools import wraps
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = 'j3m%R^u8z1LkP#b29Xd7!vGq*A4sYwE0'

# Load credentials
CREDENTIALS_FILE = 'credentials.json'
if os.path.exists(CREDENTIALS_FILE):
    with open(CREDENTIALS_FILE) as f:
        CREDS = json.load(f)
else:
    CREDS = {"username": "admin", "password": "admin"}

# Login required decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

camera_handler = CameraHandler()
scheduled_tasks = []

@app.route('/schedule_timelapse', methods=['POST'])
@login_required
def schedule_timelapse():
    start_str = request.form.get('start_time')  # format HH:MM
    end_str = request.form.get('end_time')
    try:
        now = datetime.now()
        start_time = datetime.strptime(start_str, '%H:%M').replace(year=now.year, month=now.month, day=now.day)
        end_time = datetime.strptime(end_str, '%H:%M').replace(year=now.year, month=now.month, day=now.day)

        # If start_time already passed, assume tomorrow
        if start_time <= now:
            start_time += timedelta(days=1)

        # If end_time is before start_time, assume end_time is next day
        if end_time <= start_time:
            end_time += timedelta(days=1)

        delay_start = (start_time - now).total_seconds()
        duration = (end_time - start_time).total_seconds()

        def start():
            camera_handler.start_timelapse()
            t2 = threading.Timer(duration, camera_handler.stop_timelapse)
            t2.start()
            scheduled_tasks.append(t2)

        t1 = threading.Timer(delay_start, start)
        t1.start()
        scheduled_tasks.append(t1)

        return redirect(url_for('index'))

    except Exception as e:
        return str(e), 500

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

    return render_template(
        'index.html',
        settings=camera_handler.get_settings(),
        resolutions=camera_handler.get_available_resolutions(),
        recording=camera_handler.is_recording(),
        timelapse=camera_handler.is_timelapse_running(),
        current_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        disk_percent=disk_percent,
        disk_free=disk_free,
        disk_total=disk_total,
        live_feed_enabled=camera_handler.is_feed_enabled(),
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

@app.route('/start_recording')
@login_required
def start_recording():
    camera_handler.start_recording()
    return redirect(url_for('index'))

@app.route('/stop_recording')
@login_required
def stop_recording():
    camera_handler.stop_recording()
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

@app.route('/start_timelapse')
@login_required
def start_timelapse():
    camera_handler.start_timelapse()
    return redirect(url_for('index'))

@app.route('/stop_timelapse')
@login_required
def stop_timelapse():
    camera_handler.stop_timelapse()
    for t in scheduled_tasks:
        t.cancel()  # ❌ Cancel any scheduled timers
    scheduled_tasks.clear()  # 🧹 Clear the list
    return redirect(url_for('index'))

@app.route('/gallery/photos')
@login_required
def gallery_photos():
    photo_files = []
    folders = set()
    for root, dirs, files in os.walk('photos'):
        for file in sorted(files):
            if file.endswith('.jpg'):
                rel_dir = os.path.relpath(root, 'photos')
                rel_path = os.path.join(rel_dir, file) if rel_dir != '.' else file
                photo_files.append(rel_path)
                if '/' in rel_path:
                    folders.add(rel_path.split('/')[0])
    return render_template('gallery.html', files=photo_files, folders=sorted(folders), type='photo')

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

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)


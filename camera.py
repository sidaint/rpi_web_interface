# space_rpi_cam/camera.py
from picamera2 import Picamera2
from picamera2.encoders import H264Encoder
from picamera2.outputs import FileOutput
import threading, time, io, os, subprocess
from datetime import datetime
from PIL import Image
from libcamera import Transform
import threading

class CameraHandler:
    def __init__(self):
        self.picam2 = Picamera2()
        modes = self.picam2.sensor_modes
        res_set = sorted({mode['size'] for mode in modes})
        self.available_resolutions = res_set

        self.settings = {
            'preview_resolution': res_set[0],
            'photo_resolution': res_set[-1],
            'white_balance': 'auto',
            'rotation': 0,
            'interval': 10,
            'duration_minutes': 0
        }
        self.frame_lock = threading.Lock()
        self.frame = None
        self.streaming = False
        self.recording = False
        self.timelapse_running = False
        self.timelapse_thread = None
        self.timelapse_folder = None
        self.recording_start_time = None
        self.recording_filename = None
        self._configure_camera(stream=True)
        self.live_feed_enabled = True

    def _get_transform(self):
        rot = int(self.settings.get('rotation', 0))
        return Transform(rotation=rot)

    def _configure_camera(self, stream=False):
        self.picam2.stop()
        res = self.settings['preview_resolution'] if stream else self.settings['photo_resolution']
        config = self.picam2.create_preview_configuration(main={'size': res}, transform=self._get_transform())
        self.picam2.configure(config)
        self.picam2.start()

    def gen_frames(self):
        while True:
            if not self.live_feed_enabled:
                time.sleep(0.5)
                continue
            frame = self.picam2.capture_array()
            img = Image.fromarray(frame).convert("RGB")
            buf = io.BytesIO()
            img.save(buf, format='JPEG')
            frame_bytes = buf.getvalue()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')


    def take_photo(self, custom_path=None):
        if self.recording:
            return
        self._configure_camera(stream=False)
        if not custom_path:
            filename = datetime.now().strftime("photos/photo_%Y%m%d_%H%M%S.jpg")
        else:
            filename = custom_path
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        self.picam2.capture_file(filename)

    def start_recording(self):
        if self.recording or self.timelapse_running:
            return False
        self._configure_camera(stream=False)
        time.sleep(1)
        filename = datetime.now().strftime("videos/video_%Y%m%d_%H%M%S.h264")
        self.encoder = H264Encoder()
        self.picam2.start_recording(self.encoder, FileOutput(filename))
        self.recording = True
        self.recording_start_time = time.time()
        self.recording_filename = filename
        return True

    def stop_recording(self):
        if self.recording:
            self.picam2.stop_recording()
            self.recording = False
            duration = time.time() - self.recording_start_time
            if duration < 1:
                os.remove(self.recording_filename)
            self.recording_start_time = None
            self.recording_filename = None
            self._configure_camera(stream=True)

    def update_settings(self, preview_res, photo_res, white_balance, interval, duration_minutes, rotation):
        if preview_res:
            w, h = map(int, preview_res.split('x'))
            self.settings['preview_resolution'] = (w, h)
        if photo_res:
            w, h = map(int, photo_res.split('x'))
            self.settings['photo_resolution'] = (w, h)
        if white_balance:
            self.settings['white_balance'] = white_balance
        if interval:
            self.settings['interval'] = int(interval)
        if duration_minutes:
            self.settings['duration_minutes'] = int(duration_minutes)
        if rotation:
            self.settings['rotation'] = int(rotation)
        self._configure_camera(stream=True)

    def start_timelapse(self):
        if self.timelapse_running or self.recording:
            return False
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.timelapse_folder = f"photos/timelapse_{timestamp}"
        os.makedirs(self.timelapse_folder, exist_ok=True)
        self.timelapse_running = True
        self.timelapse_thread = threading.Thread(target=self._timelapse_loop)
        self.timelapse_thread.start()
        return True

    def stop_timelapse(self):
        self.timelapse_running = False
        if self.timelapse_thread:
            self.timelapse_thread.join()
#            self._assemble_timelapse_video()

    def _timelapse_loop(self):
        count = 0
        max_photos = 0
        if self.settings['duration_minutes'] > 0:
            max_photos = (self.settings['duration_minutes'] * 60) // self.settings['interval']

        while self.timelapse_running:
            photo_path = os.path.join(self.timelapse_folder, f"img_{count:04}.jpg")
            self.take_photo(custom_path=photo_path)
            count += 1
            if max_photos and count >= max_photos:
                break
            time.sleep(self.settings['interval'])
        self.timelapse_running = False

    def _assemble_timelapse_video(self):
        if not self.timelapse_folder:
            return
        output_path = self.timelapse_folder + ".mp4"
        try:
            subprocess.run([
                "ffmpeg", "-y", "-framerate", "10",
                "-pattern_type", "glob", "-i",
                os.path.join(self.timelapse_folder, "img_*.jpg"),
                "-c:v", "libx264", "-pix_fmt", "yuv420p",
                output_path
            ], check=True)
        except Exception as e:
            print(f"Failed to assemble timelapse video: {e}")

    def get_settings(self):
        return self.settings

    def get_available_resolutions(self):
        return self.available_resolutions

    def is_recording(self):
        return self.recording

    def is_timelapse_running(self):
        return self.timelapse_running

    def get_recording_duration(self):
        if self.recording and self.recording_start_time:
            return int(time.time() - self.recording_start_time)
        return 0

    def enable_feed(self):
        self.live_feed_enabled = True
    
    def disable_feed(self):
        self.live_feed_enabled = False
    
    def is_feed_enabled(self):
        return self.live_feed_enabled


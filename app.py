import os
import subprocess
import yt_dlp
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import uuid
from pytubefix import YouTube

app = Flask(__name__)
CORS(app)

DOWNLOAD_DIR = "/tmp"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

@app.route('/api/download', methods=['POST'])
def download():
    data = request.json
    url = data.get('url')
    fmt = data.get('format', 'mp3')

    if not url:
        return jsonify({"error": "Нет ссылки"}), 400

    uid = str(uuid.uuid4())[:8]
    out_template = os.path.join(DOWNLOAD_DIR, f"{uid}_%(title)s.%(ext)s")

    ydl_opts = {
        'outtmpl': out_template,
        'quiet': True,
        'no_warnings': True,
        'cookiefile': 'cookies.txt',
    }

    if fmt == 'mp3':
        ydl_opts['format'] = 'bestaudio/best'
        ydl_opts['postprocessors'] = [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }]
    else:
        ydl_opts['format'] = 'best[height<=720]/best'
        ydl_opts['merge_output_format'] = 'mp4'

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            base, _ = os.path.splitext(filename)
            filename = base + (".mp3" if fmt == 'mp3' else ".mp4")
        return jsonify({"success": True, "file": os.path.basename(filename)})
    except Exception as e:
        print(f"yt-dlp failed: {e}, trying pytubefix...")
        try:
            yt = YouTube(url)
            if fmt == 'mp3':
                stream = yt.streams.get_audio_only()
            else:
                stream = yt.streams.get_highest_resolution()
            
            out_name = f"{uid}_{yt.title}"
            out_path = stream.download(output_path=DOWNLOAD_DIR, filename=out_name)
            
            if fmt == 'mp3':
                final_path = os.path.splitext(out_path)[0] + ".mp3"
                subprocess.run(["ffmpeg", "-y", "-i", out_path, final_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                if os.path.exists(out_path):
                    os.remove(out_path)
                return jsonify({"success": True, "file": os.path.basename(final_path)})
            
            return jsonify({"success": True, "file": os.path.basename(out_path)})
        except Exception as e2:
            return jsonify({"error": f"Ошибка: {e} | Резерв: {e2}"}), 500

@app.route('/downloads/<filename>')
def serve_file(filename):
    return send_from_directory(DOWNLOAD_DIR, filename, as_attachment=True)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
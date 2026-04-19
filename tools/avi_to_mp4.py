import subprocess
import sys
import os

def convert_video(input_path):
    # Check if the input file exists
    if not os.path.exists(input_path):
        print(f"Error: File {input_path} not found.")
        return

    output_path = input_path.replace('.avi', '.mp4')
    
    # ffmpeg command for high compatibility MP4 (H.264)
    command = [
        'ffmpeg', '-i', input_path,
        '-vf','pad=ceil(iw/2)*2:ceil(ih/2)*2',  # Ensure dimensions are even
        '-c:v', 'libx264',
        '-crf', '23',
        '-pix_fmt', 'yuv420p',
        output_path, '-y'
    ]

    print(f"Converting: {input_path} to {output_path}...")
    
    try:
        subprocess.run(command, check=True)
        print(f"Success! File saved at: {output_path}")
    except Exception as e:
        print(f"Conversion failed: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 avi_to_mp4.py <path_to_video.avi>")
    else:
        convert_video(sys.argv[1])
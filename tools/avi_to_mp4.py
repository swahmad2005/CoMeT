import subprocess
import sys
import os

def convert_video(input_path):
    if not os.path.exists(input_path):
        print(f"Error: File {input_path} not found.")
        return

    # Define both output paths
    mp4_output = input_path.replace('.avi', '.mp4')
    gif_output = input_path.replace('.avi', '.gif')
    
    # Common video filter to fix odd-pixel dimensions 
    # Added 'fps=10' for the GIF to keep the file size small
    vf_settings = 'pad=ceil(iw/2)*2:ceil(ih/2)*2'

    # 1. MP4 Command
    mp4_command = [
        'ffmpeg', '-i', input_path,
        '-vf', vf_settings,
        '-c:v', 'libx264', '-crf', '23', '-pix_fmt', 'yuv420p',
        mp4_output, '-y'
    ]

    # 2. GIF Command (using Lanczos scaling for high quality)
    gif_command = [
        'ffmpeg', '-i', input_path,
        '-vf', f'{vf_settings},fps=10,scale=800:-1:flags=lanczos',
        gif_output, '-y'
    ]

    try:
        print(f" Processing: {input_path}...")
        
        # Run MP4 conversion
        subprocess.run(mp4_command, check=True)
        print(f" Success! MP4 saved: {mp4_output}")
        
        # Run GIF conversion
        subprocess.run(gif_command, check=True)
        print(f"Success! GIF saved: {gif_output}")
        
    except Exception as e:
        print(f"Conversion failed: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 avi_to_mp4.py <path_to_video.avi>")
    else:
        convert_video(sys.argv[1])
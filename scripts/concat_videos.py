""" SCRIPT CLI (Command Line Interface) """

#*******************************************************************************
# Imports:
#*******************************************************************************

from pathlib import Path
import os
import sys
import subprocess

import matplotlib.pyplot as plt
import IPython.display as ipd
import moviepy
from moviepy.editor import VideoFileClip, concatenate_videoclips

# There is a conflict between moviepy and the current version of PIL.
# !pip uninstall pillow
# !pip install pillow==9.5.0

import PIL

""" Check versions: """
print("moviepy version:", moviepy.__version__)
print("PIL version:", PIL.__version__)
print('\n')

#*******************************************************************************
# Constants/Atributes and Global Variables:
#*******************************************************************************

FORMATS = [".mp4", ".avi", ".mkv", ".mov"]

# type of video resolution:
LANDSCAPE_RESOLUTION = (1280, 720)
REEL_RESOLUTION = (720, 1280)
TARGET_RESOLUTION = REEL_RESOLUTION # Current working resolution.

# For clip lenght:
MIN_CLIP_LENGTH = 2
MAX_CLIP_LENGTH = 10
MAX_TOTAL_LENGTH = 60

#*******************************************************************************
# ImportantPaths:
#*******************************************************************************

PATH_BASE_DIR = Path(__file__).resolve().parent.parent # Path to the base directory of the project. 
# __file__: Path current file
# .resolve(): Converts the path to the absolute path.

PATH_VIDS = PATH_BASE_DIR / r"data/videos" # Relative path where the videos are stored.
PATH_CONCATS = PATH_BASE_DIR / r"data/concatenated" # Relative path where the concatenated videos are stored.

print(f'- Current working directory: {PATH_BASE_DIR}\n')
print(f"- Path Base Dir: {PATH_BASE_DIR}\n")
print(f"- Path Vids Dir: {PATH_VIDS}\n")
print(f"- Path Concats Dir: {PATH_CONCATS}\n")

#*******************************************************************************
# Functions:
#*******************************************************************************

""" This function checks which videos are available in the videos data folder. """
def available_vids(folder : Path) -> list:
    return [v for v in folder.iterdir() if v.is_file() and v.suffix in FORMATS]

#-------------------------------------------------------------------------------

""" This function returns a list of normalized clips. """
def load_and_normalize_vids(folder : Path, resolution : tuple) -> list:
    norm_clips = []
    target_width, target_height = resolution
    
    for vid in available_vids(folder):
        clip = VideoFileClip(str(vid))
        norm = clip.resize(newsize=(target_width, target_height))
        norm_clips.append(norm)
        
    print(f'Normalized clips: {len(norm_clips)}')
    print(f'Duration: {[c.duration for c in norm_clips]}')
    print('\n')
        
    return norm_clips

# NOTE: Clips remained open so they can be used in other functions. They should be closed later in the up coming functions. 

#-------------------------------------------------------------------------------

""" This function selects the clips that will be concatenated. Cut the long ones, drop the short ones, so the total duration does not exceed the given limit."""
def selected_by_duration(clips : list, max_total_length = MAX_TOTAL_LENGTH, 
                                       min_clip_length = MIN_CLIP_LENGTH, 
                                       max_clip_length = MAX_CLIP_LENGTH) -> list:
    selected = []
    total = 0.0
    
    for clip in clips:
        duration = clip.duration
        
        # Drop short clips:
        if duration < min_clip_length:
            continue
        
        # if it's too long, cut it:
        if duration > max_clip_length:
            cutted = clip.subclip(0, max_clip_length)
            duration = max_clip_length
        else:
            cutted = clip
        
        # If adding a clip exceeds the max total length, cut it:
        if total + duration > max_total_length:
            remaining = max_total_length - total
            
            # If the remaining part is not too short, cut this last video and add it:
            if remaining >= min_clip_length: 
                partial = clip.subclip(0, remaining)
                selected.append(partial)
                total += duration
            break
        else:
            selected.append(cutted)
            total += duration
    print(f'Selected clips: {len(selected)}')
    print(f'Total Duration: {total:.2f} seconds')
    print('\n')
    
    return selected

#-------------------------------------------------------------------------------

""" This function concatenates the selected clips and exports the resulting video to a given path. """
def concat_and_export(clips : list, export_path : Path, fps=30) -> None:
    try:
        if len(clips) == 0:
            raise ValueError("No clips selected.")
        
        final_clip = concatenate_videoclips(clips, method="compose")
        final_clip.write_videofile(str(export_path), 
                                fps=fps, 
                                codec="libx264", 
                                audio_codec="aac")
        final_clip.close()
    
    # Here is where the previously opened clips are closed, no matter if an error occurs or not:
    finally:   
        for c in clips:
            c.close()
            
#-------------------------------------------------------------------------------

""" This function wraps up the previous functions into one, to get the final result. """
def build_travel_summary(video_folder : Path,
                         export_path : Path,
                         target_resolution = TARGET_RESOLUTION,
                         max_total_length = MAX_TOTAL_LENGTH,
                         min_clip_length = MIN_CLIP_LENGTH,
                         max_clip_length = MAX_CLIP_LENGTH,
                         fps = 30) -> None:
    
    video_paths = available_vids(video_folder)
    if not video_paths:
        raise ValueError("No videos found in the given folder.")
    
    clips = load_and_normalize_vids(video_folder, target_resolution)
    selected = selected_by_duration(clips, max_total_length, min_clip_length, max_clip_length)
    
    concat_and_export(selected, export_path, fps)  

#-------------------------------------------------------------------------------

if __name__ == "__main__":
    # build_travel_summary(PATH_VIDS, PATH_CONCATS / "summary.mp4")
    pass
#*******************************************************************************
# MODULE WITH THE FUNCTIONS FOR VIDEO PROCESSING - PIPELINE - NON EXECUTABLE
#*******************************************************************************
""" 
This module contains the following functions:
- available_vids: checks which videos are available in the videos data folder.
- load_and_normalize_vids: returns a list of normalized clips.
- select_clips: selects the clips that will be concatenated.
- concatenate_clips: concatenates the selected clips and exports the resulting video to a given path.
- build_travel_summary: wraps up the previous functions into one, to get the final result.
"""

#*******************************************************************************
# Imports:
#*******************************************************************************

from pathlib import Path
from typing import Optional, List, Tuple, Dict # This is just for type hinting. Doesn't affect the code at all.

import numpy as np
import matplotlib.pyplot as plt
import IPython.display as ipd
import moviepy
from moviepy.editor import (VideoFileClip, 
                            concatenate_videoclips,
                            AudioFileClip,
                            CompositeAudioClip)
from moviepy.audio.fx import all as afx  # for audio_loop
from dataclasses import dataclass

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

def split_in_segments(clip: VideoFileClip, 
                      segment_length: float = 5.0) -> list[tuple[float, float]]:
    """Devuelve una lista de (t_start, t_end) para segmentos de duración fija."""
    segments = []
    t = 0.0
    while t < clip.duration:
        t_end = min(t + segment_length, clip.duration)
        # si el último segmento es muy chiquito, lo ignoramos
        if t_end - t >= 1.0:
            segments.append((t, t_end))
        t = t_end
    return segments

#-------------------------------------------------------------------------------

def motion_score_for_segment(clip: VideoFileClip, 
                             t_start: float, 
                             t_end: float, 
                             n_samples: int = 5) -> float:
    """
    Calcula un score de movimiento aproximado.
    Toma 'n_samples' frames entre t_start y t_end y mide cuánto cambian.
    """
    times = np.linspace(t_start, t_end, n_samples)
    prev_frame = None
    diffs = []
    for t in times:
        frame = clip.get_frame(t)  # shape (h, w, 3)
        gray = frame.mean(axis=2)  # pasamos a escala de grises promedio simple
        if prev_frame is not None:
            diff = np.mean(np.abs(gray - prev_frame))
            diffs.append(diff)
        prev_frame = gray
    if not diffs:
        return 0.0
    return float(np.mean(diffs))

#-------------------------------------------------------------------------------

def audio_energy_for_segment(clip: VideoFileClip, t_start: float, t_end: float) -> float:
    """
    Estima la energía del audio (RMS) en ese intervalo.
    Usa muestreo explícito en el tiempo para evitar el bug interno
    de MoviePy con iter_chunks.
    """
    if clip.audio is None:
        return 0.0

    try:
        audio_subclip = clip.audio.subclip(t_start, t_end)
        duration = audio_subclip.duration or (t_end - t_start)
        if duration <= 0:
            return 0.0
        
        # margen pequeño para no muestrear exactamente en el borde
        eps = 1e-3
        effective_duration = max(0.0, duration - eps)
        if effective_duration <= 0:
            return 0.0

        # Elegimos un número moderado de muestras (p.ej. 100 por segmento)
        num_samples = min(1000, int(duration * 1000))  # tope por seguridad
        if num_samples <= 0:
            return 0.0

        times = np.linspace(0, duration, num_samples, endpoint=False)

        # Forzamos a to_soundarray a muestrear en tiempos específicos,
        # evitando el uso de iter_chunks
        arr = audio_subclip.to_soundarray(tt=times, fps=22050)

        # Convertimos a mono si es estéreo
        if arr.ndim == 2:
            arr_mono = arr.mean(axis=1)
        else:
            arr_mono = arr

        rms = float(np.sqrt(np.mean(arr_mono ** 2)))
        return rms

    except Exception as e:
        print(f"[WARN] Error calculando energía de audio ({t_start}-{t_end}): {e}")
        return 0.0
    
#-------------------------------------------------------------------------------

def segment_score(clip: VideoFileClip, 
                  t_start: float, 
                  t_end: float,
                  w_motion: float = 0.3, 
                  w_audio: float = 0.7) -> float:
    
    m = motion_score_for_segment(clip, t_start, t_end)
    a = audio_energy_for_segment(clip, t_start, t_end)
    # podrías normalizar, pero de entrada probemos así
    return w_motion * m + w_audio * a

#-------------------------------------------------------------------------------

@dataclass
class Segment:
    clip: VideoFileClip
    t_start: float
    t_end: float
    score: float
    clip_index: int # For debugging, tracks which clip this segment comes from.

#-------------------------------------------------------------------------------

def extract_best_segment_per_clip(clips: list[VideoFileClip], 
                                  segment_length: float = 3.0) -> list[Segment]:
    """
    Para cada clip, divide en segmentos de duración fija y se queda SOLO
    con el segmento de mayor score. Devuelve una lista con a lo sumo un
    Segment por clip.
    """
    best_segments: list[Segment] = []

    for idx, clip in enumerate(clips):
        seg_times = split_in_segments(clip, segment_length)
        print(f"\nClip #{idx} - length {clip.duration:.2f}s, segments: {len(seg_times)}")

        best_seg = None
        best_score = float("-inf")

        for (ts, te) in seg_times:
            s = segment_score(clip, ts, te)
            print(f"  segment {ts:.2f}–{te:.2f}  score={s:.4f}")
            if s > best_score:
                best_score = s
                best_seg = Segment(
                    clip=clip,
                    t_start=ts,
                    t_end=te,
                    score=s,
                    clip_index=idx
                )

        if best_seg is not None:
            print(f"=> Best clip segment #{idx}: {best_seg.t_start:.2f}–{best_seg.t_end:.2f} (score={best_seg.score:.4f})")
            best_segments.append(best_seg)

    return best_segments

#-------------------------------------------------------------------------------

def arrange_best_segments(segments: list[Segment],
                         max_total_duration: float = 60.0, 
                         min_segment_duration: float = 1.5) -> list[VideoFileClip]:
    """
    Recibe una lista de Segment donde ya hay como máximo uno por clip.
    Toma los segmentos en el orden dado (por defecto el de los videos)
    hasta alcanzar max_total_duration.
    """
    selected_clips: list[VideoFileClip] = []
    total = 0.0

    for seg in segments:
        dur = seg.t_end - seg.t_start
        if dur < min_segment_duration:
            continue

        if total + dur > max_total_duration:
            remaining = max_total_duration - total
            if remaining >= min_segment_duration:
                sub = seg.clip.subclip(seg.t_start, seg.t_start + remaining)
                selected_clips.append(sub)
                total += remaining
            break
        else:
            sub = seg.clip.subclip(seg.t_start, seg.t_end)
            selected_clips.append(sub)
            total += dur

    print (f'Selected clips: {len(selected_clips)}')
    print(f"Total length (smart): {total:.2f} s")
    return selected_clips


#-------------------------------------------------------------------------------

""" This function concatenates the selected clips and exports the resulting video to a given path. """
def concat_and_export(clips : list, 
                      export_path : Path, 
                      fps=30, bg_music_path: Path | None = None,
                      original_vol: float = 0.3,
                      music_vol: float = 1.0) -> None:
    
    music_clip, music_loop, mixed_audio = None, None, None
    
    try:
        if len(clips) == 0:
            raise ValueError("No clips selected.")
        
        final_clip = concatenate_videoclips(clips, method="compose")
        
        # Add background audio -------------------------------------------------
        if bg_music_path is not None and bg_music_path.exists():
            print(f"Background music: {bg_music_path.name}")
            
            duration = final_clip.duration    # Length final concat vid.
            original_audio = final_clip.audio # Original audio whole concat vid.
            if original_audio is not None:
                original_audio = original_audio.volumex(original_vol)
            
            # load song
            music_clip = AudioFileClip(str(bg_music_path))
        
            # Loop song if it is shorter than the video
            music_loop = afx.audio_loop(music_clip, duration=duration)
            music_loop = music_loop.volumex(music_vol)
            
            # combinar audios
            if original_audio is not None:
                mixed_audio = CompositeAudioClip([original_audio, music_loop])
            else:
                mixed_audio = music_loop

            final_clip = final_clip.set_audio(mixed_audio)
            
        else:
            print("No background music.")
        #-----------------------------------------------------------------------
        
        final_clip.write_videofile(str(export_path), 
                                fps=fps, 
                                codec="libx264", 
                                audio_codec="aac")
        final_clip.close()
    
    # Here is where the previously opened clips and audio files are closed, no matter if an error occurs or not:
    finally:   
        for c in clips:
            c.close()
            
        for au in (mixed_audio, music_loop, music_clip):
            if au is not None:
                au.close()
            
#-------------------------------------------------------------------------------

""" This function wraps up the previous functions into one, to get the final result. """
def build_travel_summary_smart(video_dir: Path,
                               output_path: Path, 
                               target_resolution=(720, 1280), 
                               segment_length: float = 6.0 , 
                               max_total_duration: float = 85.0,
                               bg_music_path: Path | None = None,
                               fps: int = 30) -> None:
    
    video_paths = available_vids(video_dir)
    if not video_paths:
        raise ValueError(f"No videos found in {video_dir}")
    
    clips = load_and_normalize_vids(video_dir, target_resolution)
    
    segments = extract_best_segment_per_clip(clips, segment_length=segment_length)
    
    selected_clips = arrange_best_segments(segments,
                                           max_total_duration=max_total_duration)

    concat_and_export(selected_clips, 
                      output_path, 
                      fps=fps, 
                      bg_music_path=bg_music_path) 
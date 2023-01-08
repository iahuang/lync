import sys
import json
import moviepy.editor as mp

TARGET_SONG = "Lil Keed - Snake"

IMG_PATH = "./cli-test/"+ TARGET_SONG+".jpg"
TRANSCRIPT_PATH = "./cli-test/"+TARGET_SONG+"-transcript.json"
AUDIO_PATH = "./cli-test/"+TARGET_SONG+".mp3"

audio_clip = mp.AudioFileClip(AUDIO_PATH)
# create the image clip object
image_clip = mp.ImageClip(IMG_PATH).set_duration(audio_clip.duration)
# use set_audio method from image clip to combine the audio with the image
video_clip = image_clip.set_audio(audio_clip)
# specify the duration of the new clip to be the duration of the audio clip
video_clip.duration = audio_clip.duration
w,h = moviesize = video_clip.size

transcript_file = open(TRANSCRIPT_PATH, "r")
transcript = json.load(transcript_file)
txt_clips = []
for segment in transcript['fragments']:
    text = segment['lines'][0]
    #break up long lines so they fit on the screen
    if len(text.split(" "))>6:
        text = text.split(" ")
        text.insert(6, "\n")
        text = " ".join(text)
        
    start = float(segment['begin'])
    end = float(segment['end'])
    txt_duration = end-start
    
    txt_clip = mp.TextClip(text, font = "Arial", color = "yellow", stroke_color='black', stroke_width=2, fontsize=40, align='center')
    txt_clip = txt_clip.set_start(start)# anticipate by 2 seconds
    txt_clip = txt_clip.set_pos( lambda t: (max(w/30,int(w-0.5*w*t)),max(5*h/6,int(100*t)))).set_duration(txt_duration)
    
    txt_clips.append(txt_clip)

print("Finished pre-rendered text clips")

final_video = mp.CompositeVideoClip([video_clip]+[clip for clip in txt_clips])
final_video.set_duration(audio_clip.duration)
final_video.write_videofile(TARGET_SONG+"-karaoke.mp4",fps=24)

transcript_file.close()
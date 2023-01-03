import os
import urllib
# external deps
from spleeter.separator import Separator
from aeneas.tools.execute_task import ExecuteTaskCLI
# lync
from lync.external.genius import Genius
from lync.external.soundcloud import Soundcloud


SONG_TARGET = "Lil Keed - Snake"
OUTDIR = "./cli-test/"
CACHE_FOREVER = -1
g = Genius(CACHE_FOREVER)
genius_result = g.search(SONG_TARGET)
assert genius_result is not None
# download lyrics
with open(OUTDIR+SONG_TARGET+".txt", "w") as f:
    for line in g.get_lyrics(genius_result).lines:
        print(line.text, file=f)
# download cover art
url=genius_result.song_image_url
img_type = "."+url.split('.')[-1]
req = urllib.request.Request(
    url,
    data = None,
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/35.0.1916.47 Safari/537.36'
    }
)
raw_img = urllib.request.urlopen(req).read()
lyric_path = OUTDIR+SONG_TARGET+img_type
with open(lyric_path, 'wb') as f:
    f.write(raw_img)
print(f"Found lyrics and cover art for {genius_result.title} by {genius_result.artist_name}\n")

soundcloud = Soundcloud()
soundcloud_result = soundcloud.search(SONG_TARGET)
assert soundcloud_result is not None

transcoding = soundcloud_result.get_transcoding("audio/mpeg")
assert transcoding is not None
audio_path = OUTDIR+SONG_TARGET+".mp3"
soundcloud.download_audio(transcoding, audio_path)

# split up audio into vocals and accompinament
separator = Separator('spleeter:2stems')
separator.separate_to_file(audio_path, OUTDIR)

test_audio_path = os.path.realpath(OUTDIR+"vocals.wav")
test_transcript_path = os.path.realpath(lyric_path)

ExecuteTaskCLI(use_sys=False).run(arguments=[
    None, # dummy program name argument
    test_audio_path,
    test_transcript_path,
    u"task_language=eng|is_text_type=plain|os_task_file_format=json",
    os.path.realpath(OUTDIR+SONG_TARGET+"-transcript.json")
    ])
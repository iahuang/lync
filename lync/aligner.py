from dataclasses import dataclass
import json
import math
import sys

import torch
import torchaudio

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")


def get_trellis(emission, tokens, blank_id=0):
        num_frame = emission.size(0)
        num_tokens = len(tokens)

        # Trellis has extra diemsions for both time axis and tokens.
        # The extra dim for tokens represents <SoS> (start-of-sentence)
        # The extra dim for time axis is for simplification of the code.
        trellis = torch.empty((num_frame + 1, num_tokens + 1))
        trellis[0, 0] = 0
        trellis[1:, 0] = torch.cumsum(emission[:, 0], 0)
        trellis[0, -num_tokens:] = -float("inf")
        trellis[-num_tokens:, 0] = float("inf")

        for t in range(num_frame):
            trellis[t + 1, 1:] = torch.maximum(
                # Score for staying at the same token
                trellis[t, 1:] + emission[t, blank_id],
                # Score for changing to the next token
                trellis[t, :-1] + emission[t, tokens],
            )
        return trellis

@dataclass
class Point:
    token_index: int
    time_index: int
    score: float

def backtrack(trellis, emission, tokens, blank_id=0):
    # Note:
    # j and t are indices for trellis, which has extra dimensions
    # for time and tokens at the beginning.
    # When referring to time frame index `T` in trellis,
    # the corresponding index in emission is `T-1`.
    # Similarly, when referring to token index `J` in trellis,
    # the corresponding index in transcript is `J-1`.
    j = trellis.size(1) - 1
    t_start = torch.argmax(trellis[:, j]).item()

    path = []
    for t in range(t_start, 0, -1):
        # 1. Figure out if the current position was stay or change
        # Note (again):
        # `emission[J-1]` is the emission at time frame `J` of trellis dimension.
        # Score for token staying the same from time frame J-1 to T.
        stayed = trellis[t - 1, j] + emission[t - 1, blank_id]
        # Score for token changing from C-1 at T-1 to J at T.
        changed = trellis[t - 1, j - 1] + emission[t - 1, tokens[j - 1]]

        # 2. Store the path with frame-wise probability.
        prob = emission[t - 1, tokens[j - 1] if changed > stayed else 0].exp().item()
        # Return token index and time index in non-trellis coordinate.
        path.append(Point(j - 1, t - 1, prob))

        # 3. Update the token
        if changed > stayed:
            j -= 1
            if j == 0:
                break
    else:
        raise ValueError("Failed to align")
    return path[::-1]

@dataclass
class Segment:
    label: str
    start: int
    end: int
    score: float

    def __repr__(self):
        return f"{self.label}\t({self.score:4.2f}): [{self.start:5d}, {self.end:5d})"

    @property
    def length(self):
        return self.end - self.start

def merge_repeats(trellis_path, transcript):
    i1, i2 = 0, 0
    segments = []
    while i1 < len(trellis_path):
        while i2 < len(trellis_path) and trellis_path[i1].token_index == trellis_path[i2].token_index:
            i2 += 1
        score = sum(trellis_path[k].score for k in range(i1, i2)) / (i2 - i1)
        segments.append(
            Segment(
                transcript[trellis_path[i1].token_index],
                trellis_path[i1].time_index,
                trellis_path[i2 - 1].time_index + 1,
                score,
            )
        )
        i1 = i2
    return segments

def merge_words(segments, separator="|"):
    words = []
    i1, i2 = 0, 0
    while i1 < len(segments):
        if i2 >= len(segments) or segments[i2].label == separator:
            if i1 != i2:
                segs = segments[i1:i2]
                word = "".join([seg.label for seg in segs])
                score = sum(seg.score * seg.length for seg in segs) / sum(seg.length for seg in segs)
                words.append(Segment(word, segments[i1].start, segments[i2 - 1].end, score))
            i1 = i2 + 1
            i2 = i1
        else:
            i2 += 1
    return words
    
@dataclass
class TranscriptLine:
    phrase: str
    start_time_s: float
    end_time_s: float

    def __repr__(self):
        return f"{self.phrase}\t({self.start_time_s}, {self.end_time_s})"
    
    @property
    def duration(self):
        return self.end_time_s - self.start_time_s

def merge_lines(word_segs, lyric_lines, waveform_len = w_len, srate = 44100):
    num_frames = word_segs[-1].end

    line_segments = []
    print(lyric_lines[-1])
    transcript_word_idx = 0
    for line in lyric_lines:
        if line == "":
            continue

        line_segment = TranscriptLine(line, word_segs[transcript_word_idx].start / num_frames * waveform_len / srate, -1)
        line_cleaned = line.strip().upper()
        line_cleaned = ''.join(filter(lambda chr: chr.isalpha() or chr == " ", line_cleaned)).split()

        for word in line_cleaned:
            line_segment.end_time_s = word_segs[transcript_word_idx].end / num_frames * waveform_len / srate
            transcript_word_idx+=1
    
        line_segments.append(line_segment)

    return line_segments

def export_transcript(merged_lines, outfile):
    script = {}
    script['fragments'] = []
    l_id = 0
    for line in merged_lines:
        fragment = {}
        fragment['lines'] = [line.phrase]
        fragment['begin'] = line.start_time_s
        fragment['end'] = line.end_time_s
        fragment['language'] = 'eng'
        fragment['children'] = []
        fragment['id'] = l_id
        l_id+=1
        script['fragments'].append(fragment)
    
    json.dump(script, outfile)

CHUNKS = 6
def align(vocal_path, lyrics_path, outfile_path):
    # prep lyrics
    lyrics_file = open(lyrics_path, 'r')
    transcript  = lyrics_file.read()
    transcript_lines = transcript.split("\n")
    transcript_cleaned = transcript.strip().replace("\n", " ").upper()
    transcript_cleaned = ''.join(filter(lambda chr: chr.isalpha() or chr == " ", transcript_cleaned)).replace(" ", "|")

    #load model
    bundle = torchaudio.pipelines.WAV2VEC2_ASR_BASE_960H
    model = bundle.get_model().to(DEVICE)
    labels = bundle.get_labels()

    # load audio
    waveform, srate = torchaudio.load(vocal_path)
    w_len = waveform.shape[1]
    chunk_len = int(math.ceil(w_len/CHUNKS))
    waveforms = [waveform[0, i:min(w_len,i+chunk_len)].unsqueeze(0) for i in range(CHUNKS)]
    
    emissions_list = []
    with torch.inference_mode():
        for i in range(CHUNKS):
            emission, _ = model(waveforms[i].to(device))
            emissions_list.append(torch.log_softmax(emission, dim=-1))
    
    emissions = torch.cat(emissions_list, 0)
    emission = emissions[0].cpu().detach()
    
    dictionary = {c: i for i, c in enumerate(labels)}
    tokens = [dictionary[c] for c in transcript_cleaned]

    trellis = get_trellis(emission, tokens) 
    path = backtrack(trellis, emission, tokens)

    segments = merge_repeats(path)
    word_segments = merge_words(segments)
    merged_lines = merge_lines(word_segments, transcript_lines)

    with open(outfile_path, 'w') as f:
        export_transcript(merged_lines, f)

if __name__ == "__main__":
    audiopath = sys.argv[1]
    if audiopath == '-h':
        print("syntax: path/to/vocal.wav path/to/transcript.txt output/path.json")
    lyricpath = sys.argv[2]
    outpath = sys.arv[3]

    align(audiopath, lyricpath, outpath)
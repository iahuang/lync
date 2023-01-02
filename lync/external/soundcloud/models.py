from dataclasses import dataclass
from typing import Optional

@dataclass(frozen=True)
class MediaTranscoding:
    url: str
    preset: str
    duration: int
    mime: str
    protocol: str

@dataclass(frozen=True)
class SoundCloudSearchResult:
    title: str
    artist_name: str
    stream_transcodings: list[MediaTranscoding]
    song_image_url: str

    def get_transcoding(self, mime_type: str) -> Optional[MediaTranscoding]:
        """
        Get transcoding by MIME type. If no such transcoding exists, return `None`.
        """

        for transcoding in self.stream_transcodings:
            if transcoding.mime.startswith(mime_type):
                return transcoding

        return None

@dataclass(frozen=True)
class Audio:
    transcoding: MediaTranscoding
    data: bytes
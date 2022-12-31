from dataclasses import dataclass

@dataclass
class SongSearchResult:
    title: str
    artist_name: str
    link: str
    song_image_url: str
from dataclasses import dataclass
import re

@dataclass
class GeniusSearchResult:
    title: str
    artist_name: str
    lyrics_url: str
    song_image_url: str

@dataclass(frozen=True)
class Section:
    section_text: str
    section_index: int

@dataclass(frozen=True)
class Line:
    text: str
    section_index: int
    """
    Will be `-1` if this line doesn't belong to a specific section.
    """

    def text_adlibs_removed(self) -> str:
        """
        Return this line's text, attempting to remove adlibs (defined as any trailing phrase
        enclosed in parentheses)
        """

        ADLIB_PATTERN = r' \(.+\)$'

        return re.sub(ADLIB_PATTERN, "", self.text)

@dataclass(frozen=True)
class Lyrics:
    sections: list[Section]
    lines: list[Line]
    
    def has_sections(self) -> bool:
        return len(self.sections) > 0


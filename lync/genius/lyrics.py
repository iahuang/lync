import re
import requests
import json
from ast import literal_eval
from typing import Optional, Union
from .data_types import SongResult, Lyrics, Section, Line
from .exceptions import LyricsFetchError


def fetch_lyrics(song: SongResult, session: requests.Session) -> Lyrics:
    """
    Fetch the lyrics corresponding to the given Genius search result.
    """

    url = song.lyrics_url

    response = session.get(url)

    # validate status and response type of request

    if not response.ok:
        LyricsFetchError(f"HTTP request failed; {response.status_code}")

    response_type = response.headers.get("content-type")

    if not response_type or "text/html" not in response_type:
        raise LyricsFetchError("Invalid response type; expected HTML")

    # extract, parse, and transform data

    lyrics_data = extract_lyrics_data(response.text)

    if not lyrics_data:
        raise LyricsFetchError("Embedded lyric data not found")

    return reformat_lyrics_data(lyrics_data)


def extract_lyrics_data(html_content: str) -> Optional[dict]:
    """
    The HTML source of a song lyrics page contains embedded JSON data that describes the
    content of the page, including the page's lyrics. Extract and return all parsed
    JSON data from the page.
    """

    DATA_REGEX_PATTERN = r"(?<=window\.__PRELOADED_STATE__ = JSON\.parse\()(['\"])(.|\n)+?\1(?=\))"

    match = re.search(DATA_REGEX_PATTERN, html_content)

    if match is None:
        return None

    # unescape dollar signs, as they produce invalid JSON
    json_string = literal_eval(match.group()).replace("\\$", "$")
    json_data = json.loads(json_string)

    return json_data


def reformat_lyrics_data(lyrics_data: dict) -> Lyrics:
    """
    Transform the raw output of the `extract_lyrics_data` function into a better structured
    object.
    """

    if not isinstance(lyrics_data, dict):
        raise LyricsFetchError()

    children = lyrics_data["songPage"]["lyricsData"]["body"]["children"][0]
    sections: list[Section] = []

    def inner_text(child: Union[dict, str]) -> str:
        """
        `children` is a list of nodes, where each node is either
        an object of the form
        ```
        Node {
            tag: string;
            children: Node[];
        }
        ```
        or a string representing encapsulated text.

        Return the entire encapsulated text of a node, concatenating the text of child nodes.
        - Nodes with tag `"br"` will be represented as a newline character.
        - Nodes with no `children` property will be represented as an empty string.  
        """

        if isinstance(child, str):
            return child
        
        if child.get("tag") == "br":
            return "\n"
        
        if not child.get("children"):
            return ""

        return "".join(inner_text(child_child) for child_child in child["children"])

    lines: list[Line] = []

    for line in inner_text(children).split("\n"):
        if section_match := re.search(r"(?<=\[).+(?=\])", line):
            # match a section header like "[Chorus: Travis Scott]"

            section_text = section_match[0]

            sections.append(Section(section_text, len(sections)))
        elif line != "":
            # assume current child represents a line

            # will be -1 if this line doesn't belong to a section; this is intended.
            current_section_index = len(sections) - 1
            line = Line(line, current_section_index)

            lines.append(line)

    return Lyrics(sections, lines)

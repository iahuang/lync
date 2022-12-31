import requests
import re
from .exceptions import SoundcloudClientIDException


def obtain_client_id(session: requests.Session) -> str:
    """
    Query the Soundcloud homepage and return a client ID.

    Soundcloud's internal API uses a client ID obtained as a hardcoded value in the bundled
    js files included in every page.
    """

    URL = "https://soundcloud.com/discover"

    # regex patterns

    SCRIPT_PATTERN = r"<script .+?>"
    SRC_PATTERN = r"(?<=src=\").+?(?=\")"
    CLIENT_ID_PATTERN = r"(?<=client_id:\").+?(?=\")"

    response = session.get(URL)

    if not response.ok:
        raise SoundcloudClientIDException("Failed to obtain client ID")

    html_content = response.text
    script_elements = re.findall(SCRIPT_PATTERN, html_content)
    script_sources_match = (re.search(SRC_PATTERN, element) for element in script_elements)
    script_sources = [match.group() for match in script_sources_match if match is not None]

    for referenced_script in script_sources:
        response = session.get(referenced_script)

        if not response.ok: continue

        js_source = response.text

        if match := re.search(CLIENT_ID_PATTERN, js_source):
            return match.group()
    
    raise SoundcloudClientIDException("Failed to obtain client ID")
            
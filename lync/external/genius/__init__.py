from typing import Any, Optional
import requests
import math
from requests_cache import CachedSession
from requests_cache.backends.filesystem import FileCache
from ..api import APIInterface, APIResponse, APIErrorData, APIErrorCode
from .models import Lyrics, GeniusSearchResult
from .lyrics import fetch_lyrics
from .exceptions import GeniusAPIError

GENIUS_API_ROOT = "https://genius.com/api"
ACHE_FOREVER = math.inf

class GeniusInterface(APIInterface):
    def _build_response(self, request_response: requests.Response) -> APIResponse:
        try:
            data = request_response.json()

            meta = data["meta"]

            if meta["status"] != 200:
                return APIResponse.Error(
                    APIErrorData(APIErrorCode.MalformedResponse, meta.get("message"))
                )

            return APIResponse.Success(data.get("response"))

        except requests.exceptions.JSONDecodeError:
            return APIResponse.Error(
                APIErrorData(APIErrorCode.MalformedResponse, request_response.content)
            )
        except KeyError:
            # In case of missing fields that were expected in the response, such as "meta"

            return APIResponse.Error(
                APIErrorData(APIErrorCode.MalformedResponse, request_response.content)
            )


def associate_array(data: list[dict], key_name: str, allow_duplicates=False) -> dict[str, Any]:
    """
    Given an array of the form
    ```
    data = [
        { K: "a", ... },
        { K: "b", ... },
        { K: "c", ... },
        { K: "d", ... },
    ]
    ```
    `associate_array(data, K)` returns
    ```
    {
        "a": { K: "a", ... },
        "b": { K: "b", ... },
        "c": { K: "c", ... }
        "d": { K: "d", ... }
    }
    ```
    if `allow_duplicates` is false, then raise an error if more than one instance of the same
    key name is found.
    """

    out: dict[str, Any] = {}

    for item in data:
        key = item[key_name]

        if key in out and not allow_duplicates:
            raise ValueError(f'Duplicate key "{key}"')

        out[key] = item

    return out


class Genius:
    """
    API Wrapper for the internal Genius API (http://genius.com/api)
    """

    _api: GeniusInterface
    _session: requests.Session

    def __init__(self, cache_age_seconds: float) -> None:
        """
        If `cache_age_seconds` is `0` or a negative number, caching is disabled. If set to
        `CACHE_FOREVER`, then the cache will never expire.
        """

        if cache_age_seconds:
            # for `CachedSession`, an expiry of -1 indicates "forever".
            if math.isinf(cache_age_seconds): cache_age_seconds = -1

            self._session = CachedSession(
                "api_cache",
                backend=FileCache(cache_name="./.cache"),
                expire_after=cache_age_seconds,
            )
        else:
            self._session = requests.Session()

        self._api = GeniusInterface(GENIUS_API_ROOT, self._session)

    def _assert_ok(self, response: APIResponse) -> None:
        """
        Assert that a given `APIResponse` object was successful, raising an error with an
        appropriate message otherwise.
        """

        if not response.ok():
            raise GeniusAPIError(f"API call failed; error: " + response.get_error().data)

    def search(self, query: str) -> Optional[GeniusSearchResult]:
        """
        Search Genius for the song provided by `query`. Return the result with most page views.

        Examples:
        - `search("drake - one dance")`
        - `search("starboy")`
        - `search("goosebumps travis scott")`
        """

        response = self._api.get("/search/multi", {"per_page": 4, "q": query})
        self._assert_ok(response)

        data = response.get_data()
        sections = associate_array(data["sections"], "type")

        song = sections.get("song")

        if not song or not song["hits"]:
            return None

        hits = song["hits"]

        # return result with most pageviews
        get_pageviews = lambda hit: hit["result"]["stats"].get("pageviews", 0)
        song_result = max(hits, key=get_pageviews)["result"]

        return GeniusSearchResult(
            title=song_result["title"],
            artist_name=song_result["artist_names"],
            lyrics_url=song_result["url"],
            song_image_url=song_result["song_art_image_url"]
        )

    def get_lyrics(self, song: GeniusSearchResult) -> Lyrics:
        """
        Extract the lyric data from the page referenced by the provided search result `song`.
        """

        return fetch_lyrics(song, session=self._session)

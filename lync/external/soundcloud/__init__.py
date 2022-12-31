from typing import Optional
import requests
import math
from requests_cache import CachedSession
from requests_cache.backends.filesystem import FileCache
from .client_id import obtain_client_id
from .exceptions import SoundcloudSearchException
from ..api import APIInterface, APIResponse, APIErrorData, APIErrorCode
from ..models import SongSearchResult

SOUNDCLOUD_API_ROOT = "https://api-v2.soundcloud.com"


class SoundcloudInterface(APIInterface):
    def _build_response(self, request_response: requests.Response) -> APIResponse:
        try:
            data = request_response.json()

            return APIResponse.Success(data)

        except requests.exceptions.JSONDecodeError:
            return APIResponse.Error(
                APIErrorData(APIErrorCode.MalformedResponse, request_response.content)
            )


class Soundcloud:
    """
    API Wrapper for the internal Soundcloud API
    """

    _api: SoundcloudInterface
    _session: requests.Session
    _client_id: str

    def __init__(self, cache_age_seconds: float) -> None:
        """
        If `cache_age_seconds` is `0` or a negative number, caching is disabled. If set to
        `CACHE_FOREVER`, then the cache will never expire.
        """

        if cache_age_seconds:
            # for `CachedSession`, an expiry of -1 indicates "forever".
            if math.isinf(cache_age_seconds):
                cache_age_seconds = -1

            self._session = CachedSession(
                "api_cache",
                backend=FileCache(cache_name="./.cache"),
                expire_after=cache_age_seconds,
            )
        else:
            self._session = requests.Session()

        self._api = SoundcloudInterface(SOUNDCLOUD_API_ROOT, self._session)
        self._client_id = obtain_client_id(self._session)

    def _assert_ok(self, response: APIResponse) -> None:
        """
        Assert that a given `APIResponse` object was successful, raising an error with an
        appropriate message otherwise.
        """

        if not response.ok():
            raise SoundcloudSearchException(f"API call failed; error: " + response.get_error().data)

    def search(self, query: str) -> Optional[SongSearchResult]:
        response = self._api.get(
            "/search", {"q": query, "facet": "model", "client_id": self._client_id}
        )
        self._assert_ok(response)

        results: list = response.get_data()["collection"]
        # filter non-tracks
        results = [item for item in results if item["kind"] == "track"]

        if not results:
            return None

        # get top result
        result = results[0]

        # get stream URL as rearch result link
        stream_transcodings = result["media"]["transcodings"]

        if not stream_transcodings:
            return None

        return SongSearchResult(
            title=result["title"],
            artist_name=result["publisher_metadata"]["artist"],
            link=stream_transcodings[0]["url"],
            song_image_url=result["artwork_url"],
        )

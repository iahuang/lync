from typing import Optional
from os import urandom, mkdir, remove
from os.path import join, exists
import requests
from pydub import AudioSegment
from .client_id import obtain_client_id
from .exceptions import SoundcloudSearchException, SoundcloudAudioDLException
from ..api import APIInterface, APIResponse, APIErrorData, APIErrorCode
from .models import SoundCloudSearchResult, MediaTranscoding, Audio

SOUNDCLOUD_API_ROOT = "https://api-v2.soundcloud.com"
UA = "ozilla/5.0 (Macintosh; Intel Mac OS X 10_8_2) AppleWebKit/537.17 (KHTML, like Gecko) Chrome/24.0.1309.0 Safari/537.17"


def random_id() -> int:
    """
    Return a cyptographically secure uint32 value.
    """

    return int.from_bytes(urandom(4), byteorder="big", signed=False)


class SoundcloudInterface(APIInterface):
    def _build_response(self, request_response: requests.Response) -> APIResponse:
        try:
            data = request_response.json()

            return APIResponse.Success(data)

        except requests.exceptions.JSONDecodeError:
            return APIResponse.Error(
                APIErrorData(APIErrorCode.MalformedResponse, request_response.content)
            )

    def _build_headers(self) -> dict[str, str]:
        headers = super()._build_headers()
        headers["User-Agent"] = UA

        return headers


class Soundcloud:
    """
    API Wrapper for the internal Soundcloud API
    """

    _api: SoundcloudInterface
    _session: requests.Session
    _client_id: str

    def __init__(self) -> None:
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

    def search(self, query: str) -> Optional[SoundCloudSearchResult]:
        response = self._api.get(
            "/search", {"q": query, "facet": "model", "client_id": self._client_id}
        )
        self._assert_ok(response)
        data = response.get_data()

        results: list = data["collection"]
        # filter non-tracks
        results = [item for item in results if item["kind"] == "track"]

        if not results:
            return None

        # get top result
        result = results[0]

        media_transcoding_objects = result["media"]["transcodings"]
        if not media_transcoding_objects:
            return None

        media_transcodings = [
            MediaTranscoding(
                url=transcoding["url"],
                preset=transcoding["preset"],
                duration=transcoding["duration"],
                protocol=transcoding["format"]["protocol"],
                mime=transcoding["format"]["mime_type"],
            )
            for transcoding in media_transcoding_objects
        ]

        return SoundCloudSearchResult(
            title=result["title"],
            artist_name=result["publisher_metadata"]["artist"],
            song_image_url=result["artwork_url"],
            stream_transcodings=media_transcodings,
        )

    def _fetch_playlist_entries(self, transcoding: MediaTranscoding) -> list[str]:
        """
        Return a list of audio URLs representing the playlist file at the URL in the provided
        transcoding.
        """

        response = self._session.get(
            transcoding.url, params={"client_id": self._client_id, "User-Agent": UA}
        )
        if not response.ok:
            raise SoundcloudAudioDLException(
                "Transcoding request failed: " + str(response.status_code) + ": " + str(response.content)
            )
        media_url = response.json()["url"]

        # download and parse m3u8 playlist file
        playlist_data = self._session.get(media_url).text
        lines = playlist_data.split("\n")
        return [line for line in lines if line.startswith("http")]  # return lines resembling URLs

    def _download_playlist(self, transcoding: MediaTranscoding, output_dir: str) -> list[str]:
        """
        Download audio files in the playlist provided by `transcoding`, returning corresponding
        file paths to downloaded audio files in the same order as the playlist.
        """

        output_filenames: list[str] = []

        if not exists(output_dir):
            mkdir(output_dir)

        for url in self._fetch_playlist_entries(transcoding):
            response = self._session.get(url)

            if not response.ok:
                raise SoundcloudAudioDLException(f"Failed to download audio file at {url}")

            identifier = random_id()
            filename = join(output_dir, str(identifier) + ".audio")  # use generic file extension
            output_filenames.append(filename)

            with open(filename, "wb") as fl:
                fl.write(response.content)

        return output_filenames

    def download_audio(self, transcoding: MediaTranscoding, output: str) -> None:
        """
        Download audio for a transcoding, writing an output audio file `output`.
        """

        audio_files = self._download_playlist(transcoding, "./.tmp")
        audio_segments: list[AudioSegment] = [AudioSegment.from_file(f) for f in audio_files]

        combined = AudioSegment.empty()

        for audio_segment in audio_segments:
            combined += audio_segment

        combined.export(output, format="mp3")

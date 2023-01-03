from __future__ import annotations
import requests
import math
from typing import Any, TypeVar, Generic, Optional
from dataclasses import dataclass
from enum import Enum


def url_join(base: str, *components: str) -> str:
    """
    Example:
    ```
    >>> url_join("http://example.com/", "api", "/v3/test")
    'http://example.com/api/v3/test'
    ```
    """

    return base.rstrip("/") + "/" + "/".join(c.strip("/") for c in components)


class APIErrorCode(Enum):
    MalformedRequest = "malformed_request"
    MalformedResponse = "malformed_response"
    RateLimited = "rate_limited"
    PermissionDenied = "permission_denied"
    Unknown = "unknown"


@dataclass
class APIErrorData:
    code: APIErrorCode
    data: Any = None


T = TypeVar("T")


class APIResponse(Generic[T]):
    """
    Object representing an API response.
    """

    _data: Optional[T]
    _ok: bool
    _error: Optional[APIErrorData]

    def __init__(self, ok: bool, data: Optional[T], error: Optional[APIErrorData]) -> None:
        """
        This constructor not to be used directly.
        """

        self._data = data
        self._ok = ok
        self._error = error

    def get_data(self) -> T:
        """
        Return the data contained within the API response only if the request was successful.
        Raise an error if the request failed.
        """

        if not self._ok:
            raise ValueError("Response to failed API request has no response data")

        return self._data  # type: ignore

    def ok(self) -> bool:
        """
        Return `True` iff. the response was successful.
        """

        return self._ok

    def get_error(self) -> APIErrorData:
        """
        Return the error data contained within the API response only if the request failed.
        Raise an error if the request succeeded.
        """

        if self._ok:
            raise ValueError("Response to successful API request has no error data")
        return self._error  # type: ignore

    @staticmethod
    def Success(data: T) -> APIResponse[T]:
        """
        Construct an `APIResponse` object representing the response of a successful request.
        """

        return APIResponse(True, data, None)

    @staticmethod
    def Error(error: APIErrorData) -> APIResponse[T]:
        """
        Construct an `APIResponse` object representing the response of a failed request.
        """

        return APIResponse(False, None, error)


class APIInterface:
    """
    Represents a generic API wrapper
    """

    _api_root: str
    _session: requests.Session

    def __init__(self, api_root: str, session: requests.Session) -> None:
        self._api_root = api_root
        self._session = session

    def get_api_root(self) -> str:
        return self._api_root

    def get(self, endpoint: str, query_params: dict[str, Any] = {}) -> APIResponse:

        url = url_join(self._api_root, endpoint)

        return self._build_response(
            self._session.get(url, headers=self._build_headers(), params=query_params)
        )

    def post(self, endpoint: str, body: Optional[str] = None) -> APIResponse:
        url = url_join(self._api_root, endpoint)

        return self._build_response(
            self._session.post(url, headers=self._build_headers(), data=body)
        )

    def _build_headers(self) -> dict[str, str]:
        """
        Overridable method implementing construction of a header object that should be
        included in every request. This is for inclusion of parameters such as
        authorization tokens and/or API keys.
        """

        return {"Accept": "application/json"}

    def _build_response(self, request_response: requests.Response) -> APIResponse:
        """
        Abstract method that should appropriately construct an `APIResponse` object from a
        `requests.Response` object.
        """

        raise NotImplementedError()


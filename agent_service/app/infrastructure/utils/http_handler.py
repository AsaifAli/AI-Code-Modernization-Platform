import requests
from typing import Any, Dict, Optional


class HttpHandler:
    """
    Reusable HTTP client for calling external REST APIs.
    Supports GET, POST, PUT, DELETE.
    """

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    def get(self, endpoint: str, params: Optional[dict] = None) -> Dict[str, Any]:
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        response = requests.get(url, params=params)
        return self._process(response)

    def post(self, endpoint: str, data: Optional[dict] = None, files: Optional[dict] = None) -> Dict[str, Any]:
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        response = requests.post(url, data=data, files=files)
        return self._process(response)

    def put(self, endpoint: str, data: Optional[dict] = None) -> Dict[str, Any]:
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        response = requests.put(url, json=data)
        return self._process(response)

    def delete(self, endpoint: str) -> Dict[str, Any]:
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        response = requests.delete(url)
        return self._process(response)

    def _process(self, response: requests.Response) -> Dict[str, Any]:
        try:
            return {
                "status_code": response.status_code,
                "data": response.json()
            }
        except Exception:
            return {
                "status_code": response.status_code,
                "data": response.text
            }

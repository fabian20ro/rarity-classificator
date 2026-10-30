"""HTTP headers first: no hidden redirect-body reads or automatic retries."""

import requests


class HTTP:
    """Minimal synchronous transport; caller owns every body read and redirect."""

    def __init__(self):
        self.adapter = requests.adapters.HTTPAdapter(max_retries=0)

    def get(self, url, *, headers, stream, allow_redirects, timeout):
        if not stream or allow_redirects:
            raise ValueError("FineWeb transport requires explicit bounded body reads")
        request = requests.Request("GET", url, headers=headers).prepare()
        # Session.send consumes redirect bodies even with allow_redirects=False.
        # Adapter.send returns after headers; redirect and Range checks stay upstream.
        return self.adapter.send(
            request,
            stream=True,
            timeout=timeout,
            verify=True,
            cert=None,
            proxies=None,
        )

    def close(self):
        self.adapter.close()

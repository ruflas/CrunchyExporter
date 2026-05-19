import base64
import pytest
from src.crunchyroll.auth import CRAuth, DEFAULT_CLIENT_ID


def _header(client_id, secret=""):
    auth = CRAuth.__new__(CRAuth)
    auth.client_id = client_id
    auth.client_secret = secret
    return auth._basic_auth_header()


def _decode(header):
    encoded = header.removeprefix("Basic ")
    return base64.b64decode(encoded).decode()


class TestBasicAuthHeader:
    def test_format_is_basic_prefix(self):
        h = _header("myid")
        assert h.startswith("Basic ")

    def test_encodes_client_id_colon_secret(self):
        creds = _decode(_header("myid", "mysecret"))
        assert creds == "myid:mysecret"

    def test_strips_trailing_colon_from_client_id(self):
        creds = _decode(_header("myid:", ""))
        assert creds == "myid:"

    def test_with_client_secret(self):
        creds = _decode(_header("abc", "xyz"))
        assert creds == "abc:xyz"

    def test_default_client_id_used(self):
        auth = CRAuth.__new__(CRAuth)
        auth.client_id = DEFAULT_CLIENT_ID
        auth.client_secret = ""
        creds = _decode(auth._basic_auth_header())
        assert creds.startswith(DEFAULT_CLIENT_ID)

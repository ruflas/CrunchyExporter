import base64
import uuid
import requests
from .models import CRToken

CR_API_BASE = "https://beta-api.crunchyroll.com"

# Public web client credentials embedded in CR's web app.
# Documented widely in open-source CR tools (crunchy-cli, etc.).
# Override via config if these ever rotate.
DEFAULT_CLIENT_ID = "noaihdevm_6iyg0a8l0q"
DEFAULT_CLIENT_SECRET = ""  # public client — no secret


class CRAuthError(Exception):
    pass


class CRAuth:
    def __init__(self, client_id: str = DEFAULT_CLIENT_ID, client_secret: str = DEFAULT_CLIENT_SECRET):
        self.client_id = client_id
        self.client_secret = client_secret
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "Mozilla/5.0"})

    def _basic_auth_header(self) -> str:
        client_id = self.client_id.rstrip(":")  # guard: strip accidental trailing colon
        creds = f"{client_id}:{self.client_secret}"
        return f"Basic {base64.b64encode(creds.encode()).decode()}"

    def login_with_etp_rt(self, etp_rt: str) -> CRToken:
        """
        Authenticate using the etp_rt browser cookie.
        CR dropped the password grant — this is the current supported method.

        How to get etp_rt:
          1. Log into crunchyroll.com in your browser.
          2. DevTools → Application → Cookies → https://www.crunchyroll.com
          3. Copy the value of the 'etp_rt' cookie.
        """
        try:
            resp = self.session.post(
                f"{CR_API_BASE}/auth/v1/token",
                headers={"Authorization": self._basic_auth_header()},
                cookies={"etp_rt": etp_rt},
                data={
                    "grant_type": "etp_rt_cookie",
                    "scope": "offline_access",
                    "device_id": str(uuid.uuid4()),
                    "device_name": "Chrome on Windows",
                    "device_type": "com.crunchyroll.desktop.windows",
                },
                timeout=15,
            )
            resp.raise_for_status()
        except requests.HTTPError as e:
            raise CRAuthError(f"Login failed ({e.response.status_code}): {e.response.text}") from e

        data = resp.json()
        account_id = self._fetch_account_id(data["access_token"])
        return CRToken(
            access_token=data["access_token"],
            refresh_token=data.get("refresh_token", ""),
            account_id=account_id,
        )

    def refresh(self, refresh_token: str) -> CRToken:
        try:
            resp = self.session.post(
                f"{CR_API_BASE}/auth/v1/token",
                headers={"Authorization": self._basic_auth_header()},
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                    "scope": "offline_access",
                },
                timeout=15,
            )
            resp.raise_for_status()
        except requests.HTTPError as e:
            raise CRAuthError(f"Token refresh failed: {e}") from e

        data = resp.json()
        account_id = self._fetch_account_id(data["access_token"])
        return CRToken(
            access_token=data["access_token"],
            refresh_token=data.get("refresh_token", refresh_token),
            account_id=account_id,
        )

    def _fetch_account_id(self, access_token: str) -> str:
        resp = self.session.get(
            f"{CR_API_BASE}/accounts/v1/me",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()["account_id"]

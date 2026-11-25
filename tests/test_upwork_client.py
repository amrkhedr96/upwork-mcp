import json
import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock

from upwork_client import Store, UpworkClient, UpworkError, auth_url, proposal_input, stamp_expiry, token_form


class ClientTests(unittest.TestCase):
    def test_auth_url_contains_client_and_callback(self) -> None:
        url = auth_url("abc123", "https://www.upwork.com/ab/messages/rooms/")
        self.assertIn("response_type=code", url)
        self.assertIn("client_id=abc123", url)
        self.assertIn("redirect_uri=", url)

    def test_credentials_roundtrip_hides_secret_from_status(self) -> None:
        with TemporaryDirectory() as tmp:
            store = Store(Path(tmp))
            store.save_config("client-id-9999", "super-secret", "")
            status = UpworkClient(store).status()
            self.assertTrue(status["configured"])
            self.assertEqual(status["client_id_tail"], "9999")
            self.assertNotIn("super-secret", json.dumps(status))

    def test_token_form_uses_authorization_code(self) -> None:
        form = token_form(
            {"client_id": "id", "client_secret": "sec", "redirect_uri": "https://example.test/cb"},
            code="once",
        )
        self.assertEqual(form["grant_type"], "authorization_code")
        self.assertEqual(form["code"], "once")

    def test_stamp_expiry_is_before_ttl(self) -> None:
        stamped = stamp_expiry({"access_token": "t", "expires_in": 100}, now=1_000)
        self.assertEqual(stamped["expires_at"], 1_040)

    def test_short_cover_letter_is_rejected(self) -> None:
        with self.assertRaises(UpworkError):
            proposal_input(
                job_reference="~1",
                cover_letter="too short",
                charged_amount=40,
                contractor_id="c",
                odesk_user_id="o",
                team_org_id="t",
            )

    def test_exchange_saves_token_without_returning_it(self) -> None:
        with TemporaryDirectory() as tmp:
            store = Store(Path(tmp))
            store.save_config("id", "secret", "https://www.upwork.com/ab/messages/rooms/")
            http = MagicMock()
            response = MagicMock()
            response.status_code = 200
            response.json.return_value = {"access_token": "secret-token", "refresh_token": "r", "expires_in": 3600}
            http.post.return_value = response
            result = UpworkClient(store, http).exchange_code("code-1")
            self.assertTrue(result["authorized"])
            self.assertNotIn("access_token", result)
            saved = json.loads(store.token_path.read_text(encoding="utf-8"))
            self.assertEqual(saved["access_token"], "secret-token")
            self.assertGreater(saved["expires_at"], int(time.time()))


if __name__ == "__main__":
    unittest.main()

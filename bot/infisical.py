import os

import commons
from dotenv import load_dotenv
from infisical_sdk import InfisicalSDKClient

load_dotenv()


class Infisical:
    def __init__(self):
        self.client = InfisicalSDKClient(host="https://secrets.skelmis.co.nz")
        self.client.auth.universal_auth.login(
            client_id=os.environ["INFISICAL_ID"],
            client_secret=os.environ["INFISICAL_SECRET"],
        )

    def get_secret(self, secret_name: str) -> str:
        return self.client.secrets.get_secret_by_name(
            secret_name=secret_name,
            project_id=os.environ["INFISICAL_PROJECT_ID"],
            environment_slug=(
                "dev" if commons.value_to_bool(os.environ.get("DEBUG")) else "prod",
            ),
            secret_path="/",
            view_secret_value=True,
        ).secretValue

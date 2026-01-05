"""
A User model, used for authentication.
"""

from __future__ import annotations

import hashlib
import logging
import secrets
from typing import TYPE_CHECKING, Any, Optional, Union

from piccolo.columns import Boolean, Secret, Varchar
from piccolo.columns.column_types import Serial, Timestamptz
from piccolo.columns.readable import Readable
from piccolo.table import Table

from web.constants import IS_PRODUCTION
from web.util.table_mixins import utc_now, AuditMixin

if TYPE_CHECKING:
    from web.tables import OAuthEntry


logger = logging.getLogger(__name__)


class Users(AuditMixin, Table, tablename="users"):
    if TYPE_CHECKING:
        id: Serial

    username = Varchar(length=100, unique=True)
    password = Secret(length=255)
    name = Varchar(null=True)
    email = Varchar(length=255, unique=True)
    active = Boolean(default=False, help_text="Can this user sign in?")
    admin = Boolean(default=False, help_text="An admin can log into the Piccolo admin GUI.")
    superuser = Boolean(
        default=False,
        help_text=(
            "If True, this user can manage other users's passwords in the " "Piccolo admin GUI."
        ),
    )
    last_login = Timestamptz(
        null=True,
        default=None,
        required=False,
        help_text="When this user last logged in.",
    )
    auths_without_password = Boolean(
        default=False,
        help_text=(
            "If True, this user only authenticates via magic link and "
            "shouldn't be shown password and mfa change"
        ),
    )
    email_is_verified = Boolean(
        default=False,
        help_text="Is the users current email address verified?",
    )

    _min_password_length = 20 if IS_PRODUCTION else 6
    _max_password_length = 128
    # The number of hash iterations recommended by OWASP:
    # https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html#pbkdf2
    _pbkdf2_iteration_count = 600_000

    def __init__(self, **kwargs):
        # Generating passwords upfront is expensive, so might need reworking.
        password: str | None = kwargs.get("password", None)
        if password is not None:
            if not password.startswith("pbkdf2_sha256"):
                kwargs["password"] = self.__class__.hash_password(password)
        super().__init__(**kwargs)

    @classmethod
    def get_salt(cls):
        return secrets.token_hex(16)

    @classmethod
    def get_readable(cls) -> Readable:
        """
        Used to get a readable string, representing a table row.
        """
        return Readable(template="%s", columns=[cls.username])

    ###########################################################################

    @classmethod
    def _validate_password(cls, password: str):
        """
        Validate the raw password. Used by :meth:`update_password` and
        :meth:`create_user`.

        :param password:
            The raw password e.g. ``'hello123'``.
        :raises ValueError:
            If the password fails any of the criteria.

        """
        if not password:
            raise ValueError("A password must be provided.")

        if len(password) < cls._min_password_length:
            raise ValueError(f"The password is too short. (min {cls._min_password_length})")

        if len(password) > cls._max_password_length:
            raise ValueError(f"The password is too long. (max {cls._max_password_length})")

        if password.startswith("pbkdf2_sha256"):
            logger.warning("Tried to create a user with an already hashed password.")
            raise ValueError("Do not pass a hashed password.")

    @classmethod
    async def update_password(cls, user: Union[str, int], password: str):
        """
        The password is the raw password string e.g. ``'password123'``.
        The user can be a user ID, or a username.
        """
        if isinstance(user, str):
            clause = cls.username == user
        elif isinstance(user, int):
            clause = cls.id == user
        else:
            raise ValueError("The `user` arg must be a user id, or a username.")

        cls._validate_password(password=password)

        password = cls.hash_password(password)
        await cls.update({cls.password: password}).where(clause).run()

    @classmethod
    def hash_password(cls, password: str, salt: str = "", iterations: Optional[int] = None) -> str:
        """
        Hashes the password, ready for storage, and for comparing during
        login.

        :raises ValueError:
            If an excessively long password is provided.

        """
        if len(password) > cls._max_password_length:
            logger.warning("Excessively long password provided.")
            raise ValueError("The password is too long.")

        if not salt:
            salt = cls.get_salt()

        if iterations is None:
            iterations = cls._pbkdf2_iteration_count

        hashed = hashlib.pbkdf2_hmac(
            "sha256",
            bytes(password, encoding="utf-8"),
            bytes(salt, encoding="utf-8"),
            iterations,
        ).hex()
        return f"pbkdf2_sha256${iterations}${salt}${hashed}"

    def __setattr__(self, name: str, value: Any):
        """
        Make sure that if the password is set, it's stored in a hashed form.
        """
        if name == "password" and not value.startswith("pbkdf2_sha256"):
            value = self.__class__.hash_password(value)

        super().__setattr__(name, value)

    @classmethod
    def split_stored_password(cls, password: str) -> list[str]:
        elements = password.split("$")
        if len(elements) != 4:
            raise ValueError("Unable to split hashed password")
        return elements

    @classmethod
    async def login(cls, username: str, password: str) -> Optional[int]:
        """
        Make sure the user exists and the password is valid. If so, the
        ``last_login`` value is updated in the database.

        :returns:
            The id of the user if a match is found, otherwise ``None``.

        """
        if (max_username_length := cls.username.length) and len(username) > max_username_length:
            logger.warning("Excessively long username provided.")
            return None

        if len(password) > cls._max_password_length:
            logger.warning("Excessively long password provided.")
            return None

        response = (
            await cls.select(cls._meta.primary_key, cls.password)
            .where(cls.username == username)
            .first()
            .run()
        )
        if not response:
            # No match found. We still call hash_password
            # here to mitigate the ability to enumerate
            # users via response timings
            cls.hash_password(password)
            return None

        stored_password = response["password"]

        algorithm, iterations_, salt, hashed = cls.split_stored_password(stored_password)
        iterations = int(iterations_)

        if cls.hash_password(password, salt, iterations) == stored_password:
            # If the password was hashed in an earlier Piccolo version, update
            # it so it's hashed with the currently recommended number of
            # iterations:
            if iterations != cls._pbkdf2_iteration_count:
                await cls.update_password(username, password)

            await cls.update({cls.last_login: utc_now()}).where(cls.username == username)
            return response["id"]
        else:
            return None

    @classmethod
    async def create_user(cls, username: str, password: str, **extra_params) -> Users:
        """
        Creates a new user, and saves it in the database. It is recommended to
        use this rather than instantiating and saving ``Users`` directly, as
        we add extra validation.

        :raises ValueError:
            If the username or password is invalid.
        :returns:
            The created ``Users`` instance.

        """
        if not username:
            raise ValueError("A username must be provided.")

        cls._validate_password(password=password)

        user = cls(username=username, password=password, **extra_params)
        await user.save()
        return user

    async def get_oauth_entry(self) -> OAuthEntry | None:
        from web.tables import OAuthEntry

        return await OAuthEntry.objects().get(OAuthEntry.user == self)

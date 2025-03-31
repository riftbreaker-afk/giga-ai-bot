from dataclasses import dataclass


ACCOUNTS_FILE = "data/accounts.csv"

DISCORD_CAPTCHA_SITEKEY = "a9b5fb07-92ff-493f-86fe-352a2803b3df"


@dataclass
class Account:
    """
    用于存储Discord账号数据的类
    """

    index: int
    token: str
    proxy: str

@dataclass
class DataForTasks:
    """
    用于存储任务数据的类
    """

    LEAVE_GUILD_IDS: list[str]
    PROFILE_PICTURES: list[str]
    EMOJIS_INFO: list[dict]
    INVITE_CODE: str | None
    REACTION_CHANNEL_ID: str | None
    REACTION_MESSAGE_ID: str | None
    IF_TOKEN_IN_GUILD_ID: str | None
    BUTTON_PRESSER_BUTTON_DATA: dict | None
    BUTTON_PRESSER_APPLICATION_ID: str | None
    BUTTON_PRESSER_GUILD_ID: str | None
    BUTTON_PRESSER_CHANNEL_ID: str | None
    BUTTON_PRESSER_MESSAGE_ID: str | None


MAIN_MENU_OPTIONS = [
    "AI Giga",
    "Exit",
]

# websites domain
import os

REDDIT = os.environ.get("REDDIT", "")
SHOPPING = os.environ.get("SHOPPING", "")
SHOPPING_ADMIN = os.environ.get("SHOPPING_ADMIN", "")
GITLAB = os.environ.get("GITLAB", "")
WIKIPEDIA = os.environ.get("WIKIPEDIA", "")
MAP = os.environ.get("MAP", "")
HOMEPAGE = os.environ.get("HOMEPAGE", "")

assert (
    REDDIT
    and SHOPPING
    and SHOPPING_ADMIN
    and GITLAB
    and WIKIPEDIA
    and MAP
    and HOMEPAGE
), (
    f"Please setup the URLs to each site. Current: "
    + f"Reddit: {REDDIT}"
    + f"Shopping: {SHOPPING}"
    + f"Shopping Admin: {SHOPPING_ADMIN}"
    + f"Gitlab: {GITLAB}"
    + f"Wikipedia: {WIKIPEDIA}"
    + f"Map: {MAP}"
    + f"Homepage: {HOMEPAGE}"
)


ACCOUNTS = {
    "reddit": {"username": "MarvelsGrantMan136", "password": "test1234"},
    "gitlab": {"username": "byteblaze", "password": "hello1234"},
    "shopping": {
        "username": "emma.lopez@gmail.com",
        "password": "Password.123",
    },
    "shopping_admin": {"username": "admin", "password": "admin1234"},
    "shopping_site_admin": {"username": "admin", "password": "admin1234"},
}

URL_MAPPINGS = {
    REDDIT: "http://10.10.0.120:9999",
    SHOPPING: "http://10.10.0.120:7770",
    SHOPPING_ADMIN: "http://10.10.0.120:7780/admin",
    GITLAB: "http://10.10.0.120:8023",
    WIKIPEDIA: "http://10.10.0.120:8888/wikipedia_en_all_maxi_2022-05/A/User:The_other_Kiwix_guy/Landing",
    MAP: "http://10.10.0.120:3000",
    HOMEPAGE: "http://10.10.0.120:4399",
}

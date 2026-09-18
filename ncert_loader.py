import requests
from bs4 import BeautifulSoup


NCERT_TEXTBOOK_URL = "https://ncert.nic.in/textbook.php"


def test_ncert_connection():

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 "
            "(KHTML, like Gecko) "
            "Chrome/140.0.0.0 Safari/537.36"
        ),
        "Accept": (
            "text/html,application/xhtml+xml,"
            "application/xml;q=0.9,image/avif,image/webp,"
            "*/*;q=0.8"
        ),
        "Accept-Language": "en-US,en;q=0.9"
    }

    try:

        print("Connecting to NCERT...")

        response = requests.get(
            NCERT_TEXTBOOK_URL,
            headers=headers,
            timeout=30
        )

        print("Status code:", response.status_code)

        if response.status_code != 200:

            print(
                "NCERT returned status:",
                response.status_code
            )

            return False

        soup = BeautifulSoup(
            response.text,
            "html.parser"
        )

        print()
        print("NCERT website connected successfully.")

        if soup.title:
            print(
                "Page title:",
                soup.title.get_text(strip=True)
            )

        print(
            "Page size:",
            len(response.text),
            "characters"
        )

        return True

    except requests.exceptions.ConnectionError as e:

        print()
        print("Connection error.")
        print(e)

        return False

    except requests.exceptions.Timeout:

        print()
        print("NCERT connection timed out.")

        return False

    except Exception as e:

        print()
        print("Unexpected error:")
        print(e)

        return False


if __name__ == "__main__":

    success = test_ncert_connection()

    print()

    if success:
        print("NCERT connection test PASSED.")
    else:
        print("NCERT connection test FAILED.")
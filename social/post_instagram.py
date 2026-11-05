"""Post today's Pourcast graphic to Instagram and the Facebook Page via Meta's Graph API.

GitHub secrets (never commit them):
  IG_TOKEN    long-lived Page access token (instagram_basic, instagram_content_publish,
              pages_manage_posts, pages_read_engagement, pages_show_list)
  IG_USER_ID  the Instagram Business account ID linked to the Pourcast Facebook Page
  FB_PAGE_ID  (optional) the Pourcast Facebook Page ID; if set, also posts to Facebook

Run: python3 social/post_instagram.py [--dry-run]
"""
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
API = "https://graph.facebook.com/v21.0"
CFG = json.load(open(os.path.join(ROOT, "config.json")))
BASE = CFG["base_url"].rstrip("/")
LOCATION = CFG.get("location_page_id", "")  # Facebook place ID for Nashville, Tennessee


class APIError(SystemExit):
    pass


def call(method, path, **params):
    data = urllib.parse.urlencode(params).encode()
    url = f"{API}/{path}"
    req = urllib.request.Request(url + ("" if method == "POST" else "?" + data.decode()),
                                 data=data if method == "POST" else None, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r)
    except urllib.error.HTTPError as err:
        body = err.read().decode(errors="replace")
        # never print the token
        raise APIError(f"Meta API error {err.code} on {path}: {body}")


def main():
    dry = "--dry-run" in sys.argv
    today = datetime.now(ZoneInfo(CFG.get("timezone", "America/Chicago"))).date().isoformat()
    cap_file = os.path.join(ROOT, "public", "social", f"{today}.txt")
    if not os.path.exists(cap_file):
        sys.exit(f"No caption for {today}. Run build.py first.")
    caption = open(cap_file).read()
    image_url = f"{BASE}/social/{today}.png"

    # the image must already be live on the website for Instagram to fetch it
    for attempt in range(10):
        try:
            with urllib.request.urlopen(urllib.request.Request(image_url, method="HEAD"), timeout=30) as r:
                if r.status == 200:
                    break
        except Exception:
            pass
        print(f"Waiting for {image_url} to go live...")
        time.sleep(60)
    else:
        sys.exit(f"{image_url} never went live; not posting.")

    if dry:
        print("DRY RUN. Would post", image_url, "\n\n" + caption)
        return

    token, user, page = os.environ.get("IG_TOKEN"), os.environ.get("IG_USER_ID"), os.environ.get("FB_PAGE_ID")
    if not token or not (user or page):
        sys.exit("IG_TOKEN plus IG_USER_ID and/or FB_PAGE_ID secrets are not set yet.")

    failed = []
    if page:
        try:
            # IG_TOKEN may be a user token; Facebook Page posts need the Page's own token,
            # which a user token can look up (needs pages_show_list / pages_manage_posts).
            page_token = call("GET", page, fields="access_token", access_token=token).get("access_token") or token
            try:
                fb = call("POST", f"{page}/photos", url=image_url, caption=caption, place=LOCATION, access_token=page_token) if LOCATION \
                    else call("POST", f"{page}/photos", url=image_url, caption=caption, access_token=page_token)
            except APIError as err:
                print("Facebook rejected the location tag, posting without it:", err)
                fb = call("POST", f"{page}/photos", url=image_url, caption=caption, access_token=page_token)
            print(f"Posted to Facebook for {today}: post id {fb.get('post_id') or fb.get('id')}")
        except SystemExit as err:
            print(err)
            if "publish_actions" in str(err):
                print("Hint: IG_TOKEN is a user token. Save the PAGE access token instead.")
            failed.append("Facebook")
    if user:
        try:
            post_instagram(user, token, image_url, caption, today)
        except SystemExit as err:
            print(err); failed.append("Instagram")
    if failed:
        sys.exit("Failed: " + ", ".join(failed))


def post_instagram(user, token, image_url, caption, today):

    try:
        container = (call("POST", f"{user}/media", image_url=image_url, caption=caption, location_id=LOCATION, access_token=token) if LOCATION
                     else call("POST", f"{user}/media", image_url=image_url, caption=caption, access_token=token))["id"]
    except APIError as err:
        print("Instagram rejected the location tag, posting without it:", err)
        container = call("POST", f"{user}/media", image_url=image_url, caption=caption, access_token=token)["id"]
    for _ in range(30):
        status = call("GET", container, fields="status_code", access_token=token).get("status_code")
        if status == "FINISHED":
            break
        if status in ("ERROR", "EXPIRED"):
            sys.exit(f"Instagram could not process the image (status {status}).")
        time.sleep(5)
    post = call("POST", f"{user}/media_publish", creation_id=container, access_token=token)
    print(f"Posted to Instagram for {today}: media id {post.get('id')}")


if __name__ == "__main__":
    main()

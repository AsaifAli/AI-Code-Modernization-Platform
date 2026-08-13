import subprocess

def clone_repo(url: str, dest: str, oauth_token: str = None):
    if oauth_token:
        # Authenticated clone for private repo
        url_with_auth = url.replace("https://", f"https://oauth2:{oauth_token}@")
    else:
        url_with_auth = url

    cmd = ["git", "clone", url_with_auth, dest]
    subprocess.run(cmd, check=True)

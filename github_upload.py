import os
import subprocess

REPO_PATH = r"F:\scraper\salons"   # ⚠️ change to your repo path

def upload_to_github(folder_name):
    try:
        os.chdir(REPO_PATH)

        # Add files
        subprocess.run(["git", "add", "."], check=True)

        # Commit
        subprocess.run(
            ["git", "commit", "-m", f"Added {folder_name} website"],
            check=True
        )

        # Push
        subprocess.run(["git", "push"], check=True)

        print("✅ Uploaded to GitHub")

        # Return live URL
        return f"https://thepagedoor.github.io/salons/{folder_name}/"

    except Exception as e:
        print("❌ GitHub upload failed:", e)
        return None
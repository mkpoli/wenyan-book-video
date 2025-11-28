import argparse
import os
import sys
from pathlib import Path
from typing import Optional

# Try to import tomllib (Python 3.11+) or fall back to toml
try:
    import tomllib
except ImportError:
    try:
        import toml as tomllib
    except ImportError:
        print("Error: 'tomllib' (Python 3.11+) or 'toml' package is required.")
        sys.exit(1)

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# If modifying these scopes, delete the file token.json.
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def load_config(config_path: Path) -> dict:
    if not config_path.exists():
        print(f"Error: Config file not found at {config_path}")
        sys.exit(1)
    with open(config_path, "rb") as f:
        return tomllib.load(f)


def get_authenticated_service(secrets_file: Path):
    creds = None
    token_path = secrets_file.parent / "token.json"
    
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
        
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not secrets_file.exists():
                print(f"Error: Client secrets file not found at {secrets_file}")
                print("Please download it from Google Cloud Console and save it as 'client_secrets.json' in the uploader directory.")
                sys.exit(1)
                
            flow = InstalledAppFlow.from_client_secrets_file(
                str(secrets_file), SCOPES
            )
            creds = flow.run_local_server(port=0)
            
        # Save the credentials for the next run
        with open(token_path, "w") as token:
            token.write(creds.to_json())

    return build("youtube", "v3", credentials=creds)


def upload_video(youtube, file_path: Path, title: str, description: str, category_id: str = "27", privacy_status: str = "private", thumbnail_path: Optional[Path] = None, playlist_id: Optional[str] = None):
    body = {
        "snippet": {
            "title": title,
            "description": description,
            "categoryId": category_id,  # 27 is Education
        },
        "status": {
            "privacyStatus": privacy_status,
            "selfDeclaredMadeForKids": False,
        }
    }

    media = MediaFileUpload(
        str(file_path),
        chunksize=-1, 
        resumable=True
    )

    print(f"Uploading file: {file_path}")
    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media
    )

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"Uploaded {int(status.progress() * 100)}%")

    print("Upload Complete!")
    video_id = response.get('id')
    print(f"Video ID: {video_id}")
    
    # Upload Thumbnail
    if thumbnail_path and thumbnail_path.exists():
        print(f"Uploading thumbnail: {thumbnail_path}")
        try:
            youtube.thumbnails().set(
                videoId=video_id,
                media_body=MediaFileUpload(str(thumbnail_path))
            ).execute()
            print("Thumbnail uploaded!")
        except Exception as e:
            print(f"Error uploading thumbnail: {e}")

    # Add to Playlist
    if playlist_id:
        print(f"Adding to playlist: {playlist_id}")
        try:
            youtube.playlistItems().insert(
                part="snippet",
                body={
                    "snippet": {
                        "playlistId": playlist_id,
                        "resourceId": {
                            "kind": "youtube#video",
                            "videoId": video_id
                        }
                    }
                }
            ).execute()
            print("Added to playlist!")
        except Exception as e:
            print(f"Error adding to playlist: {e}")
            
    return response


def main():
    parser = argparse.ArgumentParser(description="Upload Wenyan Book videos to YouTube.")
    parser.add_argument("chapter_id", type=int, help="The chapter ID (e.g., 7)")
    parser.add_argument("--dry-run", action="store_true", help="Run without uploading")
    parser.add_argument("--privacy", default="private", choices=["private", "unlisted", "public"], help="Privacy status of the video")
    
    args = parser.parse_args()
    
    # Paths
    script_dir = Path(__file__).parent.resolve()
    project_root = script_dir.parent
    config_path = script_dir / "config.toml"
    secrets_path = script_dir / "client_secrets.json"
    
    # Load Config
    config = load_config(config_path)
    
    # Get Playlist ID
    playlist_id = config.get("youtube", {}).get("playlist_id")
    
    # Get Chapter Metadata
    chapter_str = str(args.chapter_id)
    if chapter_str not in config["chapters"]:
        print(f"Error: Chapter {args.chapter_id} not found in config.")
        sys.exit(1)
        
    chapter_data = config["chapters"][chapter_str]
    chinese_title = chapter_data.get("chinese", "")
    english_title = chapter_data.get("english", "")
    
    if not english_title:
        print(f"Warning: English title for Chapter {args.chapter_id} is missing in config.toml.")
        # Proceeding anyway, user can check in confirmation
    
    # Prepare Metadata
    title_template = config["templates"]["title"]
    desc_template = config["templates"]["description"]
    
    title = title_template.format(idx=args.chapter_id, chinese_title=chinese_title, english_title=english_title)
    description = desc_template.format(idx=args.chapter_id, chinese_title=chinese_title, english_title=english_title)
    
    # Find Video File
    video_filename = f"chapter{args.chapter_id}.mp4"
    video_path = project_root / "renderer" / "out" / video_filename
    
    if not video_path.exists():
        print(f"Error: Video file not found at {video_path}")
        sys.exit(1)

    # Find Thumbnail File
    thumbnail_filename = f"{args.chapter_id}.png"
    thumbnail_path = script_dir / "thumbnails" / thumbnail_filename
    
    if not thumbnail_path.exists():
        print(f"Warning: Thumbnail file not found at {thumbnail_path}")
        thumbnail_path = None

    # Confirmation
    print("\n" + "="*40)
    print("YOUTUBE UPLOAD METADATA")
    print("="*40)
    print(f"File:        {video_path}")
    print(f"Thumbnail:   {thumbnail_path if thumbnail_path else 'None'}")
    print(f"Title:       {title}")
    LINE_DELIMITER = "\n"
    print(f"Description: (First 3 lines)\n{LINE_DELIMITER.join(description.splitlines()[:3])}...")
    print(f"Privacy:     {args.privacy}")
    print(f"MadeForKids: False")
    print(f"Playlist:    {playlist_id if playlist_id else 'None'}")
    print("="*40 + "\n")
    
    if args.dry_run:
        print("Dry run mode. Skipping upload.")
        return

    confirm = input("Proceed with upload? (y/N): ").strip().lower()
    if confirm != 'y':
        print("Upload cancelled.")
        sys.exit(0)
        
    # Authenticate and Upload
    try:
        youtube = get_authenticated_service(secrets_path)
        upload_video(youtube, video_path, title, description, privacy_status=args.privacy, thumbnail_path=thumbnail_path, playlist_id=playlist_id)
    except Exception as e:
        print(f"An error occurred: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()

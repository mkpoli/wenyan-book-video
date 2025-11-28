# YouTube Uploader for Wenyan Book Video

This directory contains scripts to upload generated videos to YouTube with formatted titles and descriptions.

## Prerequisites

### Google API

You need to have a Google Cloud Project with YouTube Data API v3 enabled with OAuth credentials in order to be able to upload to the Video.

1.  Login to https://console.cloud.google.com/
2.  Create a new project (or select an existing one).
3.  Enable the YouTube Data API v3.
    - “APIs & Services” → “Library” -> Search for “YouTube Data API v3”
4.  Create credentials (OAuth 2.0 Client ID) and download the JSON file.
    - “Credentials” → “Create Credentials” → “OAuth 2.0 Client ID”
        - To do so you need to configure consent screen first.
        - Application type: Desktop app, Name: "Wenyan Book Video Python Uploader"
5. Save the JSON file as `client_secrets.json` in this directory (`uploader/`).
6. Add YouTube scope to OAuth 2.0 Client.
    - “Google Auth Platform” -> “Data access” -> “Add or remove scopes”
6. Add your YouTube account to Test users/
    - “Google Auth Platform” -> “Audience” -> “Test users”

### Prepare the Video

You have to prepare the rendered video before hand after processing the video with processor and renderer in `/renderer/out/chapter{idx}.mp4`. Then you also need to prepare thumbnails in `/uploader/thumbnails/{idx}.png`.

## Configuration

Templates are stored in `config.toml`. You can edit `config.toml` to modify the templates and chapter titles.

## Usage

Under this folder (`uploader/`), run:
```sh
uv sync
uv run upload.py <chapter_id> --dry-run
```
Then after you're confident, run without `--dry-run` flag.

After the upload has finished, you can find the video at your YouTube channel as a private video. Make it public when you are ready.

## Details

-   The script will look for the video file at `renderer/out/chapter{id}.mp4` with given chapter ID.
-   **Thumbnails**: The script will look for a thumbnail at `uploader/thumbnails/{id}.png`. If found, it will be uploaded.
-   **Made for Kids**: The video will be explicitly set as "Not Made for Kids" (`selfDeclaredMadeForKids: False`).
-   You will be asked to confirm the metadata before the upload starts.
-   On the first run, a browser window (or a link in the console) will open for you to authenticate with your Google account. A `token.json` file will be created to store the credentials for future runs.

## Troubleshooting

-   **Client Secrets Not Found**: Ensure `client_secrets.json` is in the `uploader` directory.
-   **Video Not Found**: Ensure the video file exists in `renderer/out/`.
-   **Authentication Error**: If `token.json` is invalid or expired, delete it and run the script again to re-authenticate.

import marimo

__generated_with = "0.17.7"
app = marimo.App(width="medium")


@app.cell
def _():
    # Download the dictionary
    import requests
    response = requests.get("https://qieyun-tts.com/dictionary_txt")
    if response.status_code != 200:
        raise Exception(f"Failed to download dictionary: {response.status_code}")
    return response.text


if __name__ == "__main__":
    app.run()

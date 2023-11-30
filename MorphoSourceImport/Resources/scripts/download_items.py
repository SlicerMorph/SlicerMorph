import json
import os
import sys

import requests
import threading
import concurrent.futures


import morphosource as ms
from morphosource import DownloadConfig
from morphosource.download import download_media_bundle, get_download_media_zip_url


def download_file(url, path, api_key, chunk_size, progress_update_func, total_kb):
    headers = {"Authorization": api_key}
    download_response = requests.get(url, headers=headers, stream=True)

    with open(path, 'wb') as fd:
        for chunk in download_response.iter_content(chunk_size=chunk_size):
            fd.write(chunk)
            progress_update_func(1, total_kb)  # Update progress for each chunk


class MSDownload(object):
    def __init__(self, config_dict: dict):

        self.config_dict = config_dict
        self.DownloadConfig = DownloadConfig  # to be set when items are to be downloaded
        self.current_download_config: Optional[DownloadConfig] = None  # for storing Download config object
        self.download_media_bundle = download_media_bundle
        self.get_download_media_zip_url = get_download_media_zip_url

        self.download_folder = None
        self.items_to_download = None
        self.total_items = None
        self.completed_downloads = None
        self.total_chunks = None
        self.completed_chunks = None
        self.total_mb = None

        self.configure_download()

    def calculate_total_chunks(self):
        total_chunks = 0
        for media_id in self.items_to_download:
            url = self.get_download_media_zip_url(media_id=media_id,
                                                  download_config=self.current_download_config)
            response = requests.head(url, headers={"Authorization": self.current_download_config.api_key})
            size = int(response.headers.get('content-length', 0))
            total_chunks += size // 128 + 1
        return total_chunks

    def configure_download(self):
        self.current_download_config = self.DownloadConfig(api_key=self.config_dict['api_key'],
                                                           use_statement=self.config_dict['usage_statement'],
                                                           use_categories=self.config_dict['usage_categories'],
                                                           use_category_other=None)
        self.items_to_download = self.config_dict['checked_items']
        self.download_folder = self.config_dict['download_folder']
        self.total_items = len(self.items_to_download)
        self.total_chunks = self.calculate_total_chunks()
        total_kb = self.total_chunks * 128 / 1024  # Calculate total data in kilobytes
        self.total_mb = total_kb / 1024  # Convert total data to megabytes

    def update_progress(self, chunks, total_kb):
        self.completed_chunks += chunks
        progress = self.completed_chunks / self.total_chunks
        downloaded_kb = self.completed_chunks * 128 / 1024  # Calculate downloaded data in kilobytes
        downloaded_mb = downloaded_kb / 1024  # Convert downloaded data to megabytes
        print(f"Download Progress: {progress * 100:.2f}%, {downloaded_mb:.2f} MB "
              f"of {self.total_mb:.2f} MB downloaded", flush=True)

    def downloadItems(self):
        # Logic to download items
        self.completed_chunks = 0
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = []
            for media_id in self.items_to_download:
                filename = f"media_{media_id}.zip"
                full_file_path = os.path.join(self.download_folder, filename)
                download_url = self.get_download_media_zip_url(media_id=media_id,
                                                               download_config=self.current_download_config)
                futures.append(executor.submit(download_file, download_url, full_file_path,
                                               self.current_download_config.api_key, 128,
                                               self.update_progress, self.total_mb))
            concurrent.futures.wait(futures)

        print(f"Completed downloading {self.completed_downloads} of {len(self.items_to_download)} items.", flush=True)


if __name__ == "__main__":
    # Extract command line arguments
    config_dict = sys.argv[1]  # Assuming JSON string as the first argument
    config_dict = json.loads(config_dict)

    downloader = MSDownload(config_dict)
    downloader.downloadItems()

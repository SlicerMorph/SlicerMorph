import json
import os
import sys
import time

import requests
import threading
import concurrent.futures
from typing import Optional

# import morphosource as ms
from morphosource import DownloadConfig
from morphosource.download import download_media_bundle, get_download_media_zip_url


def file_exists_and_size(path):
    """Check if a file exists and return its size."""
    if os.path.exists(path):
        return os.path.getsize(path)
    return 0


def download_file(url, path, api_key, chunk_size, progress_update_func, total_bytes, media_id, existing_file_size=0, max_retries=10, retry_delay=5):
    headers = {"Authorization": api_key}
    if existing_file_size > 0:
        headers['Range'] = f'bytes={existing_file_size}-'

    def download_chunk(download_response, fd, downloaded_bytes):
        for chunk in download_response.iter_content(chunk_size=chunk_size):
            fd.write(chunk)
            downloaded_bytes += len(chunk)
            progress_update_func(media_id, downloaded_bytes, total_bytes)
        return downloaded_bytes

    download_response = requests.get(url, headers=headers, stream=True)

    # Check HTTP response status code
    if download_response.status_code in [200, 206]:
        downloaded_bytes = existing_file_size
        with open(path, 'ab' if existing_file_size > 0 else 'wb') as fd:
            while downloaded_bytes < total_bytes:
                try:
                    downloaded_bytes = download_chunk(download_response, fd, downloaded_bytes)
                    break  # Exit loop if successful
                except requests.RequestException as e:
                    print(f"Error during download chunk: {e}. Retrying...", flush=True)
                    time.sleep(retry_delay)
                    download_response = requests.get(url, headers=headers, stream=True)
                    max_retries -= 1
                    if max_retries <= 0:
                        print(f"Max retries reached. Download failed.", flush=True)
                        return

        # After the download loop, do a final check and update progress to 100%
        # if the downloaded size matches or exceeds the expected total size.
        final_file_size = file_exists_and_size(path)
        if final_file_size >= total_bytes:
            progress_update_func(media_id, final_file_size, total_bytes)
    else:
        # Handle error or unexpected status code
        print(f"Error during download: Unexpected status code {download_response.status_code} for media ID {media_id}", flush=True)


class MSDownload:
    def __init__(self, config_dict: dict):
        self.sizes = None
        self.total_size = None
        self.config_dict = config_dict
        self.DownloadConfig = DownloadConfig  # to be set when items are to be downloaded
        self.current_download_config: Optional[DownloadConfig] = None  # for storing Download config object
        self.download_media_bundle = download_media_bundle
        self.get_download_media_zip_url = get_download_media_zip_url

        self.download_folder = None
        self.items_to_download = None
        self.total_items = None
        self.completed_downloads = None
        self.download_progress = {}  # Dictionary to track progress of each download
        self.completed_chunks = None
        self.total_mb = None
        self.chunk_size = (1 * 1024) * 1024

        self.configure_download()

    def calculate_total_size(self):

        sizes = {}
        total_size = 0
        for media_id in self.items_to_download:
            url = self.get_download_media_zip_url(media_id=media_id,
                                                  download_config=self.current_download_config)
            response = requests.head(url, headers={"Authorization": self.current_download_config.api_key})
            size = int(response.headers.get('content-length', 0))
            total_size += size
            sizes[media_id] = size
        return total_size, sizes

    def configure_download(self):
        self.current_download_config = self.DownloadConfig(api_key=self.config_dict['api_key'],
                                                           use_statement=self.config_dict['usage_statement'],
                                                           use_categories=self.config_dict['usage_categories'],
                                                           use_category_other=None)
        self.items_to_download = self.config_dict['checked_items']
        self.download_folder = self.config_dict['download_folder']
        self.total_items = len(self.items_to_download)
        self.total_size, self.sizes = self.calculate_total_size()
        self.total_mb = self.total_size / (1024 * 1024)  # Convert total size to megabytes

    def update_progress(self, media_id, downloaded_bytes, total_bytes):
        with threading.Lock():
            self.download_progress[media_id] = downloaded_bytes

        total_downloaded_bytes = sum(self.download_progress.values())
        total_progress = total_downloaded_bytes / self.total_size  # self.total_size should be the sum of all file sizes
        total_downloaded_mb = total_downloaded_bytes / (1024 * 1024)

        # Diagnostic print statements
        # print(f"[Debug] Media ID: {media_id}, Downloaded Bytes: {downloaded_bytes}, Total Bytes: {total_bytes}")
        # print(f"[Debug] Total Downloaded Bytes: {total_downloaded_bytes}, Total Size: {self.total_size}")
        # print(f"[Debug] Total Progress: {total_progress * 100:.2f}%")
        # print(f"[Debug] Total Downloaded MB: {total_downloaded_mb:.2f} MB "
        #       f"of {self.total_mb:.2f} MB downloaded", flush=True)
        print(f"Download Progress: {total_progress * 100:.3f}%, {total_downloaded_mb:.3f} MB "
              f"of {self.total_mb:.2f} MB downloaded", flush=True)

    def downloadItems(self):
        self.completed_downloads = 0
        download_completed_successfully = False

        self.download_progress = {media_id: 0 for media_id in self.items_to_download}  # Initialize progress

        start_time = time.time()

        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
                futures = []
                for media_id in self.items_to_download:
                    partial_filename = f"partial_media_{media_id}.zip"
                    full_file_path = os.path.join(self.download_folder, partial_filename)
                    existing_file_size = file_exists_and_size(full_file_path)
                    max_retries = 10
                    retry_delay = 5
                    download_url = self.get_download_media_zip_url(media_id=media_id,
                                                                   download_config=self.current_download_config)
                    futures.append(executor.submit(download_file, download_url, full_file_path,
                                                   self.current_download_config.api_key, self.chunk_size,
                                                   self.update_progress, self.total_size, media_id,
                                                   existing_file_size, max_retries, retry_delay))
                    self.completed_downloads += 1
                concurrent.futures.wait(futures)

            download_completed_successfully = True
        except Exception as e:
            print(f"Error during download: {e}", flush=True)

        for media_id in self.items_to_download:
            partial_filename = f"partial_media_{media_id}.zip"
            full_partial_path = os.path.join(self.download_folder, partial_filename)

            if abs(file_exists_and_size(full_partial_path) - self.sizes[media_id]) <= 2:
                print(f"[Debug] Media ID: {media_id}, Downloaded Bytes: {file_exists_and_size(full_partial_path)}, "
                      f"Total Bytes: {self.sizes[media_id]}")
                final_filename = f"media_{media_id}.zip"
                full_final_path = os.path.join(self.download_folder, final_filename)
                os.rename(full_partial_path, full_final_path)
            else:
                print(f"[Debug] Media ID: {media_id}, size mismatch")
                print(f"[Debug] Media ID: {media_id}, Downloaded Bytes: {file_exists_and_size(full_partial_path)}, "
                      f"Total Bytes: {self.sizes[media_id]}")

        end_time = time.time()
        duration = end_time - start_time
        status_message = "Completed" if download_completed_successfully else "Terminated"
        print(
            f"{status_message} downloading {self.completed_downloads} of {len(self.items_to_download)} items in {duration:.2f} seconds.",
            flush=True)


if __name__ == "__main__":
    # Extract command line arguments
    config_dict = sys.argv[1]  # Assuming JSON string as the first argument
    config_dict = json.loads(config_dict)

    downloader = MSDownload(config_dict)
    downloader.downloadItems()

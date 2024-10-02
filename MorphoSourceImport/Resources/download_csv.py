import time
import datetime
import json
import sys
import os
import requests

from collections import OrderedDict

from threading import Lock
import concurrent.futures
from concurrent.futures import ThreadPoolExecutor

import pandas as pd

import slicer
import morphosource as ms
from morphosource import search_media, DownloadVisibility
from morphosource.search import SearchResults


def unlist_cell(cell):
    """If the cell is a list, return the items separated by semicolons.
    If the cell is empty or None, return an empty string. Otherwise, return the cell unchanged."""
    if isinstance(cell, list):
        return " ; ".join(map(str, cell))
    elif cell is None or cell == []:
        return ""
    return cell


class DownloadMSRecords:
    def __init__(self, query: str, media_type: str, taxonomy_gbif: str, path: str,
                 openDownloadsOnly: bool, media_tag: str = None, per_page: int = 100):

        self.completed_pages = 0  # Initialize the counter

        self.lock = Lock()  # Initialize a lock for thread-safe operations

        self.ms = ms
        self.search_media = search_media
        self.SearchResults = SearchResults

        self.pd = pd

        self.path = path

        self.query = query
        self.taxonomy_gbif = taxonomy_gbif
        self.media_type = media_type
        self.media_tag = media_tag
        self.per_page = per_page

        # set initial download visibility
        if openDownloadsOnly:
            self.visibility = DownloadVisibility.OPEN
        else:
            self.visibility = DownloadVisibility.RESTRICTED

        self.pages = OrderedDict()
        self.total_count = None
        self.total_pages = None
        self.first_record = None

        self.runFirstQuery()

    def get_urls_for_page(self, search_results):
        thumbnail_urls = []
        web_urls = []
        for media in search_results.items:
            thumbnail_urls.append(media.get_thumbnail_url())
            web_urls.append(media.get_website_url())

        return thumbnail_urls, web_urls

    def runFirstQuery(self):
        print(f'Running First Query', flush=True)
        self.first_record = self.search_media(query=self.query,
                                              taxonomy_gbif=self.taxonomy_gbif,
                                              media_type=self.media_type,
                                              visibility=self.visibility,
                                              media_tag=self.media_tag,
                                              per_page=self.per_page,
                                              page=1)
        self.total_pages = int(self.first_record.pages['total_pages'])
        self.total_count = int(self.first_record.pages['total_count'])

        print(f'First Query Done.', flush=True)

    def get_dataframe_with_updated_index(self, page_number, search_result):
        """
        Updates the index of the current DataFrame based on the page number
        and the number of records per page.
        """
        # Calculate the start index for the current page
        start_index = (page_number - 1) * self.per_page

        # Extracting the 'data' dictionaries from each item in search_results
        search_results_data = [item.data for item in search_result.items]

        # Converting the list of dictionaries to a pandas DataFrame
        search_results_df = pd.DataFrame(search_results_data)

        # Update the DataFrame index to reflect the current page
        search_results_df.index = range(start_index, start_index + len(search_results_df))

        # Apply the unlist_cell function to each cell in the DataFrame
        search_results_df = search_results_df.applymap(unlist_cell)

        return search_results_df

    def download_and_save_page(self, page):
        print(f'Downloading Page {page}', flush=True)
        retry_count = 0
        max_retries = 5  # Set the maximum number of retries

        while retry_count < max_retries:
            try:
                search_result = self.search_media(query=self.query,
                                                  taxonomy_gbif=self.taxonomy_gbif,
                                                  media_type=self.media_type,
                                                  visibility=self.visibility,
                                                  media_tag=self.media_tag,
                                                  per_page=self.per_page,
                                                  page=page)

                # Get the thumbnail and web URLs for the current page
                thumbnail_urls, web_urls = self.get_urls_for_page(search_result)

                with self.lock:
                    # Store the search results in the ordered dictionary
                    self.pages[page] = {'search_results': search_result,
                                        'thumbnail_urls': thumbnail_urls,
                                        'web_urls': web_urls,
                                        'search_results_df': self.get_dataframe_with_updated_index(page, search_result)}

                    # Increment the completed pages counter
                    self.completed_pages += 1

                # Calculate and print the progress
                progress = (self.completed_pages / self.total_pages) * 100
                print(f"PROGRESS:{progress}", flush=True)
                break  # Exit the retry loop on successful download
            except requests.exceptions.RequestException as e:
                print(f"Error in Page Download: {e}", flush=True)
                retry_count += 1  # Increment the retry counter

        if retry_count == max_retries:
            print(f"Failed to download Page {page} after {max_retries} attempts.", flush=True)

    def download_all_pages(self):
        print(f"Starting ThreadPoolExecutor", flush=True)
        with ThreadPoolExecutor(max_workers=6) as executor:
            # Create a list of futures
            futures = [executor.submit(self.download_and_save_page, page) for page in range(1, self.total_pages + 1)]

            # Optionally, you can process results as they are completed
            for future in concurrent.futures.as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    print(f"Error in Page Download: {e}", flush=True)

    def format_for_filename(self, text):
        """Format the text to be suitable for use in a filename."""
        return text.replace(" ", "_").replace("/", "_").replace("\\", "_")

    def combine_and_save_dataframes(self):
        # Initialize an empty list to store individual DataFrames
        all_dfs = []

        # Sort the keys of the pages dictionary and iterate in sorted order
        for page_number in sorted(self.pages.keys(), key=int):
            # Append the DataFrame for each page to the list
            all_dfs.append(self.pages[page_number]['search_results_df'])

        # Concatenate all DataFrames into a single DataFrame
        combined_df = pd.concat(all_dfs, ignore_index=False)

        # Format search query and taxonomy for filename
        formatted_query = self.format_for_filename(self.query)
        formatted_taxonomy = self.format_for_filename(self.taxonomy_gbif)

        # Generate a more readable timestamp
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

        # Construct the filename
        if formatted_taxonomy != 'None':
            filename = f"{formatted_query}_{formatted_taxonomy}_{timestamp}.csv"
        else:
            filename = f"{formatted_query}_{timestamp}.csv"

        # Define the file path for saving the DataFrame
        save_path = os.path.join(self.path, filename)

        # Save the DataFrame to a CSV file
        combined_df.to_csv(save_path, index=True)

        print(f"Combined DataFrame saved to {save_path}")


if __name__ == "__main__":

    print('Downloading Query Results', flush=True)
    # Extract command line arguments
    query_dict = sys.argv[1]  # Assuming JSON string as the first argument

    query_dict = json.loads(query_dict)

    try:
        searchObj = DownloadMSRecords(query=query_dict['query'], media_type=query_dict['mediaType'],
                                      taxonomy_gbif=query_dict['taxon'],
                                      openDownloadsOnly=query_dict['visibility'],
                                      media_tag=query_dict['mediaTag'],
                                      path=query_dict['download_folder'])
        searchObj.download_all_pages()
        searchObj.combine_and_save_dataframes()
    except Exception as e:
        print(f"Error initializing searchObj: {e}")
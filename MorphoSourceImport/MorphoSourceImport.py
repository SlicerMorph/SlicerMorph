import time
import json
import logging
import os
import string
import sys
import warnings
from collections import OrderedDict
from typing import Optional

import webbrowser
import requests
import threading
import concurrent.futures

import ctk
import numpy as np
import qt
import slicer
import vtk
from slicer.ScriptedLoadableModule import *

try:
    from importlib.metadata import version
except ImportError:
    from importlib_metadata import version

warnings.filterwarnings("ignore", "DataFrame.applymap has been deprecated")

#
# MorphoSourceImport
#

morphosourceVersion = "1.1.0"


def is_correct_version_installed(package, desired_version):
    try:
        installed_version = version(package)
        return installed_version == desired_version
    except Exception:
        return False


def unlist_cell(cell):
    """If the cell is a list, return the items separated by semicolons.
    If the cell is empty or None, return an empty string. Otherwise, return the cell unchanged."""
    if isinstance(cell, list):
        return " ; ".join(map(str, cell))
    elif cell is None or cell == []:
        return ""
    return cell


def download_thumbnail(url):
    try:
        response = requests.get(url)
        response.raise_for_status()  # Raises an HTTPError for bad requests
        return response.content
    except requests.exceptions.RequestException as e:
        print(f"Error fetching the thumbnail from {url}: {e}")
        return None


def download_thumbnails(urls):
    # Initialize an empty list with the same length as urls
    thumbnails = [None] * len(urls)

    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
        # Map each URL to the download_thumbnail function and store the future objects
        futures = [executor.submit(download_thumbnail, url) for url in urls]

        # Iterate over the futures in the order they were created
        for i, future in enumerate(futures):
            try:
                # Store the result in the corresponding position
                thumbnails[i] = future.result()
            except Exception as e:
                print(f"Error downloading thumbnail from {urls[i]}: {e}")

    return thumbnails


def getResourceScriptPath(scriptName):
    # Get the path of the module
    modulePath = os.path.dirname(slicer.modules.morphosourceimport.path)

    # Construct the path to the resource script
    resourceScriptPath = os.path.join(modulePath, 'Resources', scriptName)
    return resourceScriptPath


class ClickableLabel(qt.QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)

    def mousePressEvent(self, event):
        if event.button() == qt.Qt.RightButton:
            # Handle left button click
            self.showContextMenu(event.pos())
        else:
            # For other mouse events, call the default QLabel event handler
            qt.QLabel.mousePressEvent(self, event)

    def showContextMenu(self, position):
        menu = qt.QMenu()
        openAction = menu.addAction("Open in Browser")
        action = menu.exec_(self.mapToGlobal(position))
        if action == openAction:
            url = self.objectName  # Directly use the URL string
            webbrowser.open(url)  # Open the URL in the browser


class MSQuery:
    def __init__(self, query: str, media_type: str, taxonomy_gbif: str,
                 openDownloadsOnly: bool, media_tag: str = None, per_page: int = 20):
        # Attempt to import pandas, and install if not present
        try:
            import pandas as pd
        except ImportError:
            slicer.util.pip_install('pandas')
            import pandas as pd

        # Attempt to import morphosource, and install if not present
        try:
            import morphosource as ms
            from morphosource import search_media, get_media, DownloadVisibility
            from morphosource.search import SearchResults
            from morphosource.exceptions import MetadataMissingError

            # Check if MorphoSource is installed and at the correct version
            if is_correct_version_installed('morphosource', '1.1.0'):
                print("MorphoSource is already installed and at the correct version.")
            else:
                raise ImportError("MorphoSource is not installed or not the correct version.")
        except ImportError:
            # Show a dialog indicating that installation is in progress
            dependencyDialog = slicer.util.createProgressDialog(
                windowTitle="Installing...",
                labelText="Installing and Loading Required Python packages and Restarting Slicer",
                maximum=0,
            )
            slicer.app.processEvents()

            # Install the required packages
            slicer.util.pip_install('morphosource==' + morphosourceVersion)

            import morphosource as ms
            from morphosource import search_media, get_media, DownloadVisibility
            from morphosource.search import SearchResults
            from morphosource.exceptions import MetadataMissingError

            # Close the installation dialog
            dependencyDialog.close()

            # Restart 3D Slicer
            slicer.util.restart()

        self.MetadataMissingError = MetadataMissingError
        self.pd = pd
        self.ms = ms
        self.get_media = get_media
        self.search_media = search_media
        self.SearchResults = SearchResults

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
        self.current_page = None
        self.current_results = None

        # Run initial query which stores
        self.run_search(1)

    def run_search(self, page: int) -> None:
        start_time = time.time()  # Start timing
        # Check if the page has already been fetched
        if page not in self.pages:
            search_results = self.search_media(query=self.query,
                                               taxonomy_gbif=self.taxonomy_gbif,
                                               media_type=self.media_type,
                                               visibility=self.visibility,
                                               media_tag=self.media_tag,
                                               per_page=self.per_page,
                                               page=page)

            if self.total_pages is None and self.total_count is None:
                self.total_pages = int(search_results.pages['total_pages'])
                self.total_count = int(search_results.pages['total_count'])

            if self.total_count == 0:
                return

            thumbnail_urls, web_urls = self.get_urls_for_page(search_results)

            # run_search method took 9.65217113494873 seconds to execute w/ calculate_file_sizes
            file_sizes, successful_indices = self.calculate_file_sizes(search_results)

            # Filter search_results.items to include only successful media items
            search_results.items = [search_results.items[i] for i in successful_indices]

            # Filter thumbnail_urls and web_urls to include only successful media items
            thumbnail_urls = [thumbnail_urls[i] for i in successful_indices]
            web_urls = [web_urls[i] for i in successful_indices]

            thumbnails = download_thumbnails(thumbnail_urls)  # parallel requests to api, 6 workers

            # Store the search results in the ordered dictionary
            self.pages[page] = {'search_results': search_results,
                                'checked_items': [],
                                'thumbnails': thumbnails,
                                'web_urls': web_urls,
                                'sizes': file_sizes,
                                'num_records': len(search_results.items)}

            self.current_results = search_results
            self.current_page = page

        else:
            # Set the current results to the already fetched page
            self.current_results = self.pages[page]['search_results']
            self.current_page = page

        end_time = time.time()  # End timing
        elapsed_time = end_time - start_time
        print(f"run_search method took {elapsed_time} seconds to execute.")

    def get_file_size(self, media):
        try:
            size_mb = (media.get_file_metadata().file_size / 1024) / 1024
            return f"{size_mb:.2f} MB"
        except self.MetadataMissingError as e:
            print(f"Error: {e}, {media.id} excluded")
            raise  # Reraise the exception to handle it in calculate_file_sizes

    def calculate_file_sizes(self, search_results):
        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
            # Create a future for each file size calculation and store the future objects
            futures = {executor.submit(self.get_file_size, media): i for i, media in enumerate(search_results.items)}

            # Initialize a list to store file sizes
            file_sizes = []

            # Initialize a list to keep track of successful indices
            successful_indices = []

            # Iterate over the futures and process results
            for future in concurrent.futures.as_completed(futures):
                media_index = futures[future]
                try:
                    size = future.result()  # This will raise an exception if get_file_size encountered an error
                    file_sizes.append(size)
                    successful_indices.append(media_index)
                except Exception as e:
                    print(f"Error getting file size for media item at index {media_index}: {e}")

        return file_sizes, successful_indices

    def extract_dataframe(self):
        # Ensure that there are current results to process
        if self.current_results is None:
            raise ValueError("No current results to extract. Run a search first.")

        # Extracting the 'data' dictionaries from each item in search_results
        search_results_data = [item.data for item in self.current_results.items]

        # Converting the list of dictionaries to a pandas DataFrame
        search_results_df = self.pd.DataFrame(search_results_data).applymap(unlist_cell)

        search_results_df = self.revise_df(search_results_df)

        search_results_df['File size'] = self.pages[1]['sizes']

        return search_results_df

    def revise_df(self, df):

        revised_df = df[['id', 'title', 'media_type', 'physical_object_id',
                         'part', 'side', 'date_modified',
                         'physical_object_taxonomy_name', 'physical_object_taxonomy_gbif',
                         'x_pixel_spacing', 'y_pixel_spacing', 'z_pixel_spacing']]

        revised_colnames = ['Media ID', 'Title', 'Media Type', 'Object ID',
                            'Part', 'Side', 'Date Modified',
                            'Taxonomy Name', 'Taxonomy GBIF',
                            'X Pixel Spacing', 'Y Pixel Spacing', 'Z Pixel Spacing']

        revised_df.columns = revised_colnames

        return revised_df

    def get_urls_for_page(self, search_results):
        thumbnail_urls = []
        web_urls = []
        for media in search_results.items:
            thumbnail_urls.append(media.get_thumbnail_url())
            web_urls.append(media.get_website_url())

        return thumbnail_urls, web_urls

    def get_dataframe_with_updated_index(self, page_number):
        """
        Updates the index of the current DataFrame based on the page number
        and the number of records per page.
        """
        if self.current_results is None:
            raise ValueError("No current results to extract. Run a search first.")

        # Calculate the start index for the current page
        # Assuming page_number is the current page you're interested in
        # Get all 'num_records' values up to the current page
        num_records_values = [self.pages[i]['num_records'] for i in range(1, page_number)]

        # Sum up the values and add 1 to get the start_index
        start_index = sum(num_records_values)

        # Extracting the 'data' dictionaries from each item in search_results
        search_results_data = [item.data for item in self.current_results.items]

        # Converting the list of dictionaries to a pandas DataFrame
        search_results_df = self.pd.DataFrame(search_results_data)

        # Update the DataFrame index to reflect the current page
        search_results_df.index = range(start_index, start_index + len(search_results_df))

        # Apply the unlist_cell function to each cell in the DataFrame
        search_results_df = search_results_df.applymap(unlist_cell)

        search_results_df = self.revise_df(search_results_df)

        search_results_df['File size'] = self.pages[page_number]['sizes']

        return search_results_df

    def get_all_checked_items(self):
        """Fetches checked items from all pages and returns them as a list of strings."""
        all_checked_items = []
        for page in self.pages.values():
            checked_items = page.get('checked_items', [])
            all_checked_items.extend(checked_items)
        return all_checked_items


class MorphoSourceImport(ScriptedLoadableModule):
    """Uses ScriptedLoadableModule base class, available at:
    https://github.com/Slicer/Slicer/blob/main/Base/Python/slicer/ScriptedLoadableModule.py
    """

    def __init__(self, parent):
        ScriptedLoadableModule.__init__(self, parent)
        self.parent.title = "MorphoSourceImport"
        self.parent.categories = ["SlicerMorph.Input and Output"]
        self.parent.dependencies = []
        self.parent.contributors = ["Murat Maga (UW), Sara Rolfe (SCRI), Oshane Thomas(SCRI)"]
        self.parent.helpText = """This module provides a streamlined interface for querying MorphoSource database to search and retrieve dataset. For more information see  <a href=https://github.com/SlicerMorph/Tutorials/tree/master/MorphoSourceImport> the tutorial </A>."""
        self.parent.acknowledgementText = """This module was developed by Oshane Thomas for SlicerMorph with input from Julie Winchester (MorphoSource) and is based on the pyMorphoSource package by John Bradley (Imageomics Institute). The development of the module was supported by NSF/OAC grant, "HDR Institute: Imageomics: A New Frontier of Biological Information Powered by Knowledge-Guided Machine Learnings" (Award #2118240). A previous version of this module was developed by Arthur Porto (UFL) and Sara Rolfe (SCRI) with funding from NSF/DBI ABI-1759883"""


#
# MorphoSourceImportWidget
#

class MorphoSourceImportWidget(ScriptedLoadableModuleWidget):
    def __init__(self, parent=None) -> None:
        ScriptedLoadableModuleWidget.__init__(self, parent)

        self.startSearchButton = None
        self.all_pages = None
        self.searchProcess = None
        self.searchProgressBar = None
        self.downloadInProgress = None
        self.total_downloads = None
        self.completed_downloads = None
        self.progressBar = None
        self.selectDownloadFolderButton = None
        self.downloadFolderPathInput = None
        self.downloadButton = None
        self.intendedUseStatementInput = None
        self.setAPIKeyButton = None
        self.toggleAPIKeyVisibilityButton = None
        self.apiKeyInput = None
        self.pageNavigationLayout = None
        self.pageNumberEdit = None
        self.nextPageButton = None
        self.previousPageButton = None
        self.resultsTable = None
        self.submitQueryButton = None
        self.openDatasetsCheckbox = None
        self.ctImageSeriesRadioButton = None
        self.meshRadioButton = None
        self.taxonInput = None
        self.mediaTag = None
        self.elementInput = None
        self.usageCategoryCheckboxes = None

        self.downloadProcess = None  # Add this line to store the subprocess reference
        self.logic = MorphoSourceImportLogic()

    def setup(self) -> None:
        ScriptedLoadableModuleWidget.setup(self)

        self.load_dependencies()

        parametersCollapsibleButton = ctk.ctkCollapsibleButton()
        parametersCollapsibleButton.text = "MorphoSource Query Parameters"
        self.layout.addWidget(parametersCollapsibleButton)

        parametersFormLayout = qt.QFormLayout(parametersCollapsibleButton)

        self.elementInput = qt.QLineEdit()
        self.elementInput.setPlaceholderText("Input your search query, e.g., 'Skull')")
        parametersFormLayout.addRow("Query Keyword:", self.elementInput)

        # Create a new QLineEdit for the "Taxon" category input
        self.taxonInput = qt.QLineEdit()
        self.taxonInput.setPlaceholderText("Enter taxon for search query (optional) e.g., 'Primates'")
        parametersFormLayout.addRow("Taxon:", self.taxonInput)

        self.mediaTag = qt.QLineEdit()
        self.mediaTag.setPlaceholderText("Enter a media tag (optional), e.g., 'Pleistocene' ")
        parametersFormLayout.addRow("Media Tag: ", self.mediaTag)

        # Change checkboxes to radio buttons
        self.meshRadioButton = qt.QRadioButton("Mesh")
        self.ctImageSeriesRadioButton = qt.QRadioButton("CT Image Series")

        # Arrange radio buttons in a horizontal layout
        dataTypeLayout = qt.QHBoxLayout()
        dataTypeLayout.addWidget(self.meshRadioButton)
        dataTypeLayout.addWidget(self.ctImageSeriesRadioButton)

        # Create the Open Datasets Only checkbox
        self.openDatasetsCheckbox = qt.QCheckBox("Open Access Datasets Only")

        # Add to the layout
        dataTypeLayout = qt.QHBoxLayout()
        dataTypeLayout.addWidget(self.meshRadioButton)
        dataTypeLayout.addWidget(self.ctImageSeriesRadioButton)
        dataTypeLayout.addStretch(6)  # Add stretch before the separator
        dataTypeLayout.addWidget(self.openDatasetsCheckbox)

        # Add the horizontal layout to the form layout
        parametersFormLayout.addRow("Data Types:", dataTypeLayout)

        self.openDatasetsCheckbox.toggled.connect(self.logic.setOpenDatasetsOnly)

        # Folder selection button and text field
        self.downloadFolderPathInput = qt.QLineEdit()
        self.downloadFolderPathInput.setReadOnly(True)  # Make the field read-only
        self.selectDownloadFolderButton = qt.QPushButton("Select Download Folder")
        self.selectDownloadFolderButton.clicked.connect(self.onSelectDownloadFolder)

        # Layout for download folder selection
        downloadFolderLayout = qt.QHBoxLayout()
        downloadFolderLayout.addWidget(self.downloadFolderPathInput)
        downloadFolderLayout.addWidget(self.selectDownloadFolderButton)

        # Add the layout to the widget
        parametersFormLayout.addRow(downloadFolderLayout)

        self.submitQueryButton = qt.QPushButton("Submit Query")
        self.submitQueryButton.toolTip = "Query the MorphoSource database for 3D models. This may take a few minutes."
        self.submitQueryButton.enabled = False
        parametersFormLayout.addRow(self.submitQueryButton)

        # Connections
        self.elementInput.connect('textChanged(const QString &)', self.onQueryStringChanged)
        self.mediaTag.connect('textChanged(const QString &)', self.onQueryStringChanged)

        self.meshRadioButton.toggled.connect(self.onQueryStringChanged)
        self.ctImageSeriesRadioButton.toggled.connect(self.onQueryStringChanged)

        self.submitQueryButton.connect('clicked(bool)', self.onSubmitQuery)

        spacer = qt.QSpacerItem(0, 0, qt.QSizePolicy.Minimum, qt.QSizePolicy.Expanding)
        self.layout.addItem(spacer)

        # Add table to layout
        self.createBasicTable(rowHeight=30)

        # Add page navigation buttons below the results table
        self.previousPageButton = qt.QPushButton("Previous Page")
        self.nextPageButton = qt.QPushButton("Next Page")
        self.nextPageButton.setToolTip("Go to the next page of results.")
        self.nextPageButton.enabled = False  # Disable the button initially
        self.pageNumberEdit = qt.QLineEdit("1")  # Start at page 1
        # Set initial UI element for page display as "1/1" for a new search
        self.pageNumberEdit.setText("1 / 1")  # Set as "1/1" initially
        self.pageNumberEdit.setValidator(qt.QIntValidator(1, 10000))  # Assume a max of 10000 pages for now
        self.pageNumberEdit.setMaximumWidth(200)  # Set a fixed width that's just enough for 4 digits
        self.pageNumberEdit.setAlignment(qt.Qt.AlignCenter)  # Center the text inside QLineEdit

        self.pageNavigationLayout = qt.QHBoxLayout()
        self.pageNavigationLayout.addWidget(self.previousPageButton)
        self.pageNavigationLayout.addWidget(self.pageNumberEdit)
        self.pageNavigationLayout.addWidget(self.nextPageButton)
        self.layout.addLayout(self.pageNavigationLayout)

        # Disable the previous page button initially
        self.previousPageButton.setEnabled(False)

        # Connect the buttons to their respective slot functions
        self.previousPageButton.clicked.connect(self.onPreviousPageClicked)
        self.nextPageButton.clicked.connect(self.onNextPageClicked)
        self.pageNumberEdit.editingFinished.connect(self.onPageNumberChanged)

        # Create a new button for starting the search
        self.startSearchButton = qt.QPushButton("Download Query Results")
        self.startSearchButton.toolTip = "Click to download all query results as .csv"
        self.startSearchButton.setEnabled(False)

        # Layout to add the button
        layout = qt.QVBoxLayout()
        layout.addWidget(self.startSearchButton)
        self.layout.addLayout(layout)

        # Connect the button to the method
        self.startSearchButton.connect('clicked(bool)', self.startSearchProcess)

        # Existing API Key input field setup
        self.apiKeyInput = qt.QLineEdit()
        self.apiKeyInput.setPlaceholderText("Enter your public API key here")
        self.apiKeyInput.setEchoMode(qt.QLineEdit.Password)  # Start with hidden API key

        # Add a button to toggle the visibility of the API key
        self.toggleAPIKeyVisibilityButton = qt.QPushButton("Show")
        self.toggleAPIKeyVisibilityButton.setCheckable(True)  # Make it checkable
        self.toggleAPIKeyVisibilityButton.setToolTip("Toggle API key visibility")

        # Arrange API key input and toggle button in a horizontal layout
        apiKeyLayout = qt.QHBoxLayout()
        apiKeyLayout.addWidget(self.apiKeyInput)
        apiKeyLayout.addWidget(self.toggleAPIKeyVisibilityButton)
        apiKeyWidget = qt.QWidget()
        apiKeyWidget.setLayout(apiKeyLayout)
        self.layout.addWidget(apiKeyWidget)

        # Connections for the API Key and its visibility toggle
        self.toggleAPIKeyVisibilityButton.clicked.connect(self.toggleAPIKeyVisibility)

        # Add button for setting the API key
        self.setAPIKeyButton = qt.QPushButton("Set API Key")
        self.setAPIKeyButton.setToolTip("Set the API key for MorphoSource.")
        self.setAPIKeyButton.clicked.connect(self.onSetAPIKey)  # Connect the button to the respective method
        self.layout.addWidget(self.setAPIKeyButton)

        # add text field for entering intended usage
        self.intendedUseStatementInput = qt.QTextEdit()
        self.intendedUseStatementInput.setPlaceholderText("Enter your intended use statement here...")

        # Set the maximum height to make the QTextEdit box smaller
        self.intendedUseStatementInput.setMaximumHeight(60)  # You can adjust the value 100 to your preference
        self.layout.addWidget(self.intendedUseStatementInput)
        self.intendedUseStatementInput.textChanged.connect(self.checkDownloadButtonState)

        # Collapsible button for Usage Categories
        usageCategoryCollapsibleButton = ctk.ctkCollapsibleButton()
        usageCategoryCollapsibleButton.text = "Choose (at least one) appropriate usage categories"
        self.layout.addWidget(usageCategoryCollapsibleButton)

        # Grid layout for usage categories
        usageCategoryLayout = qt.QGridLayout(usageCategoryCollapsibleButton)

        # List of usage categories
        usageCategories = [
            "Completing Class Assignment(s) (Grades K-6)",
            "Completing Class Assignment(s) (Grades 7-12)",
            "Completing Class Assignment(s) (University or Post-Secondary)",
            "Completing Class Assignment(s) (Post-Graduate)",
            "Educator Resource (Grades K-6)",
            "Educator Resource (Grades 7-12)",
            "Educator Resource (University or Post-Secondary)",
            "Educator Resource (Post-Graduate)",
            "Public Outreach (Museums, Documentaries, Etc)",
            "Art",
            "Personal Interest",
            "3D Printing",
            "Commercial Use"
        ]

        # Create checkboxes for each category and add them to the grid layout
        self.usageCategoryCheckboxes = {}
        for i, category in enumerate(usageCategories):
            checkbox = qt.QCheckBox(category)

            # Set a smaller font size using a style sheet
            checkbox.setStyleSheet("QCheckBox { font-size: 9pt; }")  # Adjust the font size as needed

            col = i % 2  # Determine the column (0 or 1)
            row = i // 2  # Determine the row
            usageCategoryLayout.addWidget(checkbox, row, col)
            self.usageCategoryCheckboxes[category] = checkbox

        for checkbox in self.usageCategoryCheckboxes.values():
            checkbox.stateChanged.connect(self.checkDownloadButtonState)

        # Load saved settings and update the input fields
        savedApiKey = self.logic.loadSetting('apiKey', '')
        self.apiKeyInput.text = savedApiKey

        savedDownloadFolder = self.logic.loadSetting('downloadFolder', '')
        self.downloadFolderPathInput.text = savedDownloadFolder

        # Add download button below the table
        self.downloadButton = qt.QPushButton("Download Checked Items")
        self.downloadButton.clicked.connect(self.downloadCheckedItems)
        self.downloadButton.setEnabled(False)  # Initially disabled
        self.layout.addWidget(self.downloadButton)

        # Create the progress bar
        self.progressBar = qt.QProgressBar()
        self.progressBar.setRange(0, 100)  # Assuming 0-100% progress
        self.progressBar.setVisible(False)  # Initially hidden
        self.layout.addWidget(self.progressBar)

        self.layout.addStretch(1)
        self.onQueryStringChanged()

    def cleanup(self) -> None:
        pass

    def set_title(self) -> None:  # Unused: Not within slicer style guidelines
        moduleNameLabel = qt.QLabel("MorphoSource Import")
        moduleNameLabel.setAlignment(qt.Qt.AlignCenter)
        moduleNameLabel.setStyleSheet("font-weight: bold; font-size: 18px; padding: 10px;")
        self.layout.addWidget(moduleNameLabel)

    def createBasicTable(self, rowHeight) -> None:
        # Table for search results
        self.resultsTable = qt.QTableWidget()

        # Adjust this based on your row height
        self.resultsTable.setMinimumHeight(rowHeight * 10)

        # Adjust the size policy to expand
        sizePolicy = qt.QSizePolicy(qt.QSizePolicy.Expanding, qt.QSizePolicy.Expanding)
        self.resultsTable.setSizePolicy(sizePolicy)

        # Add the results table to the layout
        self.layout.addWidget(self.resultsTable)

    def onQueryStringChanged(self):
        selectedRadio = self.meshRadioButton.isChecked() or \
                        self.ctImageSeriesRadioButton.isChecked()

        # Check only the elementInput for activation.
        self.submitQueryButton.enabled = bool(self.elementInput.text) and selectedRadio

    def onSubmitQuery(self):

        selectedDataType = None
        if self.meshRadioButton.isChecked():
            selectedDataType = "Mesh"
        elif self.ctImageSeriesRadioButton.isChecked():
            selectedDataType = "CT Image Series"

        tagText = self.mediaTag.text if self.mediaTag.text.strip() else None

        # Check if there is text in the taxon input and add it to the dictionary
        taxonText = self.taxonInput.text if self.taxonInput.text.strip() else None

        # taxonText = taxonText[0].upper() + taxonText[1:]  # Make first character uppercase

        queryDictionary = {
            "query": self.elementInput.text,
            "mediaTag": tagText,
            "mediaType": selectedDataType,
            "taxon": taxonText  # Add the taxon text to the query dictionary
        }

        # Note: This overwrites and creates a new MSQuery Object
        self.logic.runNewQuery(queryDictionary)

        if self.logic.msq.total_count == 0:
            self.resultsTable.clearContents()
            self.checkDownloadButtonState()
            self.startSearchButton.setEnabled(False)
            slicer.util.infoDisplay("Your search did not return any results.", windowTitle="No Results Found")
            return

        else:
            page_one_results_df = self.logic.msq.extract_dataframe()

            # Update the table with search results
            self.updateResultsTable(page_one_results_df,
                                    self.logic.msq.pages[1]['thumbnails'],
                                    self.logic.msq.pages[1]['web_urls'])

            self.startSearchButton.setEnabled(True)

            self.pageNumberEdit.setText(f"1 / {self.logic.msq.total_pages}")

            self.checkPageButtonsState()

            return

    def startSearchProcess(self):
        # Prepare query dictionary
        selectedDataType = None
        if self.meshRadioButton.isChecked():
            selectedDataType = "Mesh"
        elif self.ctImageSeriesRadioButton.isChecked():
            selectedDataType = "CT Image Series"

        tagText = self.mediaTag.text if self.mediaTag.text.strip() else None

        # Check if there is text in the taxon input and add it to the dictionary
        taxonText = self.taxonInput.text if self.taxonInput.text.strip() else None

        queryDictionary = {
            "query": self.elementInput.text,
            "mediaTag": tagText,
            "mediaType": selectedDataType,
            "visibility": self.logic.openDatasetsOnly,  # add visibility
            "taxon": taxonText,  # Add the taxon text to the query dictionary
            'download_folder': self.logic.download_folder
        }

        self.searchProcess = qt.QProcess()
        self.searchProcess.readyReadStandardOutput.connect(self.onSearchProcessReadyRead)
        self.searchProcess.errorOccurred.connect(self.onSearchProcessError)

        # Prepare the command to start the download process
        command = sys.executable
        scriptPath = getResourceScriptPath('download_csv.py')

        query_json_dict = json.dumps(queryDictionary)  # Convert config to JSON string
        args = [scriptPath, query_json_dict]

        self.startDownload()
        # Start the download process
        self.searchProcess.start(command, args)

        # Assume progressBar is a member of the class and is a QProgressBar
        self.searchProgressBar = slicer.util.createProgressDialog()

    def onSearchProcessReadyRead(self):
        # Read the standard output of the search process
        output = self.searchProcess.readAllStandardOutput().data().decode("utf-8")

        # Split the output by newlines to get individual lines
        lines = output.split('\n')

        # Iterate through each line
        for line in lines:
            if line.startswith("PROGRESS:"):
                # Extract the progress value after the "PROGRESS:" prefix
                try:
                    progress_value = float(line.split(':')[1])
                    self.updateSearchProgressBar(progress_value)
                except ValueError as e:
                    # Handle any errors during conversion
                    print(f"Error converting progress to float: {e}")

            elif line.startswith("{"):  # Assuming JSON data starts with '{'
                self.all_pages = json.loads(line)
                # Process the final data
            else:
                print('output:', line)

    def updateSearchProgressBar(self, value):
        # Update the progress bar in the Slicer GUI
        self.searchProgressBar.setValue(value)

    def onSearchProcessError(self, error):
        if error == qt.QProcess.FailedToStart:
            print("Process failed to start.")
        elif error == qt.QProcess.Crashed:
            print("Process crashed.")
        elif error == qt.QProcess.Timedout:
            print("Process timeout.")
        elif error == qt.QProcess.WriteError:
            print("Process write error.")
        elif error == qt.QProcess.ReadError:
            print("Process read error.")
        else:
            print("An unknown error occurred.")

    # Method to populate the QTableWidget
    def updateResultsTable(self, df, thumbnails, web_urls):
        currentPage = self.logic.msq.current_page
        checkedItems = self.logic.msq.pages.get(currentPage, {}).get('checked_items', [])

        start_index = (currentPage - 1) * self.logic.msq.per_page

        self.resultsTable.clearContents()
        self.resultsTable.setRowCount(df.shape[0])
        self.resultsTable.setColumnCount(df.shape[1] + 2)  # +2 for the checkbox and thumbnail columns

        headers = [" ", "Image"] + [str(col).capitalize() for col in df.columns]
        self.resultsTable.setHorizontalHeaderLabels(headers)
        self.resultsTable.setVerticalHeaderLabels([str(i + 1) for i in df.index])

        # Set font size for table items
        font = qt.QFont()
        font.setPointSize(12)  # Adjust this size as needed
        self.resultsTable.setFont(font)

        # Set stylesheet for the header view to match the font size
        header = self.resultsTable.horizontalHeader()
        header.setStyleSheet(
            "QHeaderView::section { font-size: 12pt; }")  # Match the font size with the table's row text

        for row_index, row_data in df.iterrows():
            adjusted_row_index = row_index - start_index
            itemId = str(row_data.iloc[0])

            # Set up the checkbox
            checkbox = qt.QCheckBox()
            checkbox.stateChanged.connect(self.checkDownloadButtonState)
            checkbox.setChecked(itemId in checkedItems)
            checkbox.stateChanged.connect(lambda state, row=adjusted_row_index: self.onCheckboxStateChanged(state, row))
            self.resultsTable.setCellWidget(adjusted_row_index, 0, self.createCenteredWidget(checkbox))

            # Handle thumbnail display
            # print('currentPage:', currentPage, '| row_index:', row_index, '| adjusted_row_index:', adjusted_row_index)
            thumbnail = thumbnails[adjusted_row_index]
            web_url = web_urls[adjusted_row_index]
            label = ClickableLabel()
            label.setObjectName(web_url)
            if thumbnail:
                pixmap = qt.QPixmap()
                pixmap.loadFromData(thumbnail)
                scaledPixmap = pixmap.scaled(50, 50, qt.Qt.KeepAspectRatio)
                label.setPixmap(scaledPixmap)
                rowHeight = scaledPixmap.height()
                self.resultsTable.setRowHeight(adjusted_row_index, rowHeight)
            else:
                label.setText("No Image")
            self.resultsTable.setCellWidget(adjusted_row_index, 1, label)

            # Add a hidden QTableWidgetItem to store item ID
            itemIDWidget = qt.QTableWidgetItem(itemId)
            self.resultsTable.setItem(adjusted_row_index, 2, itemIDWidget)

            # Populate other columns
            for col_index, item in enumerate(row_data):
                cellItem = qt.QTableWidgetItem(str(item))
                cellItem.setFlags(cellItem.flags() ^ qt.Qt.ItemIsEditable)
                self.resultsTable.setItem(adjusted_row_index, col_index + 2, cellItem)

            self.resultsTable.setColumnWidth(0, 50)  # Width for the checkbox column
            self.resultsTable.setColumnWidth(1, 50)  # Width for the thumbnail column

    def createCenteredWidget(self, widget):
        cell_widget = qt.QWidget()
        layout = qt.QHBoxLayout(cell_widget)
        layout.addWidget(widget)
        layout.setAlignment(qt.Qt.AlignCenter)
        layout.setContentsMargins(0, 0, 0, 0)
        cell_widget.setLayout(layout)
        return cell_widget

    def connectCheckboxSignal(self, checkbox, row):
        def on_state_changed(state):
            self.onCheckboxStateChanged(state, row)

        checkbox.stateChanged.connect(on_state_changed)

    def onCheckboxStateChanged(self, state, row):
        currentPage = self.logic.msq.current_page

        # Retrieve the item ID from the hidden QTableWidgetItem
        itemId = self.resultsTable.item(row, 2).text()

        # Add or remove the item from the checked_items list
        if state == qt.Qt.Checked:
            if itemId not in self.logic.msq.pages[currentPage]['checked_items']:
                self.logic.msq.pages[currentPage]['checked_items'].append(itemId)
        elif state == qt.Qt.Unchecked:
            if itemId in self.logic.msq.pages[currentPage]['checked_items']:
                self.logic.msq.pages[currentPage]['checked_items'].remove(itemId)

    def onPreviousPageClicked(self):
        # Extract the current page number from the text
        current_page_text = self.pageNumberEdit.text.split('/')[0]
        current_page = int(current_page_text)

        # Decrement the current page number
        current_page -= 1

        # Update the pageNumberEdit text with the new page number and total pages
        if self.logic.msq:
            self.pageNumberEdit.setText(f"{current_page} / {self.logic.msq.total_pages}")

            # Call the method to update the results for the new page number
            self.updateResultsForPage(current_page)

    def onNextPageClicked(self):
        # Extract the current page number from the text
        current_page_text = self.pageNumberEdit.text.split('/')[0].strip()
        current_page = int(current_page_text)

        # Increment the current page number
        current_page += 1

        # Update the pageNumberEdit text with the new page number and total pages
        if self.logic.msq:
            self.pageNumberEdit.setText(f"{current_page} / {self.logic.msq.total_pages}")

            # Call the method to update the results for the new page number
            self.updateResultsForPage(current_page)

    def onPageNumberChanged(self):
        if self.logic.msq:
            current_page = int(self.pageNumberEdit.text.split('/')[0].strip())
            self.updateResultsForPage(current_page)

    def checkPageButtonsState(self):
        """
        Enable or disable the previous and next page buttons based on the current page and the total pages available.
        """
        if self.logic.msq:  # Ensure the MSQuery object exists
            total_pages = self.logic.msq.total_pages
            current_page_text = self.pageNumberEdit.text.split('/')[0].strip()  # Split the text and take the first part
            current_page = int(current_page_text)  # Convert the current page number to an integer

            # Disable the next page button if there's only one page or we're on the last page
            self.nextPageButton.setEnabled(current_page < total_pages)

            # Disable the previous page button if we're on the first page
            self.previousPageButton.setEnabled(current_page > 1)

    def updateResultsForPage(self, page_number):

        # Call the logic to update the results for the specified page
        self.logic.runQueryForPage(page_number)

        if self.logic.msq.total_count == 0:
            self.resultsTable.clearContents()
            self.checkDownloadButtonState()
            self.startSearchButton.setEnabled(False)
            slicer.util.infoDisplay("Your search did not return any results.", windowTitle="No Results Found")
            return

        else:
            # Extract the data for the new page
            results_df = self.logic.msq.get_dataframe_with_updated_index(page_number)

            # Update the results table with the new data
            self.updateResultsTable(results_df, self.logic.msq.pages[page_number]['thumbnails'],
                                    self.logic.msq.pages[page_number]['web_urls'])

            # Check if total_pages is available and update the pageNumberEdit
            if self.logic.msq and self.logic.msq.total_pages is not None:
                self.pageNumberEdit.setText(f"{page_number} / {self.logic.msq.total_pages}")
            else:
                self.pageNumberEdit.setText(f"{page_number} / 1")  # Default to "1" if total_pages is not known

            self.checkPageButtonsState()

            # Enable or disable the previous and next buttons as necessaryssss
            self.previousPageButton.setEnabled(page_number > 1)
            self.nextPageButton.setEnabled(page_number < self.logic.msq.total_pages)

            return

    def checkDownloadButtonState(self):
        try:
            apiKey = self.apiKeyInput.text.strip()

            intendedUseStatement = self.intendedUseStatementInput.toPlainText().strip()

            # Check if at least one usage category is selected
            atLeastOneCategorySelected = any(checkbox.isChecked() for checkbox in self.usageCategoryCheckboxes.values())

            # Check if a download folder is chosen
            downloadFolderChosen = bool(self.downloadFolderPathInput.text)

            # Check if any items have been checked across all pages
            anyItemsChecked = any(self.logic.msq.pages[page]['checked_items'] for page in self.logic.msq.pages)

            # Conditions to enable the download button
            enableDownloadButton = (
                    apiKey and
                    len(intendedUseStatement) >= 50 and
                    atLeastOneCategorySelected and
                    downloadFolderChosen and
                    anyItemsChecked
            )

            self.downloadButton.setEnabled(enableDownloadButton)

        except Exception as e:
            print("Error occurred:", str(e))

    def onSetAPIKey(self):
        apiKey = self.apiKeyInput.text.strip()
        if apiKey:  # If there is a non-empty apiKey
            # Here, you would typically save or use this apiKey for API requests.
            self.logic.setAPIKey(apiKey)  # This assumes you have a setAPIKey method in your logic class.
            self.checkDownloadButtonState()  # Check the state of checkboxes in the table after setting API key.
        else:
            # Optionally, show a warning if the entered key seems empty
            qt.QMessageBox.warning(self, "Invalid API Key", "Please enter a valid API key.")

    def toggleAPIKeyVisibility(self, checked):
        if checked:
            self.apiKeyInput.setEchoMode(qt.QLineEdit.Normal)
            self.toggleAPIKeyVisibilityButton.setText("Hide")
        else:
            self.apiKeyInput.setEchoMode(qt.QLineEdit.Password)
            self.toggleAPIKeyVisibilityButton.setText("Show")

    def onSelectDownloadFolder(self):
        folderPath = qt.QFileDialog.getExistingDirectory()
        if folderPath:
            self.downloadFolderPathInput.setText(folderPath)
            self.logic.set_download_folder(folderPath)
            self.checkDownloadButtonState()

    def prepareDownloadConfig(self):
        # Set the intended use statement

        intendedUseStatement = self.intendedUseStatementInput.toPlainText().strip()

        # Check the length of the intended use statement
        if len(intendedUseStatement) < 50:
            msgBox = qt.QMessageBox()
            msgBox.setIcon(qt.QMessageBox.Warning)
            msgBox.setWindowTitle("Invalid Usage Statement")
            msgBox.setText("Please enter a usage statement of at least 50 characters before downloading.")
            msgBox.setStandardButtons(qt.QMessageBox.Ok)
            msgBox.exec_()
            return

        # Initialize a list to hold the checked categories
        checkedCategories = []

        # Iterate through the checkboxes and collect the checked ones
        for category, checkbox in self.usageCategoryCheckboxes.items():
            if checkbox.isChecked():
                checkedCategories.append(category)

        _config_dict = {'usage_statement': intendedUseStatement, 'usage_categories': checkedCategories,
                        'api_key': self.apiKeyInput.text, 'checked_items': self.logic.msq.get_all_checked_items(),
                        'download_folder': self.logic.download_folder}

        # Create a new list for items to be downloaded after checking for existing files
        itemsToDownload = []

        # Iterate through the items to be downloaded and check if they exist
        for item in self.logic.msq.get_all_checked_items():
            filename = f"media_{item}.zip"
            filePath = os.path.join(self.logic.download_folder, filename)  # Construct the file path
            if os.path.exists(filePath):  # Check if file exists
                # Ask the user whether to overwrite or skip the file
                userChoice = self.promptUserForFileOverwrite(filename)
                if userChoice == 'overwrite':
                    itemsToDownload.append(item)  # Add to download list if user chooses to overwrite
            else:
                itemsToDownload.append(item)  # File does not exist, add to download list

        # Update the config dictionary with the revised list of items to download
        _config_dict['checked_items'] = itemsToDownload

        self.total_downloads = len(itemsToDownload)
        self.completed_downloads = 0

        return _config_dict

    def promptUserForFileOverwrite(self, fileName):
        msgBox = qt.QMessageBox()
        msgBox.setIcon(qt.QMessageBox.Question)
        msgBox.setWindowTitle("File Exists")
        msgBox.setText(f"The file '{fileName}' already exists. Do you want to overwrite it?")
        overwriteButton = msgBox.addButton("Overwrite", qt.QMessageBox.AcceptRole)
        skipButton = msgBox.addButton("Skip", qt.QMessageBox.RejectRole)
        msgBox.exec_()

        if msgBox.clickedButton() == overwriteButton:
            return 'overwrite'
        else:
            return 'skip'

    def downloadCheckedItems(self):
        _config_dict = self.prepareDownloadConfig()

        # Disable buttons
        self.disableButtons()

        # Initialize QProcess
        self.downloadProcess = qt.QProcess()

        self.downloadProcess.started.connect(self.onDownloadStarted)
        self.downloadProcess.readyReadStandardOutput.connect(self.onDownloadOutput)
        self.downloadProcess.readyReadStandardError.connect(self.onDownloadError)
        self.downloadProcess.finished.connect(self.onDownloadFinished)

        # Prepare the command to start the download process
        command = sys.executable
        scriptPath = getResourceScriptPath('download_items.py')

        config_json_dict = json.dumps(_config_dict)  # Convert config to JSON string
        args = [scriptPath, config_json_dict]

        self.startDownload()
        # Start the download process
        self.downloadProcess.start(command, args)

        # Show progress bar and update UI
        self.progressBar.setVisible(True)

    def disableButtons(self):
        # Disable buttons during download
        self.submitQueryButton.setEnabled(False)
        self.setAPIKeyButton.setEnabled(False)
        self.selectDownloadFolderButton.setEnabled(False)
        self.downloadButton.setEnabled(False)

    def enableButtons(self):
        # Enable buttons after download
        self.submitQueryButton.setEnabled(True)
        self.setAPIKeyButton.setEnabled(True)
        self.selectDownloadFolderButton.setEnabled(True)
        self.downloadButton.setEnabled(True)

    def stopDownload(self):
        if self.downloadProcess is not None and self.downloadProcess.state() != qt.QProcess.NotRunning:
            self.downloadProcess.terminate()  # Or use kill() if terminate() is not effective

    def onDownloadStarted(self):
        print("Download process started.")

    def updateProgressBar(self, progress, downloaded_mb=None, total_mb=None):
        # Convert floating-point progress to an integer percentage
        percentage = int(float(progress))
        self.progressBar.setValue(percentage)

        # Format the text to display on the progress bar
        if downloaded_mb is not None and total_mb is not None:
            progress_text = f"{percentage}% ({downloaded_mb:.2f} MB / {total_mb:.2f} MB)"
        else:
            progress_text = f"{percentage}%"

        self.progressBar.setFormat(progress_text)

    def onDownloadOutput(self):
        output = self.downloadProcess.readAllStandardOutput().data().decode("utf-8", errors='ignore').strip()
        output_lines = output.split('\n')

        for line in output_lines:
            if "Download Progress" in line:
                # Extract the progress value and update the progress bar for each line
                progress_parts = line.split(',')
                progress_value = progress_parts[0].split(': ')[1].strip().rstrip('%')
                downloaded_mb = float(progress_parts[1].strip().split(' ')[0])
                total_mb = float(progress_parts[1].strip().split(' ')[3])

                self.updateProgressBar(progress_value, downloaded_mb, total_mb)

            elif "Completed" in line:
                print(line)

            else:
                continue

    def onDownloadError(self):
        error = self.downloadProcess.readAllStandardError().data().decode("utf-8").strip()
        print("Download Error:", error)

    def onDownloadFinished(self, exitCode):
        # Handle completion of the download process
        self.progressBar.setVisible(False)
        self.enableButtons()
        print(f"Download process finished with exit code {exitCode}")

    def startDownload(self):
        # Call this method when the download starts
        self.downloadInProgress = True

    def terminateDownload(self):
        # Implement this method to terminate the download
        self.downloadInProgress = False
        self.downloadProcess.terminate()

    def load_dependencies(self):
        # Attempt to import pandas, and install if not present
        try:
            import pandas as pd
        except ImportError:
            slicer.util.pip_install('pandas')
            import pandas as pd

        # Attempt to import morphosource, and install if not present
        try:
            from morphosource import search_media, get_media, DownloadVisibility
            from morphosource.search import SearchResults

            # Check if MorphoSource is installed and at the correct version
            if is_correct_version_installed('morphosource', '1.1.0'):
                print("MorphoSource is already installed and at the correct version.")
            else:
                raise ImportError("MorphoSource is not installed or not the correct version.")
        except ImportError:
            # Show a dialog indicating that installation is in progress
            dependencyDialog = slicer.util.createProgressDialog(
                windowTitle="Installing...",
                labelText="Installing and Loading Required Python packages",
                maximum=0,
            )
            slicer.app.processEvents()

            # Install the required packages
            slicer.util.pip_install('morphosource==' + morphosourceVersion)

            from morphosource import search_media, get_media, DownloadVisibility
            from morphosource.search import SearchResults

            # Close the installation dialog
            dependencyDialog.close()

            # Ask user to restart 3D Slicer
            restart = slicer.util.confirmYesNoDisplay(
                "MorphoSourceImport has been installed. To apply changes, a restart of 3D Slicer is necessary. "
                "Would you like to restart now? Click 'YES' to restart immediately or 'NO' if you wish to save your work first and restart manually later.")

            if restart:
                slicer.util.restart()


#
# MorphoSourceImportLogic
#
class MorphoSourceImportLogic(ScriptedLoadableModuleLogic):
    def __init__(self) -> None:
        ScriptedLoadableModuleLogic.__init__(self)

        self.download_folder = None
        self.api_key = None
        self.msq: Optional[MSQuery] = None

        # self.api_key = None
        self.openDatasetsOnly = False

        # Load settings when the module logic is initialized
        self.download_folder = self.loadSetting('downloadFolder', '')
        self.api_key = self.loadSetting('apiKey', '')

    def runNewQuery(self, dictionary) -> None:
        """
        Run the query using the data dictionary
        """

        self.msq = MSQuery(query=dictionary['query'], media_type=dictionary['mediaType'],
                           taxonomy_gbif=dictionary['taxon'],
                           openDownloadsOnly=self.openDatasetsOnly, media_tag=dictionary['mediaTag'])

    def runQueryForPage(self, page_number) -> None:
        # Ensure the MSQuery object exists and has performed the initial query
        if not self.msq:
            raise RuntimeError("Query has not been run. Cannot fetch page.")

        # Run the search for the specified page
        self.msq.run_search(page_number)

    def setAPIKey(self, api_key: str) -> None:
        """
        Set the API key for MorphoSource.
        """
        self.api_key = api_key
        self.saveSetting('apiKey', api_key)

    def setOpenDatasetsOnly(self, state: bool) -> None:
        """ Set the flag for querying open datasets only.

        Args:
            state (bool): State of the checkbox, True if checked, False otherwise.
        """
        self.openDatasetsOnly = state

    def set_download_folder(self, folder_path: str) -> None:
        self.download_folder = folder_path
        self.saveSetting('downloadFolder', folder_path)

    def saveSetting(self, settingName, value):
        settings = qt.QSettings()
        settings.setValue(f'MorphoSourceImport/{settingName}', value)

    def loadSetting(self, settingName, defaultValue):
        settings = qt.QSettings()
        return settings.value(f'MorphoSourceImport/{settingName}', defaultValue)

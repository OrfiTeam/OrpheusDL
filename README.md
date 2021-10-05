<!-- PROJECT INTRO -->

<img src='https://svgshare.com/i/__W.svg' title='Orfi_temporary' height="150">

OrpheusDL
=========

A modular music archival program

[Report Bug](https://github.com/yarrm80s/orpheusdl/issues)
·
[Request Feature](https://github.com/yarrm80s/orpheusdl/issues)


## Table of content

- [About OrpheusDL](#about-orpheusdl)
- [Getting Started](#getting-started)
    - [Prerequisites](#prerequisites)
    - [Installation](#installation)
- [Usage](#usage)
- [Configuration](#configuration)
    - [Global/Formatting](#globalformatting)
        - [Format variables](#format-variables)
- [Contact](#contact)
- [Acknowledgements](#acknowledgements)



<!-- ABOUT ORPHEUS -->
## About OrpheusDL

OrpheusDL is a modular music archival tool written in Python which allows archiving from multiple different services.


<!-- GETTING STARTED -->
## Getting Started

Follow these steps to get a local copy of Orpheus up and running:

### Prerequisites

* Python 3.7+ (due to the requirement of dataclasses)

### Installation

1. Clone the repo 
   * Without modules:
      ```shell
      git clone https://github.com/yarrm80s/orpheusdl.git
      ```
   * Or with all modules
      ```shell
      git clone --recurse-submodules https://github.com/yarrm80s/orpheusdl.git
      ```
2. Install all requirements
   ```shell
   pip install -r requirements.txt
   ```
3. Run the program at least once
   ```shell
   python3 orpheus.py
   ```
4. Enter your credentials in `config/settings.json`

<!-- USAGE EXAMPLES -->
## Usage

Just call `orpheus.py` with any link you want to archive, for example Qobuz:
    ```shell
    python3 orpheus.py https://open.qobuz.com/album/c9wsrrjh49ftb
    ```

Alternatively do a search (luckysearch to automatically select the first option):
    ```shell
    python3 orpheus.py search qobuz track darkside alan walker
    ```

<!-- CONFIGURATION -->
## Configuration

You can customize every module from Orpheus individually and also set general/global settings which are active in every
loaded module. You'll find the configuration file here: `config/settings.json`

### Global/Formatting:

`track_filename_format`: How tracks are formatted in albums and playlists. The relevant extension is appended to the end.

`album_format`, `playlist_format`, `artist_format`: Base directories for their respective formats - tracks and cover art are stored here. May have slashes in it,
for instance {artist}/{album}.

`single_full_path_format`: How singles are handled, which is separate to how the above work. Instead, this has both the folder's name and the track's name.

#### Format variables

`track_format` variables are `{title}`, `{artist}`, `{album_artist}`, `{album}`, `{track_number}`,
`{total_tracks}`, `{disc_number}`, `{total_discs}`, `{date}`, `{isrc}`, `{explicit}`.

`album_format` variables are `{album_name}`, `{artist_name}`, `{artist_id}`, `{album_year}`, `{explicit}`, `{quality}`.

<!-- Contact -->
## Contact

Yarrm80s - [@yarrm80s](https://github.com/yarrm80s)

Dniel97 - [@Dniel97](https://github.com/Dniel97)

Project Link: [Orpheus Public GitHub Repository](https://github.com/yarrm80s/orpheusdl)



<!-- ACKNOWLEDGEMENTS -->
## Acknowledgements
* Chimera by Aesir - the inspiration to the project
* [Icon modified from a freepik image](https://www.freepik.com/)

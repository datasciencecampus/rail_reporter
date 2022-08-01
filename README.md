# Rail Reporter

Generate statistics and visualisations describing the state of the UK's rail network

## Setup

To clone this repo, set up a python virtual environment and install python
dependencies (OSX/Linux):

```shell
git clone https://github.com/datasciencecampus/rail_reporter.git
cd rail_reporter

python -m venv env          # Set up then activate virtual environment
source env/bin/activate

python -m pip install --upgrade pip       # Install packages
python -m pip install -r requirements.txt

brew install direnv   # Install (OSX) if not installed already
direnv allow   # Allow direnv to make available project environment variables
```

---

You will need to create a .secrets file in the project root directory with
the following information:

```
export RAIL_FEED_USER=<DTD data feed username>
export RAIL_FEED_PASS=<DTD data feed password>
export RAIL_FEED_HOST=<DTD data feed remote server host name/endpoint>
export RAIL_FEED_PORT=<DTD data feed port (usually 22, and not secret)>
```

### Run

Currently only fetching rail data is fully implemented.  To run:

```shell
python src/fetch_feeds.py timetable
```

A bash script allows for extraction and fixing of the downloaded file, to run:

```shell
# Make shell script executable, if it isn't already
chmod u+x src/clean_railfeed_zip.sh

# Where xxx is the file number in the file name
./src/clean_railfeed_zip.sh -d ./data/external -f RJTTFxxx
```

The intention is to integrate all steps into a process with one trigger script

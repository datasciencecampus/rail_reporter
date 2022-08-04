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

Note: you may need to add `eval "$(direnv hook zsh)"` to the ~/.zshrc file during an initial setup.

---

You will need to create a .secrets file in the project root directory with
the following information:

```
# For configuring data ingest
export RAIL_FEED_USER=<DTD data feed username>
export RAIL_FEED_PASS=<DTD data feed password>
export RAIL_FEED_HOST=<DTD data feed remote server host name/endpoint>
export RAIL_FEED_PORT=<DTD data feed port (usually 22, and not secret)>

# For configuring data dissemination
export RAIL_SEND_ADDR=<dissemination email address>
export RAIL_RECIPIENT="example.1@gmail.com|example.2@gov.uk"
```

For email dissemination you will also need a valid credentials.json in the root
of the project, generated by the google project the email address is linked to,
with appropriate emailing rights.  To set all that up, see this stackoverflow:
https://stackoverflow.com/a/72346413

## Run pipeline

The intention is to integrate all steps into a process with one trigger script.
Currently only fetching rail data is fully implemented.

```shell
python run.py
```

We have automated this using crontab on Mac.  Setting this up requires some
additional steps.  For instructions on enabling crontab on OSX [see here](https://osxdaily.com/2020/04/27/fix-cron-permissions-macos-full-disk-access/).
For a tutorial on how to set up a cron job (scheduled program) [see here](https://www.youtube.com/watch?v=QZJ1drMQz1A).
For a useful tool for composing cron schedules/instructions [see here](https://crontab.guru/).

- make the run script executable with: `chmod u+x run.sh`

- our cron schedule entry: `0 5 * * * cd <project_folder> && ./run.sh`


## Running steps independently

#### Request ATOC Data
First, need to request all recent ATOC data. To run:

```shell
python src/fetch_feeds.py timetable
```

---

#### Build Timetable
Then, can build a timetable by running:

```shell
python src/build_timetable.py <zip_file_name>
```

Where `<zip_file_name>` is the name of the ATOC zip file to work on (include.zip file extension). This run command also has two optional parameters:

* `--dump_date`, which is a string in DDMMYYYY format format corresponding to the day in which the ATOC zip file was "dumped". If this is not provided, the default assumption is the ATOC zip file was "dumped" on the current day of the run call.

* `--date`, which is a string in DDMMYYY format corresponding to the day in which the timetable will be filtered to/built. Note, the conversion to the ATOC format (YYMMDD) is handled during the call.

An example call using these optional parameters could be:

```shell
python src/build_timetable.py <zip_file_name> --dump_date 01082022 --date 02082022
```

Which would use `<zip_file_name>`, take the ATOC data "dump" date as 01/Aug/2022 and filter it to 02/Aug/2022.

---

#### Email out the results

The automailing functions can be run as a standalone script that'll send a test
attachment to recipients in `.secrets`:

```shell
python ./src/automail.py
```

---

#### DEPRECATED - FIX ATOC ZIP FILE
A bash script allows for extraction and fixing of the downloaded file, to run:

```shell
# Make shell script executable, if it isn't already
chmod u+x src/clean_railfeed_zip.sh

# Where xxx is the file number in the file name
./src/clean_railfeed_zip.sh -d ./data/external -f RJTTFxxx
```

## Shopping List

- automail to run as independent script if required
- build_timetable simplified, to take minimal arguments for input and output files/dirs
- fetch_feeds.py to take minimal arguments for input and output files/dirs
- ultimately only run.py should be spamming os.getenv (one place to change, reduce repetition)
- end-to-end tests
- unit tests for functions in utils
- email alerts to the team when something messes up
- fix all our dates stuff for daylight savings etc

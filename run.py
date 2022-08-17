import os
import json
import zipfile
import logging

from datetime import datetime

from src.utils import breakout_DTD_filename
from src.automail import email_rail_report


LOG_DIR = os.getenv("DIR_LOG")
ATOC_DIR = os.getenv("DIR_DATA_EXTERNAL_ATOC")
OUT_DIR = os.getenv("DIR_OUTPUTS")


def main():

    logger = logging.getLogger(__name__)
    logger.info(" ------------------------------------------------------- ")
    logger.info("Running full process")

    # Fetch latest files
    os.system(f"python ./src/fetch_feeds.py timetable {ATOC_DIR}")

    with open("progress.json", "r") as f:
        prog = json.load(f)

        if not prog["new_files"]:
            logger.info("No new feed data has been found, " + "reporting and exiting.")
            content = (
                "No new feed data detected this morning, "
                + "this may be a temporary delay in the data source, "
                + "we will try again this afternoon."
            )
            email_rail_report(content=content)
            return None

    # Find all ATOC zips for FULL data
    files = [
        breakout_DTD_filename(file)
        for file in os.listdir(ATOC_DIR)
        if ".ZIP" in file and file.startswith("RJTTF")
    ]

    logger.info(f"Found {len(files)} files")

    # Order list by production number, pop latest (highest number)
    files.sort(key=lambda d: d["number"])
    latest = files.pop()
    logger.info(f"Latest file: {latest['name']}")

    # Produce statistics from that file
    os.system(
        "python ./src/build_timetable.py "
        + f"{latest['name']} {ATOC_DIR} {OUT_DIR} --no_days 30"
    )

    # Produce visualisation from those statistics
    os.system("python ./src/make_visualisations.py --no_days 30")

    # Bundle outputs to zip, selecting all csv's, html's dated today
    OUT_FOLDER = os.path.join(OUT_DIR, datetime.now().strftime("%Y%m%d"))

    out_files = [
        file
        for file in os.listdir(OUT_FOLDER)
        if ((".csv" in file) | (".html" in file) | (".png" in file))
        & (datetime.now().strftime("%Y%m%d") in file)
    ]

    archive_name = "rail_status_{date}.zip".format(date=str(datetime.now().date()))

    with zipfile.ZipFile(os.path.join(OUT_FOLDER, archive_name), mode="w") as archive:
        for file in out_files:
            file_path = os.path.join(OUT_FOLDER, file)
            archive.write(file_path, arcname=file, compress_type=zipfile.ZIP_DEFLATED)

    logger.info(
        "files {file_list} zipped to {archive}".format(
            file_list=", ".join(out_files), archive=archive_name
        )
    )

    # Mail the zip file to the recipient list configured in .secrets
    email_rail_report(attachment_filepaths=[os.path.join(OUT_FOLDER, archive_name)])


if __name__ == "__main__":
    # Configure logging
    log_fmt = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    logging.basicConfig(
        level=logging.INFO,
        format=log_fmt,
        filename=os.path.join(
            os.getenv("DIR_LOG"), f"{str(datetime.now().date())}.log"
        ),
    )

    main()

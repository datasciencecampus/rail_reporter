import os
import zipfile
import logging

from datetime import datetime

from src.utils import breakout_DTD_filename
from src.automail import email_rail_report


LOG_DIR = os.getenv("DIR_LOG")
ATOC_DIR = os.getenv("DIR_DATA_EXTERNAL_ATOC")


def main():

    logger = logging.getLogger(__name__)
    logger.info("Running full process")

    # Fetch latest files
    os.system("python ./src/fetch_feeds.py timetable")

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
    os.system(f"python ./src/build_timetable.py {latest['name']}")

    # Bundle outputs to zip
    out_files = [
        file
        for file in os.listdir(os.getenv("DIR_OUTPUTS"))
        if (".csv" in file) | (".html" in file)
    ]

    archive_name = "rail_status_{date}.zip".format(date=str(datetime.now().date()))

    with zipfile.ZipFile(
        os.path.join(os.getenv("DIR_OUTPUTS"), archive_name), mode="w"
    ) as archive:
        for file in out_files:
            file_path = os.path.join(os.getenv("DIR_OUTPUTS"), file)
            archive.write(file_path, arcname=file)

    logger.info(
        "files {file_list} zipped to {archive}".format(
            file_list=", ".join(out_files), archive=archive_name
        )
    )

    # Mail the zip file to the recipient list configured in .secrets
    email_rail_report([os.path.join(os.getenv("DIR_OUTPUTS"), archive_name)])


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

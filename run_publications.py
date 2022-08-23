import logging
import os
from datetime import datetime

LOG_DIR = os.getenv("DIR_LOG")
ATOC_DIR = os.getenv("DIR_DATA_EXTERNAL_ATOC")
OUT_DIR = os.getenv("DIR_OUTPUTS")


def main():

    logger = logging.getLogger(__name__)
    logger.info("Running publications process...")

    # # Fetch latest files
    # os.system(f"python ./src/fetch_feeds.py timetable {ATOC_DIR}")

    # build timetable for single day visual - 20220806
    # os.system(
    #     f"python ./src/build_timetable.py RJTTF458.zip {ATOC_DIR} {OUT_DIR} "
    #     "--dump_date 06082022 --start_date 06082022"
    # )

    # build timetable for single day visual (20220813) and timeseries (11 to 31)
    # os.system(
    #     f"python ./src/build_timetable.py RJTTF463.zip {ATOC_DIR} {OUT_DIR} "
    #     "--dump_date 11082022 --start_date 11082022"
    # )

    # # build single day visual for 20220806
    # os.system(
    #     f"python ./src/make_publications.py --working_directory {OUT_DIR}"
    #     "/20220806 --csv_input_filename "
    #     "full_uk_disruption_summary_multiday_start_20220806_30days.csv  "
    #     "--start_date 06082022"
    # )

    # # build single day visual for 20220813
    # os.system(
    #     f"python ./src/make_publications.py --working_directory {OUT_DIR}"
    #     "/20220811 --csv_input_filename "
    #     "full_uk_disruption_summary_multiday_start_20220811_30days.csv  "
    #     "--start_date 13082022"
    # )

    # # build timeseries visual for 20220811 to 20220831
    os.system(
        f"python ./src/make_publications.py --working_directory {OUT_DIR}"
        "/20220811 --csv_input_filename "
        "full_uk_disruption_summary_multiday_start_20220811_30days.csv  "
        "--start_date 11082022 --end_date 31082022"
    )


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

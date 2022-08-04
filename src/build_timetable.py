import logging
import os
import shutil
from datetime import datetime, timedelta

import click
import pandas as pd
import numpy as np

from utils import (
    create_perm_and_new_df,
    cut_mca_to_size,
    filter_to_date,
    filter_to_dft_time,
    find_station_tiplocs,
    unpack_atoc_data,
    download_big_file,
)


@click.command()
@click.argument("zip_name")
@click.argument("data_directory")
@click.argument("output_directory")
@click.option("--dump_date", default=None, type=str)
@click.option("--start_date", default=None, type=str)
@click.option("--increment_days", default=30, type=int)
def main(
    zip_name: str,
    data_directory: str,
    output_directory: str,
    dump_date: str,
    start_date: str,
    increment_days: int,
):
    """
    Handles building and saving timetable data for a daily ATOC feed

    Parameters
    ----------
    zip_name : str
        Name of the ATOC zip file to build off (with .zip file extension).
    dump_date : str
        Date string corresponding to the date the ATOC zip file was "dumped"
        in DDMMYYYY format.
    date : str
        Date string to filter ATOC data to in DDMMYYYY format.
    """
    logger = logging.getLogger(__name__)

    # set to today if no dump_date is provided
    if dump_date is None:
        dump_date = datetime.now().date().strftime("%d%m%Y")
        logger.info(
            f'Setting `dump_date` to "{dump_date}" (today) automatically'
            " since the optional argument was not set."
        )

    if start_date is None:
        start_date = datetime.now().date()
        logger.info(
            f"Setting `start_date` to {start_date} (today) automatically since the"
            "optional argument was not set."
        )
    else:
        start_date = datetime.strptime(start_date, "%d%m%Y").date()

    # print inputs to logger for records
    logger.info(
        f'Using inputs ATOC zip:"{zip_name}", dump_date:"{dump_date}",'
        f' start_date:{start_date}, increment_days:"{increment_days}".'
    )

    # build a list of days to run over
    dates = []
    for i in range(0, increment_days):
        dates.append(start_date + timedelta(days=i))
    logger.info(f"Days to analyse = {dates}")

    # Download file if not already exists
    download_big_file(os.getenv("URL_STOPS"), "Stops.csv", data_directory)
    station_tiplocs = find_station_tiplocs(os.path.join(data_directory, "Stops.csv"))
    logger.info("Tiplocs retrieved from Stops.csv/tiploc file...")

    # unpack the atoc data
    unpack_atoc_data(data_directory, zip_name, dump_date)
    logger.info(f'"{zip_name}" unziped.')

    # remove header rows (non-timetable data)
    df = cut_mca_to_size(data_directory, zip_name.replace(".zip", ""), dump_date)
    logger.info("MCA cut to size.")

    # filter journey data and cancellation data
    logger.info("Creating calendar and cancelled dataframes... (~30s)")
    calendar_df, cancelled_df = create_perm_and_new_df(df)

    # include only rows for actual station stops i.e. not flybys
    calendar_df = calendar_df[calendar_df["TIPLOC_type"] != "F"]
    logger.info("Created calendar and cancelled dataframes and removed flybys.")

    for run_num, date_datetime in enumerate(dates):

        # get the date in the required int format
        date = int(date_datetime.strftime("%y%m%d"))

        # calculate the day from `date`
        day = datetime.strptime(str(date), "%y%m%d").strftime("%A")

        logger.info(f"*** Running with date: {date}, day: {day} ***")

        logger.info(f"Filtering to {date}...")
        canc_today = filter_to_date(cancelled_df, date=date, cancellations=True)
        cal_today = filter_to_date(calendar_df, date=date)
        cal_times_today = filter_to_dft_time(cal_today)

        # filter permanent timetabled journeys attributed to this date
        # (i.e. before any cancellations or exceptions)
        timetabled = (
            cal_times_today["TIPLOC"][cal_times_today["Flag"] == "P"]
            .value_counts()
            .reset_index()
        )
        timetabled.columns = ["TIPLOC", "journeys_timetabled"]
        timetabled["journeys_timetabled"] = timetabled["journeys_timetabled"].astype(
            "int"
        )

        # split journeys into categories
        perm_new_today = cal_times_today[cal_times_today["Flag"].isin(["P", "N"])]
        overlays_today = cal_times_today[cal_times_today["Flag"] == "O"]

        # list affected journeys
        overlays_today_list = overlays_today["Identifier"].unique()
        cancellations_today_list = canc_today["Identifier"].unique()

        # filter out journeys cancelled or amended
        today_amended = perm_new_today[
            (~perm_new_today["Identifier"].isin(cancellations_today_list))
        ]
        today_amended = today_amended[
            (~today_amended["Identifier"].isin(overlays_today_list))
        ]
        logger.info("Removed cancelled journeys and added exceptions.")

        # add in overlayed exceptions in place of some journeys
        final_df = pd.concat([today_amended, overlays_today])
        logger.info("`final_df` built.")

        # filter to show only rail station TIPLOCs
        stations_df = final_df[
            final_df["TIPLOC"].isin(list(station_tiplocs["TIPLOC"].unique()))
        ]
        final_df = stations_df.merge(
            station_tiplocs[["TIPLOC", "Station_Name", "Latitude", "Longitude"]],
            on="TIPLOC",
            how="inner",
        )
        logger.info(f"Full schedule for {date} built")

        scheduled = final_df["TIPLOC"].value_counts().reset_index()
        scheduled.columns = ["TIPLOC", "journeys_scheduled"]

        merged = pd.merge(scheduled, timetabled, on="TIPLOC", how="left")
        merged["pct_timetabled_services_running"] = np.round(
            merged["journeys_scheduled"] / merged["journeys_timetabled"] * 100, 2
        )
        merged.sort_values("journeys_timetabled", ascending=False, inplace=True)
        output = merged.merge(
            station_tiplocs[["TIPLOC", "Station_Name", "Latitude", "Longitude"]],
            on="TIPLOC",
            how="inner",
        )

        # add date to output
        output.loc[:, "date"] = datetime.strftime(date_datetime, "%Y-%m-%d")

        logger.info(f"Full disruption summary for {date}.")

        if run_num == 0:
            out_df = output.copy()
            logger.info(f"Run number {run_num}: Creating out_df")
        else:
            out_df = pd.concat([out_df, output], ignore_index=True)
            logger.info(f"Run number {run_num}: Concated output onto out_df")

    logger.info("Exporting out_df...")
    output_file_name = (
        f"full_uk_disruption_summary_multiday_start_"
        f'{str(start_date).replace("-","")}_{increment_days}days.csv'
    )
    out_df.to_csv(os.path.join(output_directory, output_file_name))
    logger.info(f"out_df exported to {output_directory}/{output_file_name}")

    # tidyup - remove unzipped atoc folder
    shutil.rmtree(os.path.join(data_directory, f"atoc_{dump_date}"))
    logger.info(f"Tidy up: removed atoc_{dump_date} folder.")

    return None


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

import logging
import os
import shutil
from datetime import datetime

import click
import pandas as pd
import numpy as np
from pyprojroot import here

from utils import (
    create_perm_and_new_df,
    cut_mca_to_size,
    filter_to_date_and_time,
    find_station_tiplocs,
    unpack_atoc_data,
)


@click.command()
@click.argument("zip_name")
@click.option("--dump_date", default=None, type=str)
@click.option("--date", default=None, type=str)
def main(zip_name: str, dump_date: str, date: str):
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

    # set to today is no date is provided
    if date is None:
        date = int(datetime.now().date().strftime("%y%m%d"))
        logger.info(
            f"Setting `date` to {date} (today) automatically since the"
            "optional argument was not set."
        )
    else:
        # change the format of the input to required format
        date = int(datetime.strptime(str(date), "%d%m%Y").strftime("%y%m%d"))

    # calculate the day from `date`
    day = datetime.strptime(str(date), "%y%m%d").strftime("%A")

    logger.info(
        f'Using inputs ATOC zip:"{zip_name}", dump_date:"{dump_date}",'
        f' date:{date}, day:"{day}".'
    )

    external_folder_path = os.path.join(here(), "data", "external")
    outputs_folder_path = os.path.join(here(), "output")

    # unpack the atoc data
    unpack_atoc_data(external_folder_path, zip_name, dump_date)
    logger.info(f'"{zip_name}" unziped.')

    # remove header rows (non-timetable data)
    df = cut_mca_to_size(external_folder_path, zip_name.replace(".zip", ""), dump_date)
    logger.info("MCA cut to size.")

    # filter journey data and cancellation data
    logger.info("Creating calendar and cancelled dataframes... (~30s)")
    calendar_df, cancelled_df = create_perm_and_new_df(df)
    logger.info("Created calendar and cancelled dataframes.")

    logger.info(f"Filtering to {date}")
    cal_today = filter_to_date_and_time(calendar_df, date, day)
    canc_today = filter_to_date_and_time(cancelled_df, date, day)

    # filter permanent timetabled journeys attributed to this date
    # (i.e. before any cancellations or exceptions)
    timetabled = (
        cal_today["TIPLOC"][cal_today["Flag"] == "P"].value_counts().reset_index()
    )
    timetabled.columns = ["TIPLOC", "journeys_timetabled"]
    timetabled["journeys_timetabled"] = timetabled["journeys_timetabled"].astype("int")

    # split journeys into categories
    perm_new_today = cal_today[cal_today["Flag"].isin(["P", "N"])]
    overlays_today = cal_today[cal_today["Flag"] == "O"]

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

    # retrieve station tiplocs
    tiploc_filepath = os.path.join(here(), "data", "external", "geography", "Stops.csv")
    logger.info("Opening Stops.csv/tiploc file...")
    station_tiplocs = find_station_tiplocs(tiploc_filepath)

    # filter to show only rail station TIPLOCs
    stations_df = final_df[
        final_df["TIPLOC"].isin(list(station_tiplocs["TIPLOC"].unique()))
    ]
    final_df = stations_df.merge(
        station_tiplocs[["TIPLOC", "Station_Name", "Latitude", "Longitude"]],
        on="TIPLOC",
        how="inner",
    )
    final_df.to_csv(os.path.join(outputs_folder_path, f"full_uk_schedule_{date}.csv"))
    logger.info(f"Full schedule for {date} exported to {outputs_folder_path}")

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
    output.to_csv(
        os.path.join(outputs_folder_path, f"full_uk_disruption_summary_{date}.csv")
    )
    logger.info(f"Full disruption summary for {date} exported to {outputs_folder_path}")

    # tidyup - remove unzipped atoc folder
    shutil.rmtree(os.path.join(external_folder_path, "atoc", f"atoc_{dump_date}"))
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
        filemode="w",
    )

    main()

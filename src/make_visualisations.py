import logging
import os
from datetime import datetime

import click
import pandas as pd
from pyprojroot import here

from utils import (
    add_folium_times,
    build_features,
    build_legend_macro,
    convert_to_gpdf,
    scale_col,
)


@click.command()
@click.option("--working_directory", default=None, type=str)
@click.option("--csv_input_filename", default=None, type=str)
@click.option("--no_days", default=30, type=int)
@click.option("--scale_markers_on", default="journeys_timetabled", type=str)
@click.option(
    "--measure_control", is_flag=True, show_default=True, default=True, type=bool
)
@click.option("--mini_map", is_flag=True, show_default=True, default=True, type=bool)
@click.option("--full_screen", is_flag=True, show_default=True, default=True, type=bool)
@click.option(
    "--add_geocoder", is_flag=True, show_default=True, default=True, type=bool
)
def main(
    working_directory: str,
    csv_input_filename: str,
    no_days: int,
    scale_markers_on: str,
    measure_control: bool,
    mini_map: bool,
    full_screen: bool,
    add_geocoder: bool,
):
    """
    Handles building timeseries and static visualisations
    """
    logger = logging.getLogger(__name__)

    # handle working directory
    if working_directory is None:
        date = datetime.now().date().strftime("%Y%m%d")
        working_directory = os.path.join(here(), "output", date)
        logger.info(
            f"Setting `working_directory` to {working_directory} automatically"
            " since the optional argument was not set."
        )

    # handle csv name
    if csv_input_filename is None:
        date = datetime.now().date().strftime("%Y%m%d")
        csv_input_filename = (
            f"full_uk_disruption_summary_multiday_start_{date}_{no_days}days.csv"
        )
        logger.info(
            f"Setting `csv_input_filename` to {csv_input_filename} automatically"
            " since the optional argument was not set."
        )

    # get df from the csv
    df_directory = os.path.join(working_directory, csv_input_filename)
    df = pd.read_csv(df_directory, index_col=0)
    logger.info(f"Opened {df_directory}")

    # share optional params status
    logger.info(
        f"Building with `measure_control`: {measure_control}, "
        f"`mini_map`: {mini_map}, `full_screen`: {full_screen}, and "
        f"`add_geocoder`: {add_geocoder}"
    )

    gp_df = convert_to_gpdf(df, lat_col="Latitude", long_col="Longitude")
    logger.info("Converted to a GeoPandas DataFrame.")

    gp_df["times"] = gp_df.apply(add_folium_times, axis=1, args=["date"])
    logger.info("Set and built folim `times` column.")

    gp_df["radius"] = scale_col(gp_df, scale_markers_on, 2, 12)
    logger.info(
        f'Scaled marker radius on column "{scale_markers_on}". '
        f'Min marker radius: {gp_df["radius"].min()}, '
        f'Max marker radius: {gp_df["radius"].max()}.'
    )

    _ = build_legend_macro()
    logger.info("Legend macro built.")

    # drop missing rows with no percentage data
    gp_df = gp_df[~gp_df["pct_timetabled_services_running"].isna()]

    _ = build_features(gp_df)


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

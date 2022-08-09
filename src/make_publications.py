import logging
import os
import re
from datetime import datetime

import click
import pandas as pd
from pyprojroot import here

from utils import (
    add_build_date,
    add_timestamped_geojson,
    add_folium_times,
    add_logo,
    add_singleday_display_date,
    build_base_map,
    build_features,
    build_macro_legend_publication,
    convert_to_gpdf,
    scale_col,
)


@click.command()
@click.option("--working_directory", default=None, type=str)
@click.option("--csv_input_filename", default=None, type=str)
@click.option("--start_date", default=None, type=str)
@click.option("--end_date", default=None, type=str)
@click.option("--scale_markers_on", default="journeys_timetabled", type=str)
@click.option(
    "--measure_control", is_flag=True, show_default=False, default=False, type=bool
)
@click.option("--mini_map", is_flag=True, show_default=False, default=False, type=bool)
@click.option(
    "--full_screen", is_flag=True, show_default=False, default=False, type=bool
)
@click.option(
    "--add_geocoder", is_flag=True, show_default=True, default=True, type=bool
)
def main(
    working_directory: str,
    csv_input_filename: str,
    start_date: str,
    end_date: str,
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

    today_date = datetime.now().date().strftime("%Y%m%d")

    if start_date is None:
        # add one day so pipeline starts one day after dump day
        start_date = datetime.now().date().strftime("%Y%m%d")
        logger.info(
            f"Setting `start_date` to {start_date} automatically since the"
            "optional argument was not set."
        )
    else:
        start_date = datetime.strptime(start_date, "%d%m%Y").date()

    if end_date is None:
        single_day = True
        logger.info(
            f"Setting `single_day` to {single_day} - generating a single day vis."
        )
    else:
        single_day = False
        logger.info(
            f"Setting `single_day` to {single_day} - generating a multi day vis."
        )
        end_date = datetime.strptime(end_date, "%d%m%Y").date()

    # handle working directory
    if working_directory is None:
        working_directory = os.path.join(here(), "outputs", today_date)
        logger.info(
            f"Setting `working_directory` to {working_directory} automatically"
            " since the optional argument was not set."
        )

    # handle csv name
    if csv_input_filename is None:
        csv_input_filename = (
            f"full_uk_disruption_summary_multiday_start_{today_date}_30days.csv"
        )
        logger.info(
            f"Setting `csv_input_filename` to {csv_input_filename} automatically"
            " since the optional argument was not set."
        )

    # get df from the csv
    df_directory = os.path.join(working_directory, csv_input_filename)
    df = pd.read_csv(df_directory, index_col=0)
    logger.info(f"Opened {df_directory}")

    # filter df to provided start/end dates
    df["date_format"] = pd.to_datetime(df["date"], format="%Y-%m-%d").dt.date
    if single_day:
        df = df[df.date_format == start_date].copy()
        logger.info(f"Filtered df to {start_date} only.")
    else:
        df = df[(df.date_format >= start_date) & (df.date_format <= end_date)].copy()
        logger.info(f"Filtered df between {start_date} and {end_date} inclusive.")
    df.drop(columns=["date_format"], inplace=True)

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

    # drop missing rows with no percentage data
    gp_df = gp_df[~gp_df["pct_timetabled_services_running"].isna()]

    # categorical, sequential colour scale - BuRd
    colour_scale = [
        "#000000",
        "#8b0000",
        "#ff0000",
        "#ff0066",
        "#ff00cc",
        "#cc00ff",
        "#6600ff",
        "#0000ff",
    ]

    features = build_features(gp_df, colour_scale=colour_scale)
    logger.info("Built features.")

    m = build_base_map(
        full_screen, mini_map, add_geocoder, measure_control, publication=True
    )
    logger.info("Built base map")

    m = add_timestamped_geojson(m, features)
    logger.info("Added TimestampedGeoJson object to map.")

    m = add_logo(m)
    logger.info("Added logo to map.")

    m = add_build_date(m)
    logger.info("Added build date to map.")

    macro = build_macro_legend_publication(colour_scale)
    m.get_root().add_child(macro)
    logger.info("Legend macro built and added.")

    start_date_out = start_date.strftime("%Y%m%d")
    if not single_day:
        logger.info("Saving timeseries visual...")
        end_date_out = end_date.strftime("%Y%m%d")
        vis_filepath = os.path.join(
            working_directory,
            f"publication_timeseries_{start_date_out}_to_{end_date_out}.html",
        )
        m.save(vis_filepath)
        logger.info(f"Timeseries visual saved {vis_filepath}")
    else:
        logger.info("Saving single day visual...")

        m = add_singleday_display_date(m, start_date)

        vis_filepath = os.path.join(
            working_directory,
            f"publication_singleday_{start_date_out}.html",
        )
        m.save(vis_filepath)

        with open(vis_filepath, "r") as f:
            lines_in = f.readlines()
        lines_out = [
            re.sub(
                r"map_[a-zA-Z0-9]+.addControl\(this.timeDimensionControl\);", "", line
            )
            for line in lines_in
        ]
        with open(vis_filepath, "w") as f:
            f.writelines(lines_out)

    logger.info("Make publications complete!")


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

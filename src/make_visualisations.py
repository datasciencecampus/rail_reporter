import logging
import os
from datetime import datetime

import click
import pandas as pd
from pyprojroot import here

from utils import (
    add_build_date,
    add_timestamped_geojson,
    add_folium_times,
    add_logo,
    build_base_map,
    build_features,
    build_legend_macro,
    build_static_visual,
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

    date = datetime.now().date().strftime("%Y%m%d")

    # handle working directory
    if working_directory is None:
        working_directory = os.path.join(here(), "output", date)
        logger.info(
            f"Setting `working_directory` to {working_directory} automatically"
            " since the optional argument was not set."
        )

    # handle csv name
    if csv_input_filename is None:
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

    # drop missing rows with no percentage data
    gp_df = gp_df[~gp_df["pct_timetabled_services_running"].isna()]

    features = build_features(gp_df)
    logger.info("Built features.")

    m = build_base_map(full_screen, mini_map, add_geocoder, measure_control)
    logger.info("Built base map")

    m = add_timestamped_geojson(m, features)
    logger.info("Added TimestampedGeoJson object to map.")

    m = add_logo(m)
    logger.info("Added logo to map.")

    m = add_build_date(m)
    logger.info("Added build date to map.")

    macro = build_legend_macro()
    m.get_root().add_child(macro)
    logger.info("Legend macro built and added.")

    logger.info("Saving timeseries visual...")
    vis_filepath = os.path.join(
        working_directory,
        csv_input_filename.replace(".csv", ".html"),
    )
    m.save(vis_filepath)
    logger.info(f"Timeseries visual saved {vis_filepath}")

    logger.info("Building GB static visual...")
    gb_bbox_html = m.get_root().render()
    build_static_visual(working_directory, date, "GB", m)
    del gb_bbox_html
    logger.info("Built GB static visual.")

    bboxes = {
        "midlands": {
            "bbox": [(52.0564, -2.7160), (52.6369, -1.1398)],
            "padding": (-60, -60),
        },
        "london": {
            "bbox": [(51.0076, -0.9390), (51.8959, 0.8919)],
            "padding": (-90, 90),
        },
        "northwest": {
            "bbox": [(53.1839, -3.4250), (53.9614, -1.0739)],
            "padding": (-80, -80),
        },
        "northengland": {
            "bbox": [(54.4035, -3.2326), (55.0393, 0)],
            "padding": (-50, -50),
        },
        "scotland": {
            "bbox": [(55.6800, -4.5136), (56.1745, -3.0308)],
            "padding": (-30, -30),
        },
    }
    for place in bboxes.keys():
        logger.info(f"Building {place} static visual...")
        m.fit_bounds(bboxes[place]["bbox"], padding=bboxes[place]["padding"])
        build_static_visual(working_directory, date, place, m)
        logger.info(f"Built {place} static visual.")

    logger.info("Make visualisations completed!")


if __name__ == "__main__":
    # Configure logging
    log_fmt = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    logging.basicConfig(
        level=logging.INFO,
        format=log_fmt,
        filename=os.path.join(
            os.getenv("DIR_LOG"), f"{str(datetime.now().date())}.log"
        ),
        filemode="a",
    )

    main()

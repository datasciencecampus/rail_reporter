import os
import re
from zipfile import ZipFile

import pandas as pd
from convertbng.util import convert_lonlat


def breakout_filenames(filename: str):
    """Pulls metadata out of a DTD rail data filename"""
    return {
        "name": filename,
        "number": re.sub(r"[^0-9]", "", filename),
        "type": re.sub(r"[^A-Z]", "", filename),
    }


def unpack_atoc_data(folder_path, zip_name, dump_date):
    """Unpacks atoc zip file"""

    with ZipFile(os.path.join(folder_path, "atoc", zip_name), "r") as zip:
        zip.extractall(os.path.join(folder_path, "atoc", f"atoc_{dump_date}"))


def cut_mca_to_size(folder_path, zip_name, dump_date):

    mca_file_path = os.path.join(
        folder_path, "atoc", f"atoc_{dump_date}", f"{zip_name}.MCA"
    )

    with open(mca_file_path, "r") as f:
        lines = f.readlines()

    # remove leading rows and start from first timetabled journey
    for row, line in enumerate(lines):
        if line[:2] == "BS":
            first_row = row
            break

    timetable = lines[first_row:]

    return timetable


def create_perm_and_new_df(timetable):

    ind_movts = []
    cancelled_movts = []

    for spec_line in timetable:

        if spec_line[:2] == "BS":
            unq_id = spec_line[3:9]
            cal_from = spec_line[9:15]
            cal_to = spec_line[15:21]
            monday = spec_line[21]
            tuesday = spec_line[22]
            wednesday = spec_line[23]
            thursday = spec_line[24]
            friday = spec_line[25]
            saturday = spec_line[26]
            sunday = spec_line[27]
            flag = spec_line[-2]

            if flag == "C":
                cancelled_movts.append(
                    [
                        unq_id,
                        monday,
                        tuesday,
                        wednesday,
                        thursday,
                        friday,
                        saturday,
                        sunday,
                        cal_from,
                        cal_to,
                        flag,
                    ]
                )

            station_stop = 0

        elif spec_line[:2] == "BX":
            operator = spec_line[11:13]

        else:
            if spec_line[:2] == "LO":
                tiploc = spec_line[2:].split(" ")[0]
                station_stop += 1
                time = spec_line[10:14]
                tiploc_type = "S"  # station
                ind_movts.append(
                    [
                        unq_id,
                        operator,
                        tiploc,
                        tiploc_type,
                        time,
                        station_stop,
                        monday,
                        tuesday,
                        wednesday,
                        thursday,
                        friday,
                        saturday,
                        sunday,
                        cal_from,
                        cal_to,
                        flag,
                    ]
                )

            elif spec_line[:2] == "LT":
                tiploc = spec_line[2:].split(" ")[0]
                station_stop += 1
                time = spec_line[10:14]
                tiploc_type = "S"  # station
                ind_movts.append(
                    [
                        unq_id,
                        operator,
                        tiploc,
                        tiploc_type,
                        time,
                        station_stop,
                        monday,
                        tuesday,
                        wednesday,
                        thursday,
                        friday,
                        saturday,
                        sunday,
                        cal_from,
                        cal_to,
                        flag,
                    ]
                )

            elif spec_line[:2] == "LI":
                tiploc = spec_line[2:].split(" ")[0]

                # times for stations and junctions (slightly different format)
                if spec_line[10] != " ":
                    time = spec_line[10:14]
                    tiploc_type = "S"  # station
                    station_stop += 1
                else:
                    time = spec_line[20:24]
                    tiploc_type = "F"  # flyby

                ind_movts.append(
                    [
                        unq_id,
                        operator,
                        tiploc,
                        tiploc_type,
                        time,
                        station_stop,
                        monday,
                        tuesday,
                        wednesday,
                        thursday,
                        friday,
                        saturday,
                        sunday,
                        cal_from,
                        cal_to,
                        flag,
                    ]
                )

            else:
                pass

    calendar_df = pd.DataFrame(
        ind_movts,
        columns=[
            "Identifier",
            "Operator",
            "TIPLOC",
            "TIPLOC_type",
            "Time",
            "Stop",
            "Monday",
            "Tuesday",
            "Wednesday",
            "Thursday",
            "Friday",
            "Saturday",
            "Sunday",
            "Valid_from",
            "Valid_to",
            "Flag",
        ],
    )

    cancelled_df = pd.DataFrame(
        cancelled_movts,
        columns=[
            "Identifier",
            "Monday",
            "Tuesday",
            "Wednesday",
            "Thursday",
            "Friday",
            "Saturday",
            "Sunday",
            "Valid_from",
            "Valid_to",
            "Flag",
        ],
    )

    return calendar_df, cancelled_df


def filter_to_date_and_time(
    journey_rows_df,
    date,
    weekday,
    # time_slice=(["0000", "2359"]),
):

    journey_rows_df[["Valid_from", "Valid_to"]] = journey_rows_df[
        ["Valid_from", "Valid_to"]
    ].astype("int64")

    return journey_rows_df[
        (journey_rows_df["Valid_from"] <= date)
        & (journey_rows_df["Valid_to"] >= date)
        # & (journey_rows_df["Time"] >= time_slice[0])
        # & (journey_rows_df["Time"] <= time_slice[1])
        & (journey_rows_df[weekday] == "1")
    ]


def find_station_tiplocs(stops_file_path):
    # assumes NAPTAN csv is present (https://beta-naptan.dft.gov.uk/download/national)
    tiploc_coords = pd.read_csv(stops_file_path, low_memory=False)
    tiploc_coords = tiploc_coords[
        (tiploc_coords["Status"] == "active") & (tiploc_coords["StopType"] == "RLY")
    ]
    tiploc_coords["TIPLOC"] = [x[4:] for x in tiploc_coords["ATCOCode"]]

    # convert from OS grid references to coordinates
    tiploc_coords["Longitude"], tiploc_coords["Latitude"] = convert_lonlat(
        tiploc_coords["Easting"], tiploc_coords["Northing"]
    )

    tiploc_clean = tiploc_coords[
        ["TIPLOC", "CommonName", "Latitude", "Longitude"]
    ].copy()
    tiploc_clean.rename(columns={"CommonName": "Station_Name"}, inplace=True)

    return tiploc_clean

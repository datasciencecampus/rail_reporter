# flake8: noqa E501

import os
import re
from zipfile import ZipFile
from datetime import datetime, timedelta
import calendar
import glob
import base64
import io
import time
from pyprojroot import here

import pandas as pd
import numpy as np
from convertbng.util import convert_lonlat
import geopandas as gpd
import folium
from folium.plugins import (
    FloatImage,
    Fullscreen,
    Geocoder,
    MeasureControl,
    MiniMap,
    TimestampedGeoJson,
)
from folium.utilities import temp_html_filepath
from selenium import webdriver

from branca.element import MacroElement, Template
from shapely.geometry import mapping
from PIL import Image, ImageDraw, ImageFont
from html2image import Html2Image


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


def create_perm_and_new_df(timetable):  # noqa: C901

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
                time = spec_line[15:19]  # updated to departure time
                tiploc_type = "S"  # station

                # added to isolate DfT's 0000-0159 requirement
                if time >= "0000" and time <= "0159":
                    small_hours = 1
                else:
                    small_hours = 0

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
                        small_hours,
                    ]
                )

            elif spec_line[:2] == "LT":
                tiploc = spec_line[2:].split(" ")[0]
                station_stop += 1
                time = spec_line[15:19]  # updated to departure time
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
                        small_hours,
                    ]
                )

            elif spec_line[:2] == "LI":
                tiploc = spec_line[2:].split(" ")[0]

                # times for stations and junctions (slightly different format)
                if spec_line[10] != " ":
                    time = spec_line[15:19]  # updated to departure time
                    tiploc_type = "S"  # station
                    station_stop += 1
                else:
                    time = spec_line[20:24]
                    tiploc_type = "F"  # flyby, will be filtered out later

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
                        small_hours,
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
            "Small_hours",
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


# def filter_to_date_and_time(
#     journey_rows_df,
#     date,
#     weekday,
#     # time_slice=(["0000", "2359"]),
# ):

#     journey_rows_df[["Valid_from", "Valid_to"]] = journey_rows_df[
#         ["Valid_from", "Valid_to"]
#     ].astype("int64")

#     return journey_rows_df[
#         (journey_rows_df["Valid_from"] <= date)
#         & (journey_rows_df["Valid_to"] >= date)
#         # & (journey_rows_df["Time"] >= time_slice[0])
#         # & (journey_rows_df["Time"] <= time_slice[1])
#         & (journey_rows_df[weekday] == "1")
#     ]


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


def filter_to_date(journey_rows_df, date, cancellations=False):

    journey_rows_df[["Valid_from", "Valid_to"]] = journey_rows_df[
        ["Valid_from", "Valid_to"]
    ].astype("int64")

    # lookahead by one day
    d1 = datetime.strptime(str(date), "%y%m%d").date()
    d2 = d1 + timedelta(1)
    date2 = int(d2.strftime("%y%m%d"))

    weekday1 = calendar.day_name[d1.weekday()]
    weekday2 = calendar.day_name[d2.weekday()]

    # cancellation rows don't feature times
    if cancellations is True:
        day1 = journey_rows_df[
            (journey_rows_df[weekday1] == "1")
            & (journey_rows_df["Valid_from"] <= date)
            & (journey_rows_df["Valid_to"] >= date)
        ]

        day2 = journey_rows_df[
            (journey_rows_df[weekday2] == "1")
            & (journey_rows_df["Valid_from"] <= date2)
            & (journey_rows_df["Valid_to"] >= date2)
        ]

        output = pd.concat([day1, day2])

    # all other journey rows can be filtered by time
    else:
        core_time = journey_rows_df[
            (journey_rows_df[weekday1] == "1")
            & (journey_rows_df["Valid_from"] <= date)
            & (journey_rows_df["Valid_to"] >= date)
            & (journey_rows_df["Small_hours"] == 0)
        ]

        small_time = journey_rows_df[
            (journey_rows_df[weekday2] == "1")
            & (journey_rows_df["Valid_from"] <= date2)
            & (journey_rows_df["Valid_to"] >= date2)
            & (journey_rows_df["Small_hours"] == 1)
        ]

        output = pd.concat([core_time, small_time])

    return output


def filter_to_dft_time(
    today_rows_df,
):

    # id journeys starting between 0200 and 2359
    core_start = list(
        today_rows_df["Identifier"][
            (today_rows_df["Stop"] == 1) & (today_rows_df["Time"] >= "0200")
        ]
    )

    # id journeys starting between 0000 and 0159
    small_start = list(
        today_rows_df["Identifier"][
            (today_rows_df["Stop"] == 1) & (today_rows_df["Time"] < "0200")
        ]
    )

    core_journeys = today_rows_df[today_rows_df["Identifier"].isin(core_start)]
    small_journeys = today_rows_df[today_rows_df["Identifier"].isin(small_start)]

    return pd.concat([core_journeys, small_journeys])


def get_most_recent_file(folder_path: str, file_type: str = r"/*ZIP"):

    # retrieve list of files matching the folder path and file type
    files = glob.glob(folder_path + file_type)

    # get the most recent file
    latest_file = max(files, key=os.path.getctime)

    # return only the file name and file extension
    return os.path.basename(latest_file)


def convert_to_gpdf(df, lat_col="Latitude", long_col="Longitude"):
    return gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df[long_col], df[lat_col]))


def add_folium_times(s: pd.Series, times_prop_name: str) -> list:
    """Utility function to extend times_prop_name column to a list that
    matches the geometry shape - requirement for folium timestampedGeoJSON
    function"""
    return [s[times_prop_name]]


def scale_col(df, col_name, min_val=2, max_val=12):

    srq_root_col = np.sqrt(df[col_name])
    col_min = srq_root_col.min()
    col_max = srq_root_col.max()

    return min_val + ((srq_root_col - col_min) * (max_val - min_val)) / (
        col_max - col_min
    )


def write_tooltip(name, time, tiploc, sheduled, timetabled, percentage):
    # color of columns
    left_col_color = "#0F8243"
    right_col_color = "#EAEAEA"

    # html string, first using the area_name as the title, then adding the
    # modality, time and value to a summary table
    html = (
        """<!DOCTYPE html>
        <html>
        <head>
        <h4 style="margin-bottom:10"; width="200px">{}</h4>""".format(
            name
        )
        + """
        </head>
        <table style="height: 125px; width: 300px;">
        <tbody>
        <tr>
        <td style="background-color: """
        + left_col_color
        + """;"><span style="color: #ffffff;">Day (YYYY-MM-DD)</span></td>
        <td style="width: 150px;background-color: """
        + right_col_color
        + """;">{}</td>""".format(time)
        + """
        </tr>
        <tr>
        <td style="background-color: """
        + left_col_color
        + """;"><span style="color: #ffffff;">TIPLOC code</span></td>
        <td style="width: 150px;background-color: """
        + right_col_color
        + """;">{}</td>""".format(tiploc)
        + """
        </tr>
        <tr>
        <td style="background-color: """
        + left_col_color
        + """;"><span style="color: #ffffff;">No. Scheduled Movements</span></td>
        <td style="width: 150px;background-color: """
        + right_col_color
        + """;">{:.0f}</td>""".format(sheduled)
        + """
        </tr>
        <tr>
        <td style="background-color: """
        + left_col_color
        + """;"><span style="color: #ffffff;">No. Timetabled Movements</span></td>
        <td style="width: 150px;background-color: """
        + right_col_color
        + """;">{:.0f}</td>""".format(timetabled)
        + """
        </tr>
        <tr>
        <td style="background-color: """
        + left_col_color
        + """;"><span style="color: #ffffff;">Percentage Running</span></td>
        <td style="width: 150px;background-color: """
        + right_col_color
        + """;">{:.1f}%</td>""".format(percentage)
        + """
        </tr>
        </tbody>
        </table>
        </html>
        """
    )
    return html


def get_colour(val):
    if val == 0:
        return "#000000"
    if val < 50:
        return "#8b0000"
    elif (val >= 50) & (val < 60):
        return "#ff0000"
    elif (val >= 60) & (val < 70):
        return "#ff0066"
    elif (val >= 70) & (val < 80):
        return "#ff00cc"
    elif (val >= 80) & (val < 90):
        return "#cc00ff"
    elif (val >= 90) & (val < 100):
        return "#6600ff"
    elif val >= 100:
        return "#0000ff"
    else:
        return "#808080"


def build_legend_macro():  # noqa: E501

    template = """
    {% macro html(this, kwargs) %}

    <!doctype html>
    <html lang="en">
    <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title></title>
    <link rel="stylesheet" href="//code.jquery.com/ui/1.12.1/themes/base/jquery-ui.css">

    <script src="https://code.jquery.com/jquery-1.12.4.js"></script>
    <script src="https://code.jquery.com/ui/1.12.1/jquery-ui.js"></script>

    <script>
    $( function() {
        $( "#maplegend" ).draggable({
                        start: function (event, ui) {
                            $(this).css({
                                right: "auto",
                                top: "auto",
                                bottom: "auto"
                            });
                        }
                    });
    });

    </script>
    </head>
    <body>


    <div id='maplegend' class='maplegend'
        style='position: absolute; z-index:9999; border:2px solid grey; background-color:rgba(255, 255, 255, 0.8);
        border-radius:6px; padding: 10px; font-size:14px; right: 10px; bottom: 200px;'>

    <div class='legend-title'>Percentage of Timetabled<br>Services Running</div>
    <div class='legend-scale'>
    <ul class='legend-labels'>
        <li><span style='background:#000000;opacity:0.5;'></span>0%</li>
        <li><span style='background:#8b0000;opacity:0.5;'></span>(0%, 50%)</li>
        <li><span style='background:#ff0000;opacity:0.5;'></span>[50%, 60%)</li>
        <li><span style='background:#ff0066;opacity:0.5;'></span>[60%, 70%)</li>
        <li><span style='background:#ff00cc;opacity:0.5;'></span>[70%, 80%)</li>
        <li><span style='background:#cc00ff;opacity:0.5;'></span>[80%, 90%)</li>
        <li><span style='background:#6600ff;opacity:0.5;'></span>[90%, 100%)</li>
        <li><span style='background:#0000ff;opacity:0.5;'></span>≥100%</li>
    </ul>
    </div>
    </div>

    </body>
    </html>

    <style type='text/css'>
    .maplegend .legend-title {
        text-align: left;
        margin-bottom: 5px;
        font-weight: bold;
        font-size: 90%;
        }
    .maplegend .legend-scale ul {
        margin: 0;
        margin-bottom: 5px;
        padding: 0;
        float: left;
        list-style: none;
        }
    .maplegend .legend-scale ul li {
        font-size: 80%;
        list-style: none;
        margin-left: 0;
        line-height: 18px;
        margin-bottom: 2px;
        }
    .maplegend ul.legend-labels li span {
        display: block;
        float: left;
        height: 16px;
        width: 30px;
        margin-right: 5px;
        margin-left: 0;
        border: 1px solid #999;
        }
    .maplegend .legend-source {
        font-size: 80%;
        color: #777;
        clear: both;
        }
    .maplegend a {
        color: #777;
        }
    </style>
    {% endmacro %}"""

    macro = MacroElement()
    macro._template = Template(template)
    return macro


def build_features(gp_df):

    features = [
        {
            "type": "Feature",
            "geometry": {
                "type": mapping(row["geometry"])["type"],
                "coordinates": mapping(row["geometry"])["coordinates"],
            },
            "properties": {
                "times": row["times"],
                "popup": write_tooltip(
                    row["Station_Name"],
                    row["times"][0],
                    row["TIPLOC"],
                    row["journeys_scheduled"],
                    row["journeys_timetabled"],
                    row["pct_timetabled_services_running"],
                ),
                "style": {"color": ""},
                "icon": "circle",
                "iconstyle": {
                    "fillColor": get_colour(row["pct_timetabled_services_running"]),
                    "fillOpacity": 0.5,
                    "radius": row["radius"],
                },
            },
        }
        for _, row in gp_df.iterrows()
    ]

    return features


def build_base_map(
    full_screen: bool, mini_map: bool, add_geocoder: bool, measure_control: bool
):

    m = folium.Map(
        tiles="openstreetmap",
        max_bounds=True,
    )

    if full_screen:
        m.add_child(Fullscreen())

    if mini_map:
        m.add_child(MiniMap())

    if add_geocoder:
        m.add_child(Geocoder(add_marker=False, collapsed=True))

    # add measuring controls if requested
    if measure_control:
        m.add_child(
            MeasureControl(
                primary_length_unit="kilometers",
            )
        )

    return m


def add_timestamped_geojson(m, features):

    # add TimestampGeoJson to the area
    TimestampedGeoJson(
        {
            "type": "FeatureCollection",
            "features": features,
        },
        transition_time=2000,
        period="P1D",
        duration="PT1s",
        max_speed=2,
        date_options="YYYY-MM-DD",
        auto_play=False,
    ).add_to(m)

    # fit view to bounds
    m.fit_bounds(m.get_bounds())

    return m


def add_logo(m):

    logo_filepath = os.path.join(here(), "src", "images", "logo_reduced.png")

    with open(logo_filepath, "rb") as lf:
        # open in binary mode, read bytes, encode, decode obtained bytes as utf-8 string
        b64_content = base64.b64encode(lf.read()).decode("utf-8")

    FloatImage("data:image/png;base64,{}".format(b64_content), bottom=7, left=1).add_to(
        m
    )

    return m


def add_build_date(m):

    build_date_filepath = os.path.join(here(), "src", "images", "build_text.png")

    W, H = (200, 200)
    im = Image.new("RGBA", (W, H))
    draw = ImageDraw.Draw(im)
    msg = "Generated on {}".format(datetime.now().date().strftime("%Y-%m-%d"))
    fnt = ImageFont.truetype("/Library/Fonts/Arial.ttf", 14)
    _, _, w, h = fnt.getbbox(msg)
    draw.text((0, 0), msg, font=fnt, fill=(0, 0, 0))
    im.crop((0, 0, w, h)).save(build_date_filepath, "PNG")

    with open(build_date_filepath, "rb") as lf:
        # open in binary mode, read bytes, encode, decode obtained bytes as utf-8 string
        b64_content = base64.b64encode(lf.read()).decode("utf-8")

    FloatImage("data:image/png;base64,{}".format(b64_content), bottom=5, left=1).add_to(
        m
    )

    return m


def build_static_visual(folder_path, date, place, m):

    png_filename = f"full_uk_disruption_summary_{date}_{place}.png"

    options = webdriver.firefox.options.Options()
    options.add_argument("--headless")
    driver = webdriver.Firefox(options=options)

    html = m.get_root().render()
    with temp_html_filepath(html) as fname:
        # We need the tempfile to avoid JS security issues.
        driver.get("file:///{path}".format(path=fname))
        driver.set_window_position(0, 0)
        driver.set_window_size(1920, 1080)
        time.sleep(5)
        img_data = driver.get_screenshot_as_png()
        driver.quit()

    img = Image.open(io.BytesIO(img_data))
    img.save(os.path.join(folder_path, png_filename))
    # hti = Html2Image(
    #     custom_flags=[
    #         "--virtual-time-budget=250",
    #         "--hide-scrollbars",
    #     ],
    #     output_path=folder_path,
    # )

    # hti.screenshot(html_str=html_str, save_as=png_filename)

    # del hti

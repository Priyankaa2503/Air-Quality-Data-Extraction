import gpxpy
import gpxpy.gpx
import pandas as pd
import pytz
from pytz import all_timezones


# Function to convert datetime from gpx to 2024-04-16 format


import xml.etree.ElementTree as ET
import csv
from datetime import datetime


def parse_custom_time(time_str):
    dt = datetime.strptime(time_str, "%m/%d/%Y, %I:%M:%S %p")
    return dt.strftime("%Y-%m-%d"), dt.strftime("%H:%M:%S")


# Data Extraction from gpx


gpx_file_path = "danielle GPX .GPX"
tree = ET.parse(gpx_file_path)
root = tree.getroot()

namespaces = {"default": "http://www.topografix.com/GPX/1/1"}

data = []
for trkpt in root.findall(".//default:trkpt", namespaces):
    lat = trkpt.get("lat")
    lon = trkpt.get("lon")
    ele = trkpt.find("default:ele", namespaces).text
    time = trkpt.find("default:time", namespaces).text
    date, time = parse_custom_time(time)
    data.append(
        {
            "latitude": lat,
            "longitude": lon,
            "altitude (m)": ele,
            "date": date,
            "time": time,
        }
    )



gpx_data = pd.DataFrame(data)
gpx_data.head()


# Import GPX Data to CSV



gpx_data.to_csv("danielle.csv", index=False)


# https://gist.github.com/pianosnake/b4a45ef6bgpx_data2ffb2e1b44bbcca107298

# Function to get boundary box from lat,long



import math

EARTH_CIR_METERS = 40075016.686
degreesPerMeter = 360 / EARTH_CIR_METERS


def toRadians(degrees):
    return degrees * math.pi / 180


def latLngToBounds(lat, lng, zoom, width, height):
    metersPerPixelEW = EARTH_CIR_METERS / math.pow(2, zoom + 8)
    metersPerPixelNS = (
        EARTH_CIR_METERS / math.pow(2, zoom + 8) * math.cos(toRadians(lat))
    )

    shiftMetersEW = width / 2 * metersPerPixelEW
    shiftMetersNS = height / 2 * metersPerPixelNS

    shiftDegreesEW = shiftMetersEW * degreesPerMeter
    shiftDegreesNS = shiftMetersNS * degreesPerMeter

    minX = lng - shiftDegreesEW
    minY = lat - shiftDegreesNS
    maxX = lng + shiftDegreesEW
    maxY = lat + shiftDegreesNS

    return f"{minX:.4f},{minY:.6f},{maxX:.4f},{maxY:.6f}"





gpx_data["latitude"] = gpx_data["latitude"].astype(float)
gpx_data["longitude"] = gpx_data["longitude"].astype(float)

gpx_data["bbox"] = gpx_data.apply(
    lambda x: latLngToBounds(x["latitude"], x["longitude"], 12, 400, 400), axis=1
)


# Getting bbox for all gpx data



gpx_data.head()

import requests
import csv
from io import StringIO


def get_air_quality(gpx_data):
    hour = gpx_data["time"].split(":")[0]
    header_array = [
        "Latitude",
        "Longitude",
        "UTC",
        "Parameter",
        "Unit",
        "AQI",
        "Category",
    ]
    url = f"https://www.airnowapi.org/aq/data/?startDate={gpx_data['date']}T{hour}&endDate={gpx_data['date']}T{hour}&parameters=PM25,PM10&BBOX={gpx_data['bbox']}&dataType=A&format=text/csv&verbose=0&monitorType=0&includerawconcentrations=0&API_KEY=342FB14E-3637-470D-BEAE-A5DF1E193ADB"
    response = requests.get(url)
    return response.text


# Get air quality for first 400 rows from gpx data


import pandas as pd
from io import StringIO

results = []
for index, row in gpx_data.head(400).iterrows():
    results.append(get_air_quality(row))

results_str = "\n".join(results)

data_io = StringIO(results_str)
df_temp = pd.read_csv(data_io, header=None)

df_temp.columns = [
    "Latitude",
    "Longitude",
    "UTC",
    "Parameter",
    "AQI",
    "Category",
]


df_temp.head()
df_temp.to_csv("air_quality.csv", index=False)


# Get air quality for next 400 rows from gpx data


for index, row in gpx_data.iloc[400:700].iterrows():
    results.append(get_air_quality(row))

results_str = "\n".join(results)

data_io = StringIO(results_str)
df_temp = pd.read_csv(data_io, header=None)

df_temp.columns = [
    "Latitude",
    "Longitude",
    "UTC",
    "Parameter",
    "AQI",
    "Category",
]

with open("air_quality.csv", "a") as f:
    df_temp.to_csv(f, header=False, index=False)


# Data extraction from survey data



import pandas as pd
import os

directory = "surveyData"

dataframes = {}

for filename in os.listdir(directory):
    if filename.endswith(".csv"):
        dataframes[filename] = pd.read_csv(os.path.join(directory, filename))


# Dictionary of dataframes




dataframes.keys()


# Assigning variables to all survey data



ping1 = dataframes["Ping1.csv"]
ping2 = dataframes["Ping2.csv"]
ping3 = dataframes["Ping3.csv"]
ping4 = dataframes["Ping4.csv"]
ping5 = dataframes["Ping5.csv"]
ping6 = dataframes["Ping6.csv"]





ping1.head()


# Function for matching the timestamp and location from survey data to air quality data and  for calculating the average pollution exposure to PM2.5 and PM10 for the hour prior to each survey timestamp




import pandas as pd
from datetime import datetime, timedelta


def process_ping_data(ping, air_quality_path="air_quality.csv"):
    ping["bbox"] = ping.apply(
        lambda x: latLngToBounds(x["LONGITUDE"], x["LATITUDE"], 12, 400, 400), axis=1
    )

    def isInsideBbox(lat, lng, bbox):
        lng = float(lng)
        lat = float(lat)
        bbox = bbox.split(",")
        if (
            lng >= float(bbox[0])
            and lng <= float(bbox[2])
            and lat >= float(bbox[1])
            and lat <= float(bbox[3])
        ):
            return True
        return False

    results = []

    air_quality = pd.read_csv(air_quality_path)

    ping["actual_start_local"] = pd.to_datetime(ping["actual_start_local"])
    ping["hour"] = ping["actual_start_local"].dt.hour - 1
    air_quality["time"] = pd.to_datetime(air_quality["UTC"])
    air_quality["hour"] = air_quality["time"].dt.hour

    ping["date"] = ping["actual_start_local"].dt.date

    air_quality["date"] = air_quality["time"].dt.date

    for index, row in ping.iterrows():
        op = [] 
        for index1, row1 in air_quality.iterrows():
            if (
                isInsideBbox(row1["Latitude"], row1["Longitude"], row["bbox"])
                and row["hour"] == row1["hour"]
                and row["date"] == row1["date"]
            ):
                op.append(
                    {
                        "Latitude": row1["Latitude"],
                        "Longitude": row1["Longitude"],
                        "UTC": row1["UTC"],
                        "Parameter": row1["Parameter"],
                        "AQI": row1["AQI"],
                        "Category": row1["Category"],
                    }
                )
        results.append(pd.DataFrame(op))

    avg_PM25 = {}
    avg_PM10 = {}

    for i, df in enumerate(results):
        if not df.empty:
            avg_PM25[i] = df[df["Parameter"] == "PM2.5"]["AQI"].mean()
            avg_PM10[i] = df[df["Parameter"] == "PM10"]["AQI"].mean()
        else:
            avg_PM25[i] = None
            avg_PM10[i] = None

    ping["avg_PM25"] = pd.Series(avg_PM25)
    ping["avg_PM10"] = pd.Series(avg_PM10)

    return ping



# Save data to new files with avg exposure added




for key in dataframes.keys():
    dataframes[key] = process_ping_data(dataframes[key])

for key, df in dataframes.items():
    df.to_csv(f"./OutputData/{key}_avgAQI.csv", index=False)


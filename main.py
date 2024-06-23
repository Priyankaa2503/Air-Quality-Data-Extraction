import gpxpy
import gpxpy.gpx
import pandas as pd
import pytz
from pytz import all_timezones
import xml.etree.ElementTree as ET
import csv
from datetime import datetime, timedelta
import math
import requests
from io import StringIO
import os


class AirQualityAnalyzer:
    def __init__(self, gpx_file_path, api_key, survey_data_directory, output_directory):
        self.gpx_file_path = gpx_file_path
        self.api_key = api_key
        self.survey_data_directory = survey_data_directory
        self.output_directory = output_directory
        self.gpx_data = None
        self.air_quality_data = None
        self.survey_dataframes = {}

    def parse_custom_time(self, time_str):
        dt = datetime.strptime(time_str, "%m/%d/%Y, %I:%M:%S %p")
        return dt.strftime("%Y-%m-%d"), dt.strftime("%H:%M:%S")

    def extract_gpx_data(self):
        tree = ET.parse(self.gpx_file_path)
        root = tree.getroot()

        namespaces = {"default": "http://www.topografix.com/GPX/1/1"}

        data = []
        for trkpt in root.findall(".//default:trkpt", namespaces):
            lat = trkpt.get("lat")
            lon = trkpt.get("lon")
            ele = trkpt.find("default:ele", namespaces).text
            time = trkpt.find("default:time", namespaces).text
            date, time = self.parse_custom_time(time)
            data.append(
                {
                    "latitude": lat,
                    "longitude": lon,
                    "altitude (m)": ele,
                    "date": date,
                    "time": time,
                }
            )

        self.gpx_data = pd.DataFrame(data)

    def save_gpx_data_to_csv(self, file_name="gpx_data.csv"):
        self.gpx_data.to_csv(file_name, index=False)

    def latLngToBounds(self, lat, lng, zoom, width, height):
        EARTH_CIR_METERS = 40075016.686
        degreesPerMeter = 360 / EARTH_CIR_METERS

        def toRadians(degrees):
            return degrees * math.pi / 180

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

    def add_bounding_boxes_to_gpx(self):
        self.gpx_data["latitude"] = self.gpx_data["latitude"].astype(float)
        self.gpx_data["longitude"] = self.gpx_data["longitude"].astype(float)

        self.gpx_data["bbox"] = self.gpx_data.apply(
            lambda x: self.latLngToBounds(x["latitude"], x["longitude"], 12, 400, 400),
            axis=1,
        )

    def get_air_quality(self, gpx_row):
        hour = gpx_row["time"].split(":")[0]
        url = (
            f"https://www.airnowapi.org/aq/data/?startDate={gpx_row['date']}T{hour}&endDate={gpx_row['date']}T{hour}"
            f"&parameters=PM25,PM10&BBOX={gpx_row['bbox']}&dataType=A&format=text/csv&verbose=0&monitorType=0"
            f"&includerawconcentrations=0&API_KEY={self.api_key}"
        )
        response = requests.get(url)
        return response.text

    def fetch_air_quality_data(self, rows=400):
        results = []
        for index, row in self.gpx_data.head(rows).iterrows():
            results.append(self.get_air_quality(row))

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

        self.air_quality_data = df_temp

    def append_air_quality_data(self, start_row, end_row):
        results = []
        for index, row in self.gpx_data.iloc[start_row:end_row].iterrows():
            results.append(self.get_air_quality(row))

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

    def load_survey_data(self):
        for filename in os.listdir(self.survey_data_directory):
            if filename.endswith(".csv"):
                self.survey_dataframes[filename] = pd.read_csv(
                    os.path.join(self.survey_data_directory, filename)
                )

    def process_ping_data(self, ping):
        ping["bbox"] = ping.apply(
            lambda x: self.latLngToBounds(x["LONGITUDE"], x["LATITUDE"], 12, 400, 400),
            axis=1,
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

        air_quality = pd.read_csv("air_quality.csv")

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

    def process_all_survey_data(self):
        for key in self.survey_dataframes.keys():
            self.survey_dataframes[key] = self.process_ping_data(
                self.survey_dataframes[key]
            )

    def save_processed_survey_data(self):
        for key, df in self.survey_dataframes.items():
            df.to_csv(f"{self.output_directory}/{key}_avgAQI.csv", index=False)


if __name__ == "__main__":
    analyzer = AirQualityAnalyzer(
        gpx_file_path="danielle GPX .GPX",
        api_key="342FB14E-3637-470D-BEAE-A5DF1E193ADB",
        survey_data_directory="surveyData",
        output_directory="OutputData",
    )

    analyzer.extract_gpx_data()
    analyzer.save_gpx_data_to_csv("danielle.csv")
    analyzer.add_bounding_boxes_to_gpx()
    # analyzer.fetch_air_quality_data(400)
    analyzer.append_air_quality_data(710, 720)
    analyzer.load_survey_data()
    analyzer.process_all_survey_data()
    analyzer.save_processed_survey_data()

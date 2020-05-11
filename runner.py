import configparser
import datetime
import os

import pandas as pd
from dateutil.relativedelta import relativedelta
from pytz import timezone

from azure_blob import AzureBlob
from meter_session_manager import MeterSessionManager

# Set Storage Mode:
BLOB_ENABLED = True if os.getenv("BLOB_ENABLED") else False

# Prepare Secrets
if not os.getenv("FETCH_SECRETS_FROM_ENVIRONMENT"):
    assert os.path.exists("secrets.ini")
    key_config = configparser.ConfigParser()
    key_config.read("secrets.ini")
    assert key_config
    username = key_config['CREDENTIALS']['SMART_METER_USERNAME']
    password = key_config['CREDENTIALS']['SMART_METER_PASSWORD']
    if BLOB_ENABLED:
        blob_account_name = key_config['AZURE_BLOB']['BLOB_ACCOUNT_NAME']
        blob_account_key = key_config['AZURE_BLOB']['BLOB_ACCOUNT_KEY']
        blob_container_name = key_config['AZURE_BLOB']['BLOB_CONTAINER_NAME']
else:
    username = os.getenv("SMART_METER_USERNAME")
    password = os.getenv("SMART_METER_PASSWORD")
    if BLOB_ENABLED:
        blob_account_name = os.getenv("BLOB_ACCOUNT_NAME")
        blob_account_key = os.getenv("BLOB_ACCOUNT_KEY")
        blob_container_name = os.getenv("BLOB_CONTAINER_NAME")

assert username and password, "Could not source USERNAME and PASSWORD!"
if BLOB_ENABLED:
    assert blob_account_name and blob_account_key and blob_container_name, "Could not source BLOB Credentials"

# Set Data Files
METER_INFO_DATAFILE = "meter_info.csv"
MONTHLY_TRENDS_DATAFILE = "monthly_trends.csv"
DAILY_TRENDS_DATAFILE = "daily_trends.csv"
INTERVAL_TRENDS_DATAFILE = "interval_trends.csv"
LAST_BILLED_METER_READING_DATAFILE = "last_billed_meter_reading.csv"
LATEST_METER_READING_DATAFILE = "latest_meter_reading.csv"
USAGE_SINCE_LAST_READING_DATAFILE = "usage_since_last_reading.csv"
CURRENT_USAGE_DATAFILE = "current_usage.csv"
PAST_24_HOUR_TREND_DATAFILE = "past_24_hour_trend.csv"
HISTORIC_HOURLY_TREND_DATAFILE = "historic_hourly_trend.csv"

data_files_list = [METER_INFO_DATAFILE,
                   MONTHLY_TRENDS_DATAFILE,
                   DAILY_TRENDS_DATAFILE,
                   INTERVAL_TRENDS_DATAFILE,
                   LAST_BILLED_METER_READING_DATAFILE,
                   LATEST_METER_READING_DATAFILE,
                   USAGE_SINCE_LAST_READING_DATAFILE,
                   CURRENT_USAGE_DATAFILE,
                   PAST_24_HOUR_TREND_DATAFILE,
                   HISTORIC_HOURLY_TREND_DATAFILE]

# Prepare Local Data File Path
data_file_path = os.path.join(os.path.abspath(os.path.curdir), "data_files")
os.makedirs(data_file_path, exist_ok=True)


# Write File to Local
def write_data_to_file_as_pdf(data, file_name):
    try:
        if isinstance(data, dict):
            try:
                df = pd.DataFrame(data, index=[0])
            except:
                df = pd.DataFrame.from_dict(data)
        elif isinstance(data, list):
            df = pd.DataFrame(data)
        else:
            raise NotImplementedError
        local_file_name = os.path.join(data_file_path, file_name)
        df.to_csv(local_file_name, index=False)
    except Exception as e:
        print("Failed to Write Data to File: [{}]".format(file_name))


# Read File from Local
def read_data_from_file_as_pdf(file_name):
    try:
        local_file_name = os.path.join(data_file_path, file_name)
        return pd.read_csv(local_file_name)
    except Exception as e:
        print("Failed to Read Data from File: [{}]".format(file_name))
        return None


# Download All Files from Blob
def download_all_files_from_blob():
    blob_obj = AzureBlob(account_name=blob_account_name, account_key=blob_account_key,
                         container_name=blob_container_name)
    for file_name in data_files_list:
        try:
            blob_obj.download_files_from_blob(local_path=data_file_path, file_name=file_name)
        except Exception as e:
            print("Failed to Retrieve File: [{}] from BLOB".format(file_name))


# Download All Files from Blob
def upload_all_files_to_blob():
    blob_obj = AzureBlob(account_name=blob_account_name, account_key=blob_account_key,
                         container_name=blob_container_name)
    for file_name in data_files_list:
        try:
            blob_obj.upload_file_to_blob(local_path=data_file_path, file_name=file_name)
        except Exception as e:
            print("Failed to Upload File: [{}] to BLOB".format(file_name))


if __name__ == "__main__":
    try:
        print("#" * 30)
        start_time = datetime.datetime.now(tz=timezone("US/Central"))
        print("Fetch Usage Started At: [{}]".format(start_time))
        if BLOB_ENABLED:
            download_all_files_from_blob()
        msm = MeterSessionManager(username=username, password=password)
        msm.set_auth_keys()
        dashboard_meta = msm.get_dashboard()
        meter_master_info = msm.meter_details
        if meter_master_info:
            meter_info = {
                "ADDRESS": meter_master_info['fullAddress'],
                "METER_NUMBER": meter_master_info['meterNumber'],
                "ESIID": meter_master_info['esiid']
            }
            write_data_to_file_as_pdf(meter_info, METER_INFO_DATAFILE)

        usageData = dashboard_meta.get("usageData")
        interval_usage = list()
        for x in usageData:
            usage_date_time = "{date}{time}".format(date=x['date'], time=x['endtime']).upper()
            usage_date_time = datetime.datetime.strptime(usage_date_time, "%Y-%m-%d %I:%M %p")
            usage = x['consumption']
            interval_usage.append({"USAGE_TIME": usage_date_time, "USAGE": usage})
        if interval_usage:
            write_data_to_file_as_pdf(interval_usage, INTERVAL_TRENDS_DATAFILE)

        monthly_trends = msm.get_monthly_usage_trends(12)
        if monthly_trends:
            write_data_to_file_as_pdf(monthly_trends, MONTHLY_TRENDS_DATAFILE)

        daily_trends = msm.get_daily_usage_trends(45)
        if daily_trends:
            write_data_to_file_as_pdf(daily_trends, DAILY_TRENDS_DATAFILE)

        latest_billed_data = msm.get_latest_billed_reading()
        if latest_billed_data:
            write_data_to_file_as_pdf(latest_billed_data, LAST_BILLED_METER_READING_DATAFILE)

        usage_since_last_on_demand_reading, current_meter_reading = msm.get_on_demand_read()
        if current_meter_reading:
            write_data_to_file_as_pdf(current_meter_reading, LATEST_METER_READING_DATAFILE)
        if usage_since_last_on_demand_reading:
            write_data_to_file_as_pdf(usage_since_last_on_demand_reading, USAGE_SINCE_LAST_READING_DATAFILE)

        current_usage = current_meter_reading["CURRENT_READING"] - latest_billed_data["LAST_BILLED_READING"]
        current_usage = {"CURRENT_CYCLE_USAGE": current_usage}
        if current_usage:
            write_data_to_file_as_pdf(current_usage, CURRENT_USAGE_DATAFILE)

        if os.path.exists(os.path.join(data_file_path, PAST_24_HOUR_TREND_DATAFILE)):
            past_24_hour_trend_df = read_data_from_file_as_pdf(PAST_24_HOUR_TREND_DATAFILE)
            trend_start_time = start_time - datetime.timedelta(hours=24)
            trend_start_time = trend_start_time.replace(tzinfo=None)
            past_24_hour_trend_df['READING_TIME'] = past_24_hour_trend_df['READING_TIME'].astype('datetime64[ns]')
            past_24_hour_trend_df = past_24_hour_trend_df[past_24_hour_trend_df["READING_TIME"] >= trend_start_time]
            past_24_hour_trend_dict = past_24_hour_trend_df.to_dict(orient='list')
            past_24_hour_trend_dict["READING_TIME"] = [x.to_pydatetime() for x in
                                                       past_24_hour_trend_dict["READING_TIME"]]
        else:
            past_24_hour_trend_dict = {"READING_TIME": list(), "METER_READING": list()}

        if current_meter_reading["CURRENT_READING_TIME"] not in past_24_hour_trend_dict["READING_TIME"]:
            past_24_hour_trend_dict["READING_TIME"].append(current_meter_reading["CURRENT_READING_TIME"])
            past_24_hour_trend_dict["METER_READING"].append(current_meter_reading["CURRENT_READING"])
            write_data_to_file_as_pdf(past_24_hour_trend_dict, PAST_24_HOUR_TREND_DATAFILE)

        if os.path.exists(os.path.join(data_file_path, HISTORIC_HOURLY_TREND_DATAFILE)):
            historic_hourly_trend_df = read_data_from_file_as_pdf(HISTORIC_HOURLY_TREND_DATAFILE)
            historic_hourly_trend_df['READING_TIME'] = historic_hourly_trend_df['READING_TIME'].astype('datetime64[ns]')
            historic_hourly_trend_dict = historic_hourly_trend_df.to_dict(orient='list')
            historic_hourly_trend_dict["READING_TIME"] = [x.to_pydatetime() for x in
                                                       historic_hourly_trend_dict["READING_TIME"]]
        else:
            historic_hourly_trend_dict = {"READING_TIME": list(), "METER_READING": list()}

        if current_meter_reading["CURRENT_READING_TIME"] not in historic_hourly_trend_dict["READING_TIME"]:
            historic_hourly_trend_dict["READING_TIME"].append(current_meter_reading["CURRENT_READING_TIME"])
            historic_hourly_trend_dict["METER_READING"].append(current_meter_reading["CURRENT_READING"])
            write_data_to_file_as_pdf(historic_hourly_trend_dict, HISTORIC_HOURLY_TREND_DATAFILE)

        print("-" * 30)
        print(read_data_from_file_as_pdf(PAST_24_HOUR_TREND_DATAFILE))
        print("\n")
        print("-" * 30)
        print(read_data_from_file_as_pdf(CURRENT_USAGE_DATAFILE))
        print("-" * 30)
        end_time = datetime.datetime.now(tz=timezone("US/Central"))
        print("Fetch Usage Ended At: [{}]".format(end_time))
        elapsed_time = relativedelta(end_time, start_time)
        print("Time Taken: [{}]Minutes [{}]Seconds".format(elapsed_time.minutes, elapsed_time.seconds))
        print("#" * 30)
        print("\n")
    except Exception as e:
        print(e)
    finally:
        if BLOB_ENABLED:
            upload_all_files_to_blob()

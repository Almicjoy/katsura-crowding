from flask import Flask, render_template, request
from flask_cors import CORS
import numpy as np
import pandas as pd
import requests
import os
import json
from requests.auth import HTTPBasicAuth
import datetime
import pytz
from datetime import timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from concurrent.futures import ThreadPoolExecutor, as_completed

app = Flask(__name__)
CORS(app)

sched = BackgroundScheduler(daemon=True)

# Set default timezone to Japan Time Zone
jst = pytz.timezone('Asia/Tokyo')

# Define function to round the time ------------------------------------------------------------------------
def roundTime(dt, roundTo=15):
    ''' This function ensures that the time is in blocks of 'roundTo' seconds '''
    dt = dt - datetime.timedelta(minutes=dt.minute % roundTo,
                                seconds=dt.second,
                                microseconds=dt.microsecond)

    return dt


# Read in the required csv file and format that columns appropriately ----------------------------
historical_averages = {}
files = os.listdir("historical_averages")
for file in files:
    print("File: ", file)
    df = pd.read_csv("historical_averages/"+file)
    df['Time'] = pd.to_datetime(df['Time'], format='mixed')
    df['Time'] = df['Time'].apply(lambda x: x.time())
    historical_averages[file] = df
    # print(df)

# Keep a dictionary of the days of the week to be used in getting the
# corresponding averages
week_days = {0:"Monday", 1:"Tuesday", 2:"Wednesday", 3:"Thursday", 4:"Friday", 5:"Saturday", 6:"Sunday"}

# This variable will store the preloaded live data
LIVE_DATA = [pd.DataFrame({}), pd.DataFrame({})]
TIME = [datetime.datetime.now(jst)]
SENSOR = "AMPM18-KJ016"

@app.route("/day_average", defaults={'sensor':SENSOR})
@app.route("/day_average/<sensor>")
def get_day_average(sensor):
    df = historical_averages[sensor+".csv"]
    time = datetime.datetime.now(jst)
    day = time.weekday()

    try:
        day = week_days[int(day)]
        message = "SUCCESS"
        day_average = df[['Time', day]]
        day_average = day_average.rename(columns={"Time":"time", day:"count"})
        data = day_average.to_json(orient='records')
        data = json.loads(data)
    except:
        message = "INVALID_DATE"
        data = {}

    TIME[0] = time

    return {"message":message, "data":data, "sensor": sensor}



def get_live_data(time):
    timeCode = time.strftime("%H") + time.strftime("%M")
    dataURL = 'https://ampdev6.jriss.jp/katsura/csv/5min/' + timeCode + '.csv'
    print("Data URL: ", dataURL)
    response = requests.get(dataURL, auth=HTTPBasicAuth('katsura', 'katsura'), stream=True)
    df = pd.read_csv(response.raw)
    df['TIMESTAMP'] = pd.to_datetime(df['TIMESTAMP'])
    df['TIMESTAMP'] = df['TIMESTAMP'].dt.tz_localize("Asia/Tokyo")

    return df


def get_aggregated_data(live_data, aggregate=60, time=TIME):
    time1 = time[0]
    time1 = roundTime(time1, roundTo=5)
    print("Time: ", time1)

    # Generate time points for 15-min data (3 requests) and 60-min data (12 requests)
    times_15min = [time1 - timedelta(minutes=5*i) for i in range(3)]
    times_60min = [time1 - timedelta(minutes=5*i) for i in range(12)]

    # Fetch all data in parallel using ThreadPoolExecutor
    print("Fetching data in parallel...")
    with ThreadPoolExecutor(max_workers=8) as executor:
        # Submit all requests
        futures_15min = {executor.submit(get_live_data, t): t for t in times_15min}
        futures_60min = {executor.submit(get_live_data, t): t for t in times_60min}
        
        # Collect results for 15-min data
        dfs_15min = []
        for future in as_completed(futures_15min):
            try:
                dfs_15min.append(future.result())
            except Exception as e:
                print(f"Error fetching 15-min data: {e}")
        
        # Collect results for 60-min data
        dfs_60min = []
        for future in as_completed(futures_60min):
            try:
                dfs_60min.append(future.result())
            except Exception as e:
                print(f"Error fetching 60-min data: {e}")

    # Concatenate results
    if dfs_15min:
        df_15 = pd.concat(dfs_15min).reset_index(drop=True)
        live_data[0] = df_15.copy()
    
    if dfs_60min:
        df_60 = pd.concat(dfs_60min).reset_index(drop=True)
        live_data[1] = df_60.copy()

    print("Parallel data fetch complete")
    return live_data[1] if dfs_60min else pd.DataFrame({})


def count_users(df, sensor):
    if sensor != None:
        df = df[df['AMPID']==sensor]
    df = df.reset_index(drop=True)
    count = len(df.AMAC.unique())
    return (df,count)



get_aggregated_data(LIVE_DATA)
print(LIVE_DATA)
sched.add_job(get_aggregated_data,'interval', minutes=1, args=[LIVE_DATA])


CAFE_SENSORS = ["AMPM18-KJ010", "AMPM18-KJ016", "AMPM18-KJ017"]

@app.route("/service-level-api", defaults={'sensor':SENSOR})
@app.route("/service-level-api/<sensor>")
def service_level(sensor, live_data=LIVE_DATA, time=TIME):
    time = TIME[0]

    if sensor in CAFE_SENSORS:
        df = live_data[0].copy()
        # start = roundTime(time, roundTo=5)
        # end = start - timedelta(minutes=15)
        # df = df[df['TIMESTAMP'] >= end]
        time = roundTime(time, roundTo=15)
    else:
        df = live_data[1].copy()
        time = roundTime(time, roundTo=60)

    df,count = count_users(df, sensor=sensor)
    print("Count: ", count)

    time_to_display = time.strftime('%A, %B %d, %Y')
    time = "{:02d}:{:02d}".format(time.hour, time.minute)
    print("Returned time: ", time)

    # return df.to_html()
    response = {"sensor":sensor,
                "time": time,
                "count":count,
                "time_to_display": time_to_display}

    return response


if __name__ == "__main__":
    sched.start()
    app.run(port=5001)

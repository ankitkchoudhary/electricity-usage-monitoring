import configparser
import os
from datetime import datetime

import pandas as pd
import streamlit as st
from bokeh.layouts import gridplot
from bokeh.models import (ColumnDataSource, NumeralTickFormatter, HoverTool,
                          Span)
from bokeh.plotting import figure

from azure_blob import AzureBlob

# Set Storage Mode:
BLOB_ENABLED = True if os.getenv("BLOB_ENABLED") else False
BLOB_ENABLED = True

# Prepare Secrets
if BLOB_ENABLED:
    if os.getenv("FETCH_SECRETS_FROM_ENVIRONMENT"):
        blob_account_name = os.getenv("BLOB_ACCOUNT_NAME")
        blob_account_key = os.getenv("BLOB_ACCOUNT_KEY")
        blob_container_name = os.getenv("BLOB_CONTAINER_NAME")
    else:
        assert os.path.exists("secrets.ini")
        key_config = configparser.ConfigParser()
        key_config.read("secrets.ini")
        blob_account_name = key_config['AZURE_BLOB']['BLOB_ACCOUNT_NAME']
        blob_account_key = key_config['AZURE_BLOB']['BLOB_ACCOUNT_KEY']
        blob_container_name = key_config['AZURE_BLOB']['BLOB_CONTAINER_NAME']
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


def _max_width_():
    max_width_str = f"max-width: 2000PX;"
    st.markdown(
        f"""
    <style>
    .reportview-container .main .block-container{{
        {max_width_str}
    }}
    </style>
    """,
        unsafe_allow_html=True,
    )


def grid_plot(list_df, x_col, y_cols, xaxis_label, yaxis_label, span_col=None, scatter=True, tick_interval=None):
    grid_children = []
    for df in list_df:
        colors = ['rgb(114,160,193)', 'rgb(175,0,42)', 'rgb(255,191,0)', 'rgb(59,122,87)', 'rgb(242,103,0)']
        source = ColumnDataSource(data=df)
        tools_to_show = 'box_zoom,pan,save,reset,wheel_zoom'
        p = figure(x_range=df[x_col].tolist(),
                   plot_height=300,
                   y_axis_label=yaxis_label,
                   toolbar_location='right',
                   tools=tools_to_show)

        for i in range(len(y_cols)):
            c = p.line(x_col, y_cols[i],
                       source=source,
                       line_width=2,
                       color=colors[i])
            if scatter:
                circle = p.circle(x_col, y_cols[i],
                                  source=source,
                                  fill_color=colors[i],
                                  color=colors[i],
                                  size=6)

                p.add_tools(HoverTool(tooltips=[(f"{y_cols[i]}", "@%s{'0.00'}" % (y_cols[i]))],
                                      renderers=[circle], mode='mouse',
                                      formatters={f'{y_cols[i]}': 'numeral'}))
        # create span for average level
        if span_col:
            _span(df, span_col, p)
        p.title.text_font_size = "12pt"
        p.xaxis.major_label_text_font_size = "10pt"
        p.xaxis.major_label_orientation = 1
        p.yaxis.major_label_text_font_size = "11pt"
        p.yaxis[0].formatter.use_scientific = False
        p.yaxis[0].formatter = NumeralTickFormatter(format='0.00')
        p.y_range.start = 0
        p.x_range.range_padding = 0.05
        p.y_range.range_padding = 0.1
        grid_children.append(p)

    grid = gridplot(children=[grid_children[i:i + 1] for i in range(0, len(grid_children), 1)],
                    sizing_mode="stretch_width")
    st.bokeh_chart(grid)


def _span(df, col_name, p):
    level = df[col_name].values[0]
    average_span = Span(location=level,
                        dimension='width', line_color='black',
                        line_dash='dashed', line_width=2)
    p.add_layout(average_span)


def plot():
    _max_width_()
    meter_meta = read_data_from_file_as_pdf(METER_INFO_DATAFILE)
    address = meter_meta['ADDRESS'][0]
    meter_number = meter_meta['METER_NUMBER'][0]
    esiid = meter_meta['ESIID'][0]
    current_cycle_usage = read_data_from_file_as_pdf(CURRENT_USAGE_DATAFILE)['CURRENT_CYCLE_USAGE'][0]
    past_24_hours = read_data_from_file_as_pdf(PAST_24_HOUR_TREND_DATAFILE)
    past_45_days = read_data_from_file_as_pdf(DAILY_TRENDS_DATAFILE)
    past_12_months = read_data_from_file_as_pdf(MONTHLY_TRENDS_DATAFILE)
    past_day_interval = read_data_from_file_as_pdf(INTERVAL_TRENDS_DATAFILE)
    meter_last_read = read_data_from_file_as_pdf(LATEST_METER_READING_DATAFILE)
    latest_reading_time = meter_last_read['CURRENT_READING_TIME'][0]
    latest_reading_time = datetime.strptime(latest_reading_time, "%Y-%m-%d %H:%M:%S")
    last_billed = read_data_from_file_as_pdf(LAST_BILLED_METER_READING_DATAFILE)
    last_billed_date = last_billed['LAST_BILLED_DATE'][0]
    last_billed_units = last_billed['LAST_BILLED_READING'][0]

    # static info
    st.title("Real-Time Electricity Usage Dashboard")
    st.write("**Address : **{}".format(address))
    st.write("**Meter ID : **{}".format(meter_number), "&nbsp" * 30, "**ESIID : **{}".format(esiid))
    st.write("**Previous Billed Reading : **", last_billed_units, "&nbsp" * 9, "**Previous Billed Date : **",
             last_billed_date)
    st.write("**Latest Meter Units : **", meter_last_read['CURRENT_READING'][0], "&nbsp" * 11,
             "**Latest Reading Time : **",
             latest_reading_time.strftime("%A, %B %e, %Y - %I:%M %p"))
    st.write("# Current Cycle Usage : ", round(current_cycle_usage, 2))

    # plots
    past_24_hours['PREV_METER_READING'] = past_24_hours['METER_READING'].shift(1)
    past_24_hours['USAGE'] = past_24_hours['METER_READING'] - past_24_hours['PREV_METER_READING']
    past_24_hours = past_24_hours.drop(columns=['PREV_METER_READING', 'METER_READING'])
    past_24_hours['AVERAGE_USAGE'] = past_24_hours['USAGE'].mean()
    past_24_hours['USAGE_DATE'] = pd.to_datetime(past_24_hours['READING_TIME']).dt.date.astype('str')
    past_24_hours['USAGE_TIME'] = pd.to_datetime(past_24_hours['READING_TIME']).dt.time.astype('str')
    unq_day_past_24_hours = ','.join(past_24_hours['USAGE_DATE'].unique().tolist())
    st.subheader(f"**Consumption Trends: Past 24 Hours ({unq_day_past_24_hours})**")
    grid_plot(list_df=[past_24_hours],
              x_col='USAGE_TIME',
              y_cols=['USAGE'],
              xaxis_label='Date Time',
              yaxis_label='Usage (in kWh)',
              span_col='AVERAGE_USAGE',
              scatter=True,
              tick_interval=False)

    past_day_interval['AVERAGE_USAGE'] = past_day_interval['USAGE'].mean()
    past_day_interval['USAGE_DATE'] = pd.to_datetime(past_day_interval['USAGE_TIME']).dt.date.astype('str')
    past_day_interval['USAGE_TIME'] = pd.to_datetime(past_day_interval['USAGE_TIME']).dt.time.astype('str')
    unq_past_day_interval = ','.join(past_day_interval['USAGE_DATE'].unique().tolist())
    st.subheader(f"**Consumption Trends: 15 minute Intervals ({unq_past_day_interval})**")
    grid_plot(list_df=[past_day_interval],
              x_col='USAGE_TIME',
              y_cols=['USAGE'],
              xaxis_label='Date Time',
              yaxis_label='Usage (in kWh)',
              span_col='AVERAGE_USAGE',
              scatter=False,
              tick_interval=False)

    st.subheader("**Consumption Trends: Past 45 Days**")
    past_45_days['AVERAGE_USAGE'] = past_45_days['USAGE'].mean()
    grid_plot(list_df=[past_45_days],
              x_col='DAILY_DATE',
              y_cols=['USAGE'],
              xaxis_label='Date',
              yaxis_label='Usage (in kWh)',
              span_col='AVERAGE_USAGE',
              scatter=False,
              tick_interval=False)

    st.subheader("**Consumption Trends: Past 12 Months**")
    past_12_months['MONTH_YEAR'] = pd.to_datetime(past_12_months['MONTHLY_DATE']).dt.to_period('M').astype('str')
    past_12_months_grp = past_12_months.groupby('MONTH_YEAR').USAGE.sum().reset_index()
    past_12_months_grp['AVERAGE_USAGE'] = past_12_months_grp['USAGE'].mean()
    grid_plot(list_df=[past_12_months_grp],
              x_col='MONTH_YEAR',
              y_cols=['USAGE'],
              xaxis_label='Month Year',
              yaxis_label='Usage (in kWh)',
              span_col='AVERAGE_USAGE',
              scatter=True,
              tick_interval=False)


if BLOB_ENABLED:
    download_all_files_from_blob()

plot()

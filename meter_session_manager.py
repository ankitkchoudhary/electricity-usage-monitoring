import configparser
import datetime
import json
import time

from dateutil.relativedelta import relativedelta
from pytz import timezone
from requests import sessions

api_config = configparser.ConfigParser()
api_config.read("api_endpoints.ini")


class MeterSessionManager:
    def __init__(self, username, password):
        self.meter_session = sessions.session()
        self.meter_session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14_6) AppleWebKit/537.36 (KHTML,'
                          ' like Gecko) Chrome/77.0.3865.90 Safari/537.36',
            'Accept-Encoding': 'gzip, deflate',
            'Accept': 'application/json, text/plain, */*',
            'Connection': 'keep-alive',
            'Origin': api_config['API_ENDPOINTS']['PORTAL_BASE'],
            'Sec-Fetch-Mode': 'cors',
            'Content-Type': 'application/json;charset=UTF-8'
        })
        self.username = username
        self.password = password
        self.meter_session_cookies = None
        self.meter_auth_token = None
        self.meter_details = None
        self.set_cookies()
        print("Created Meter Session Manager Object")

    def call_meter_api(self, url, method="GET", payload=None, total_tries=3, retry_delay=30, pass_auth_header=True,
                       parse_response=True):
        print("Calling URL : [{}]".format(url))
        data = json.dumps(payload) if payload else None
        for try_num in range(1, total_tries + 1):
            try:
                if method == "GET":
                    response = self.meter_session.get(url=url, data=json.dumps(payload))
                else:
                    if pass_auth_header:
                        auth_header = {"Authorization": "Bearer {}".format(self.meter_auth_token)}
                        self.meter_session.headers.update(auth_header)
                        response = self.meter_session.post(url=url, data=data)
                    else:
                        response = self.meter_session.post(url=url, data=data)
                if 200 <= int(response.status_code) < 300:
                    if parse_response:
                        return response.json()
                    else:
                        return response
                else:
                    raise RuntimeError(response.content)
            except Exception as e:
                time.sleep(retry_delay)
                if try_num == total_tries:
                    print("Max Retries Reached while making the request.")
                    raise OverflowError("Max Tries Exhausted")

    def set_cookies(self):
        print("Setting the Session Cookies")
        self.meter_session.get(url=api_config['API_ENDPOINTS']['PORTAL_BASE'])
        self.meter_session_cookies = self.meter_session.cookies

    def set_auth_keys(self):
        print("Fetching Authorization Token")
        req_payload = {
            "username": self.username,
            "password": self.password,
            "rememberMe": "true"
        }
        api_url = api_config['API_ENDPOINTS']['API_BASE'] + api_config['API_ENDPOINTS']['AUTHENTICATE_API']
        auth_response = self.call_meter_api(url=api_url, payload=req_payload, method="POST", pass_auth_header=False)
        self.meter_auth_token = auth_response.get('token')

    def get_dashboard(self):
        print("Fetching Dashboard MetaData")
        dashboard_url = api_config['API_ENDPOINTS']['API_BASE'] + api_config['API_ENDPOINTS']['DASHBOARD_API']
        dashboard_meta = self.call_meter_api(url=dashboard_url, method="POST")
        dashboard_meta = dashboard_meta['data']
        self.meter_details = dashboard_meta['defaultMeterDetails']
        assert self.meter_details['esiid']
        print("Meter Details Fetched : {}".format(self.meter_details))
        return dashboard_meta

    def get_monthly_usage_trends(self, num_months=12, return_raw=False):
        print("Fetching Monthly Trends for Last [{}] months".format(num_months))
        monthly_usage_url = api_config['API_ENDPOINTS']['API_BASE'] + api_config['API_ENDPOINTS'][
            'MONTHLY_METER_READ_API']
        end_date = datetime.datetime.today()
        start_date = end_date - relativedelta(months=num_months)
        start_date = start_date.replace(day=1)
        payload = {"esiid": str(self.meter_details['esiid']),
                   "startDate": start_date.strftime("%m/%d/%Y"),
                   "endDate": end_date.strftime("%m/%d/%Y")}
        monthly_usage_response = self.call_meter_api(url=monthly_usage_url, method="POST", payload=payload).get(
            "monthlyData")
        if return_raw:
            return monthly_usage_response
        monthly_usage = list()
        for usage_month in monthly_usage_response:
            read_start_date = datetime.datetime.strptime(usage_month["startdate"], "%m/%d/%Y")
            read_end_date = datetime.datetime.strptime(usage_month["enddate"], "%m/%d/%Y")
            kwh_usage = usage_month["actl_kwh_usg"]
            read_date = read_start_date + (read_end_date - read_start_date) / 2
            monthly_usage.append({"MONTHLY_DATE": read_date.date().replace(day=1), "USAGE": kwh_usage})
        return monthly_usage

    def get_daily_usage_trends(self, num_days=30, specific_date=None, return_raw=False):
        print("Fetching Daily Trends for Last [{}] days".format(num_days))
        daily_usage_url = api_config['API_ENDPOINTS']['API_BASE'] + api_config['API_ENDPOINTS']['DAILY_METER_READ_API']
        if specific_date:
            start_date = end_date = specific_date
        else:
            end_date = datetime.datetime.today() - relativedelta(days=1)
            start_date = end_date - relativedelta(days=num_days)
        payload = {"esiid": str(self.meter_details['esiid']),
                   "startDate": start_date.strftime("%m/%d/%Y"),
                   "endDate": end_date.strftime("%m/%d/%Y")}
        daily_usage_response = self.call_meter_api(url=daily_usage_url, method="POST", payload=payload).get("dailyData")
        if return_raw:
            return daily_usage_response
        daily_usage = list()
        for usage_day in daily_usage_response:
            read_date = datetime.datetime.strptime(usage_day["date"], "%m/%d/%Y")
            kwh_usage = usage_day["reading"]
            daily_usage.append({"DAILY_DATE": read_date.date(), "USAGE": kwh_usage})
        return daily_usage

    def get_on_demand_read(self):
        print("Invoking On Demand Meter Reading")
        invoke = False
        l_odr = self.get_last_reading()
        if not l_odr.get("odrstatus"):
            print("No Recent On-Demand Meter Reads. Ready to Trigger one now.")
            invoke = True
        else:
            l_odr_time = l_odr.get("odrdate")
            print("Last On Demand Read Triggered at: [{}]".format(l_odr_time))
            print("Last On Demand Read Status: [{}]".format(l_odr.get("odrstatus")))
            l_odr_time = l_odr_time if l_odr_time else "01/01/1970 00:00:00"
            l_odr_time = datetime.datetime.strptime(l_odr_time, "%m/%d/%Y %H:%M:%S")
            l_odr_time = timezone("US/Central").localize(l_odr_time)
            current_time = datetime.datetime.now(tz=timezone("US/Central"))
            time_diff = (current_time - l_odr_time).seconds
            # ODR API Limit: 2 - Per hour, 24 - Per Day
            print("Last ODR Call was made [{}] seconds earlier".format(time_diff))
            if time_diff > 3600:
                print("Last On Demand Read was before 60 minutes. Ready to Trigger one now.")
                invoke = True
        if invoke:
            on_demand_read_url = api_config['API_ENDPOINTS']['API_BASE'] + api_config['API_ENDPOINTS'][
                'ON_DEMAND_METER_READ_API']
            payload = {"ESIID": str(self.meter_details['esiid']), "MeterNumber": str(self.meter_details['meterNumber'])}
            on_demand_read_response = self.call_meter_api(url=on_demand_read_url, method="POST", payload=payload).get(
                "data")
            print("Response: [{}]".format(on_demand_read_response))
            if on_demand_read_response.get("statusCode") != '0':
                print("Failed to Submit On Demand Meter Read Request")
                pass
        else:
            print("Latest Meter Read was less than 60 minutes before. Not calling now.")
            pass
        for i in range(10):
            l_odr = self.get_last_reading()
            if l_odr.get("odrstatus") == "COMPLETED":
                odr_date = datetime.datetime.strptime(l_odr["odrdate"], "%m/%d/%Y %H:%M:%S")
                odr_reading = float(l_odr["odrread"])
                usage_since_last_read = {"USAGE_SINCE_LAST_OD_READ": int(float(l_odr["odrusage"]))}
                return usage_since_last_read, {"CURRENT_READING_TIME": odr_date, "CURRENT_READING": odr_reading}
            time.sleep(30)
        return 0, 0

    def get_last_reading(self):
        print("Check Last Reading Status")
        last_reading_url = api_config['API_ENDPOINTS']['API_BASE'] + api_config['API_ENDPOINTS']['LAST_METER_READ_API']
        payload = {"ESIID": str(self.meter_details['esiid'])}
        last_reading_response = self.call_meter_api(url=last_reading_url, method="POST", payload=payload).get("data")
        return last_reading_response

    def get_latest_billed_reading(self):
        print("Fetching Latest Billed Reading")
        monthly_usage_response = self.get_monthly_usage_trends(num_months=1, return_raw=True)
        end_date_list = [datetime.datetime.strptime(x["enddate"], "%m/%d/%Y") for x in monthly_usage_response]
        last_billed_date = max(end_date_list)
        billed_date_reading = self.get_daily_usage_trends(specific_date=last_billed_date, return_raw=True)
        last_billed_reading = int(float(billed_date_reading[0].get("startreading")))
        return {"LAST_BILLED_DATE": last_billed_date, "LAST_BILLED_READING": last_billed_reading} \
            if last_billed_reading and last_billed_date else None

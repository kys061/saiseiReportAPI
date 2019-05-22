#!/usr/bin/python2.7
# -*- coding: utf-8 -*-
# writer : yskang (kys061@gmail.com)

from flask import Flask, Response, request, json, jsonify, url_for, make_response
import os
import sys
import copy
from saisei.saisei_api import saisei_api
from logging.handlers import RotatingFileHandler
from logging.handlers import SysLogHandler
from logging import StreamHandler
import logging
from traceback import format_exc
from datetime import datetime, date, timedelta

from pprint import pprint
import time
from socket import socket, AF_INET, gethostname
import json
import report_json

LOG_SYSLOG_FACILITY = logging.handlers.SysLogHandler.LOG_LOCAL6

REST_SERVER = 'localhost'
REST_PORT = 5000
REST_USER = 'cli_admin'
REST_PASSWORD = 'cli_admin'

REST_BASIC_PATH ='configurations/running/'
REST_FLOW_PATH = 'flows/'
REST_INT_PATH = 'interfaces/'
FLOW_CSV_FILENAME = '{}{}{}_{}_{}_flows.log' # year, mon, day, {with}, ip
RECORDER_LOG_FILENAME = r'/var/log/flow_recorder8.0.log'
FLOW_PATH = '/var/log/flows/'
TOKEN = '1'
ORDER = '<average_rate'
START = '0'
LIMIT = '100000'
WITH = 'with='  # with=dest_host=ipaddress
WITH_ATTR = [
'dest_host',
'source_host',
]
OUTPUT_FILENAME = '/var/log/report_api.log'

logger_recorder = None
# Set to True to enable any logger.debug
ENABLE_DEBUG_LOGGING = False

TARGET_DIR = os.path.dirname(os.path.realpath(__file__))
FILES_DIR = TARGET_DIR + "/files"


app = Flask(__name__)

# FIELD_NAMES = copy.deepcopy(FLOW_ATTR)
# FIELD_NAMES.insert(0, "timestamp")


def make_logger():
    global logger_recorder
    logger_recorder = logging.getLogger('report_api')
    #  ==== MUST be True for hg commit ====
    if True:
        fh = RotatingFileHandler(RECORDER_LOG_FILENAME, 'a', 50 * 1024 * 1024, 4)
        logger_recorder.setLevel(logging.INFO)
    else:
        fh = StreamHandler(sys.stdout)
        logger_recorder.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    fh.setFormatter(formatter)
    logger_recorder.addHandler(fh)
    logger_recorder.info("***** logger_recorder starting %s *****" % (sys.argv[0]))


logger = logging.getLogger(__name__)
file_handler = SysLogHandler(address='/dev/log', facility=LOG_SYSLOG_FACILITY)
file_handler.setFormatter(logging.Formatter('%(levelname)s: %(message)s [in PID %(process)d at %(pathname)s:%(lineno)d]'))
logger.addHandler(file_handler)
logger.setLevel(logging.DEBUG if ENABLE_DEBUG_LOGGING else logging.INFO)


def getInterfaceRcvData():
# http://192.168.10.25:5000/rest/stm/configurations/running/interfaces/external1?select=receive_rate&from=11:56:00_20190401&operation=raw&history_points=true&until=11:56:00_20190402
    api = saisei_api(server=REST_SERVER, port=REST_PORT, user=REST_USER, password=REST_PASSWORD)

    url = "{}{}external1?select=receive_rate&from=11:56:00_20190401&operation=raw&history_points=true&until=11:56:00_20190402".format(
            REST_BASIC_PATH, REST_INT_PATH)
    collections = api.rest.get(url)['collection']
    return collections

api = saisei_api(server=REST_SERVER, port=REST_PORT, user=REST_USER, password=REST_PASSWORD)


def make_url(_select, _operation, _history_points, _from, _until):
    return "{}{}external1?select={}&from={}&operation={}&history_points={}&until={}".format(
            REST_BASIC_PATH, REST_INT_PATH, _select, _from, _operation, _history_points, _until)


'''
1. from과 until 사이의 데이터에서 해당 날짜에 대한 데이터만 구분하여 배열[시간, 트래픽속도]을 만든다.
2. 만든 배열의 총합과 개수로 나눠 평균 트래픽 양을 구한다. 
3. 해당 배열에서 최대 트래픽 속도를 검색한다.
'''

@app.route('/interfaces', methods=['GET'])
def get_interfaces_data():
    _select = [
        'receive_rate',
        'transmit_rate'
    ]
    _select = ','.join(_select)
    _operation = 'raw'
    _history_points = 'true'
    ## check from and until is right using regex
    if request.args['from'] == '' or request.args['until']=='':
        return jsonify({'message': "parameter doesn't exist:\n %s" % (format_exc(), ),
                      'status': 500})
    else:
        _from = request.args['from']
        _until = request.args['until']

    url = make_url(_select, _operation, _history_points, _from, _until)

    print(url)
    collections = api.rest.get(url)['collection']

    # pprint(collections)
    _history_receive_rate = collections[0]['_history_receive_rate']
    _history_transmit_rate = collections[0]['_history_transmit_rate']
    # _from = collections[0]['from']
    _from = datetime.strptime(collections[0]['from'], "%Y-%m-%dT%H:%M:%S")
    _until = datetime.strptime(collections[0]['until'], "%Y-%m-%dT%H:%M:%S")
    durations = _until.date() - _from.date()

    cmp_date = []
    cmp_date.append(_from.strftime("%Y-%m-%d"))
    for i in range(durations.days):
        cmp_date.append((_from + timedelta(days=i+1)).strftime("%Y-%m-%d"))

    print (_from.date())
    print (_until.date())
    print (cmp_date)
    # print (duration.days)
    # _until = collections[0]['until']
    rcv_rate = []
    rcv_time = []
    trs_rate = []
    trs_time = []
    for i, rcv in enumerate(_history_receive_rate):
        if (0 == i%20):
            rcv_time.append(datetime.fromtimestamp(rcv[0] * 0.001).strftime("%Y. %m. %d. %p %I:%M:%S")
                            .replace('PM', '오후').replace('AM', '오전'))
            rcv_rate.append(round(rcv[1]*0.001, 3))
            # print(datetime.fromtimestamp(rcv[0]*0.001))
            # print(round(rcv[1]*0.001, 3))

    for i, trs in enumerate(_history_transmit_rate):
        if (0 == i%20):
            trs_time.append(datetime.fromtimestamp(trs[0] * 0.001).strftime("%Y. %m. %d. %p %I:%M:%S")
                            .replace('PM', '오후').replace('AM', '오전'))
            trs_rate.append(round(trs[1]*0.001, 3))
            # print(datetime.fromtimestamp(trs[0]*0.001))
            # print(round(trs[1]*0.001, 3))

    rcv_avg = []
    rcv_tot = 0
    rcv_len = 0
    for j in range(durations.days+1):
        for i, rcv in enumerate(_history_receive_rate):
            if cmp_date[j] == datetime.fromtimestamp(rcv[0] * 0.001).strftime("%Y-%m-%d"):
                rcv_tot += rcv[1] * 0.001;
                rcv_len += 1;
        print (rcv_tot, rcv_len)
        rcv_avg.append(rcv_tot/rcv_len)
        rcv_tot = 0
        rcv_len = 0

    print(rcv_avg)

    return_data = {
        'graph_data': [
            [rcv_time, rcv_rate],
            [trs_time, trs_rate]
        ],
    }

    # int_rcv_data = getInterfaceRcvData()
    # logger(api.rest.get(url)['collection'])
    # logger_recorder(api.rest.get(url)['collection'])
    # time.sleep(10)

    return jsonify(return_data)
    # return jsonify({'test': 'hello-world'})

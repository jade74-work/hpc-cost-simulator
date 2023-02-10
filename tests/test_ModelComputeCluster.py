'''
Test the ModelComputeCluster.py module and script.

Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
SPDX-License-Identifier: MIT-0
'''

from copy import deepcopy
from random import gammavariate
from CSVLogParser import CSVLogParser, logger as CSVLogParser_logger
from datetime import datetime, timedelta, timezone
import filecmp
from ModelComputeCluster import ComputeClusterModel, logger as ModelComputeCluster_logger
import json
import logging
from MemoryUtils import MEM_GB, MEM_KB, MEM_MB
import os
from os import environ, getenv, listdir, makedirs, path, system
from os.path import abspath, dirname
import pytest
from random import expovariate, gammavariate, randint, randrange
from SchedulerJobInfo import logger as SchedulerJobInfo_logger, SchedulerJobInfo
from SchedulerLogParser import logger as SchedulerLogParser_logger
import subprocess
from subprocess import CalledProcessError, check_output
from test_JobAnalyzer import order as last_order
import unittest
from VersionCheck import logger as VersionCheck_logger

order = last_order // 100 * 100 + 100
assert order == 700

SECONDS_PER_MINUTE = 60
MINUTES_PER_HOUR = 60
SECONDS_PER_HOUR = SECONDS_PER_MINUTE * MINUTES_PER_HOUR

logger = logging.getLogger(__file__)
logger_formatter = logging.Formatter('%(levelname)s:%(asctime)s: %(message)s')
logger_streamHandler = logging.StreamHandler()
logger_streamHandler.setFormatter(logger_formatter)
logger.addHandler(logger_streamHandler)
logger.propagate = False
logger.setLevel(logging.INFO)

class TestModelComputeCluster(unittest.TestCase):
    global order

    def __init__(self, name):
        super().__init__(name)
        self._restore_instance_type_info()

    REPO_DIR = abspath(f"{dirname(__file__)}/..")

    TEST_FILES_BASE_DIR = path.join(REPO_DIR, 'test_files', 'ModelComputeCluster')

    CONFIG_FILENAME = path.join(TEST_FILES_BASE_DIR, 'config.yml')

    INPUT_CSV = path.join(TEST_FILES_BASE_DIR, 'jobs_random_10.csv')

    OUTPUT_DIR = path.join(REPO_DIR, 'output/ComputeClusterModel')

    _compute_cluster_model = None

    def get_compute_cluster_model(self):
        if self._compute_cluster_model:
            return self._compute_cluster_model
        self._use_static_instance_type_info()
        csv_parser = CSVLogParser(TestModelComputeCluster.INPUT_CSV, None)
        self._compute_cluster_model = ComputeClusterModel(csv_parser, TestModelComputeCluster.CONFIG_FILENAME, TestModelComputeCluster.OUTPUT_DIR, None, None, None, None)
        return self._compute_cluster_model

    def _use_static_instance_type_info(self):
        system(f"cp {self.REPO_DIR}/test_files/instance_type_info.json {self.REPO_DIR}/instance_type_info.json")

    def _restore_instance_type_info(self):
        system(f"git restore {dirname(__file__)+'/../instance_type_info.json'}")

    def cleanup_output_files(self):
        system(f"rm -rf {dirname(__file__)+'/../output'}")

    def _create_jobs_csv(self, filename: str, starttime: str, endtime: str, number_of_jobs: int, min_num_cores: int=1, max_num_cores: int=64) -> None:
        '''
        _create_jobs_csv

        Jobs will be created that:
            * start before starttime and finish before starttime
            * start before starttime and finish at starttime
            * start before starttime and end between starttime and endtime
            * start before starttime and end at endtime
            * start before starttime and end after endtime
            * start at starttime and end between starttime and endtime
            * start at starttime and end at endtime
            * start at starttime and end after endtime
            * start between starttime and endtime and end between starttime and endtime
            * start between starttime and endtime and end at endtime
            * start between starttime and endtime and end after endtime
            * start at endtime and end after endtime

        Args:
            filename (str):  Jobs CSV file that will be created
            starttime (str): Starting time for analysis.
            endtime (str):   Ending time for analysis.
            number_of_jobs (int): Number of jobs to create between that include starttime and endtime
            min_num_cores (int): Minimum number of cores per job. Default=1
            max_num_cores (int): Maximum number of cores per job. Default=64
        Returns:
            None
        '''
        EARLY_SPECIAL_CASE_JOBS = 6
        EARLY_SPECIAL_CASE_JOBS_IN_TIME_WINDOW = 5
        EARLY_SPECIAL_CASE_JOBS_NOT_IN_TIME_WINDOW = EARLY_SPECIAL_CASE_JOBS - EARLY_SPECIAL_CASE_JOBS_IN_TIME_WINDOW
        LATE_SPECIAL_CASE_JOBS = 5
        LATE_SPECIAL_CASE_JOBS_IN_TIME_WINDOW = 4
        LATE_SPECIAL_CASE_JOBS_NOT_IN_TIME_WINDOW = LATE_SPECIAL_CASE_JOBS - LATE_SPECIAL_CASE_JOBS_IN_TIME_WINDOW

        csv_parser = CSVLogParser('/dev/null', filename, starttime, endtime)
        starttime_dt = csv_parser._starttime_dt
        endtime_dt = csv_parser._endtime_dt

        first_hour = int(starttime_dt.timestamp()) // SECONDS_PER_HOUR
        last_hour = int(endtime_dt.timestamp()) // SECONDS_PER_HOUR

        early_submit_time = datetime.fromtimestamp(randrange((first_hour - 1) * SECONDS_PER_HOUR, starttime_dt.timestamp() - 2)).replace(tzinfo=timezone.utc)
        between_submit_time = datetime.fromtimestamp(randrange(starttime_dt.timestamp() + 1, endtime_dt.timestamp() - 2)).replace(tzinfo=timezone.utc)
        late_submit_time_timestamp = randrange((last_hour + 1) * SECONDS_PER_HOUR, (last_hour + 2) * SECONDS_PER_HOUR) - 2
        late_submit_time = datetime.fromtimestamp(randrange((last_hour + 1) * SECONDS_PER_HOUR, (last_hour + 2) * SECONDS_PER_HOUR) - 2).replace(tzinfo=timezone.utc)

        early_finish_time = datetime.fromtimestamp(randrange(early_submit_time.timestamp(), starttime_dt.timestamp() - 1)).replace(tzinfo=timezone.utc)
        between_finish_time = datetime.fromtimestamp(randrange(between_submit_time.timestamp() + 1, endtime_dt.timestamp() - 1)).replace(tzinfo=timezone.utc)
        late_finish_time = datetime.fromtimestamp(randrange(late_submit_time.timestamp(), (last_hour + 2) * SECONDS_PER_HOUR) - 1).replace(tzinfo=timezone.utc)

        logger.info(f"""
            early_submit_time:   {early_submit_time}
            early_finish_time:   {early_finish_time}
            starttime:           {starttime_dt}
            between_submit_time: {between_submit_time}
            between_finish_time: {between_finish_time}
            endtime:             {endtime_dt}
            late_submit_time:    {late_submit_time}
            late_finish_time:    {late_finish_time}
            """)

        job_id = 0
        number_of_jobs_in_time_window = 0
        for submit_time in [early_submit_time, starttime_dt, between_submit_time]:
            for finish_time in [early_finish_time, starttime_dt, between_finish_time]:
                if finish_time < submit_time:
                    continue
                job_id += 1
                number_of_cores = min(int(max(min_num_cores, expovariate(1/4))), max_num_cores)
                max_mem_gb = round(gammavariate(2, 2) * 1.5, 0)
                job = SchedulerJobInfo(job_id, number_of_cores, max_mem_gb, 1, SchedulerJobInfo.datetime_to_str(submit_time), SchedulerJobInfo.datetime_to_str(submit_time), SchedulerJobInfo.datetime_to_str(finish_time))
                csv_parser.write_job_to_csv(job)
                if csv_parser._job_in_time_window(job):
                    number_of_jobs_in_time_window += 1
        assert job_id == EARLY_SPECIAL_CASE_JOBS
        assert number_of_jobs_in_time_window == EARLY_SPECIAL_CASE_JOBS_IN_TIME_WINDOW
        logger.info(f"{job_id} early jobs")
        for job_index in range(number_of_jobs - EARLY_SPECIAL_CASE_JOBS_IN_TIME_WINDOW - LATE_SPECIAL_CASE_JOBS_IN_TIME_WINDOW):
            job_id += 1
            submit_time = submit_time + timedelta(seconds=gammavariate(2,2))
            start_time = submit_time
            finish_time = start_time + timedelta(seconds=gammavariate(2, 2) * 60)
            number_of_cores = min(int(max(min_num_cores, expovariate(1/4))), max_num_cores)
            max_mem_gb = round(gammavariate(2, 2) * 1.5, 0)
            job = SchedulerJobInfo(job_index, number_of_cores, max_mem_gb, 1, SchedulerJobInfo.datetime_to_str(submit_time), SchedulerJobInfo.datetime_to_str(start_time), SchedulerJobInfo.datetime_to_str(finish_time))
            csv_parser.write_job_to_csv(job)
            if csv_parser._job_in_time_window(job):
                number_of_jobs_in_time_window += 1
        logger.info(f"{job_id} jobs")
        assert job_id == (EARLY_SPECIAL_CASE_JOBS - EARLY_SPECIAL_CASE_JOBS_IN_TIME_WINDOW + number_of_jobs - LATE_SPECIAL_CASE_JOBS_IN_TIME_WINDOW)
        for submit_time in [submit_time, endtime_dt, late_submit_time]:
            for finish_time in [endtime_dt, late_finish_time]:
                if finish_time < submit_time:
                    continue
                job_id += 1
                number_of_cores = min(int(max(min_num_cores, expovariate(1/4))), max_num_cores)
                max_mem_gb = round(gammavariate(2, 2) * 1.5, 0)
                job = SchedulerJobInfo(job_id, number_of_cores, max_mem_gb, 1, SchedulerJobInfo.datetime_to_str(submit_time), SchedulerJobInfo.datetime_to_str(submit_time), SchedulerJobInfo.datetime_to_str(finish_time))
                csv_parser.write_job_to_csv(job)
                if csv_parser._job_in_time_window(job):
                    number_of_jobs_in_time_window += 1
        logger.info(f"{job_id} jobs")
        assert number_of_jobs_in_time_window == number_of_jobs
        assert job_id == (EARLY_SPECIAL_CASE_JOBS_NOT_IN_TIME_WINDOW + number_of_jobs + LATE_SPECIAL_CASE_JOBS_NOT_IN_TIME_WINDOW)

    def _get_hourly_files(self, dir):
        '''
        Gets the hourly output files for the current job

        Args:
            dir (str): output directory
        Returns:
            [str]: Sorted list of output filenames
        '''
        all_files = listdir(dir)
        output_files = []
        prefix = path.basename("hourly-")
        for file in all_files:
            if file.startswith(prefix) and file[-4:] == ".csv":
                output_file = file
                output_files.append(output_file)
        output_files.sort()
        return output_files

    order += 1
    @pytest.mark.order(order)
    def test_find_best_instance_families(self):
        self._use_static_instance_type_info()
        self.cleanup_output_files()

        try:
            #ModelComputeCluster_logger.setLevel(logging.DEBUG)
            compute_cluster_model = self.get_compute_cluster_model()
            print(json.dumps(compute_cluster_model._instance_families, indent=4))
            print(json.dumps(compute_cluster_model._best_instance_family, indent=4))
            exp_best_instance_families = {
                'OnDemand': {
                    4: 'c6a',
                    8: "m6a",
                    16: "r5",
                    32: "x2idn",
                    64: "x2iezn"
                },
                "spot": {
                    4: "c5d",
                    8: "m6id",
                    16: "r5",
                    32: "x2idn",
                    64: "x2iezn"
                }
            }
            self.assertDictEqual(compute_cluster_model._best_instance_family, exp_best_instance_families)
        except:
            raise
        finally:
            self._restore_instance_type_info()

    order += 1
    @pytest.mark.order(order)
    def test_10_random_jobs(self):
        try:
            self._use_static_instance_type_info()
            self.cleanup_output_files()

            input_csv = path.join(TestModelComputeCluster.TEST_FILES_BASE_DIR, 'jobs_random_10.csv')
            csv_parser = CSVLogParser(input_csv, None)
            compute_cluster_model = ComputeClusterModel(csv_parser, TestModelComputeCluster.CONFIG_FILENAME, TestModelComputeCluster.OUTPUT_DIR, None, None, None, None)
            compute_cluster_model.model_jobs()
        finally:
            self._restore_instance_type_info()

    order += 1
    @pytest.mark.order(order)
    def test_100_random_jobs(self):
        self._use_static_instance_type_info()
        self.cleanup_output_files()

        try:
            input_csv = path.join(TestModelComputeCluster.TEST_FILES_BASE_DIR, 'jobs_random_100.csv')
            csv_parser = CSVLogParser(input_csv, None)
            compute_cluster_model = ComputeClusterModel(csv_parser, TestModelComputeCluster.CONFIG_FILENAME, TestModelComputeCluster.OUTPUT_DIR, None, None, None, None)
            compute_cluster_model.model_jobs()
        finally:
            self._restore_instance_type_info()

    order += 1
    @pytest.mark.order(order)
    def test_starttime_endtime(self):
        try:
            self._use_static_instance_type_info()
            self.cleanup_output_files()

            number_of_jobs = 1000
            # Cover DST switch in spring
            starttime = '2022-03-12T00:00:00'
            endtime = '2022-03-13T23:00:00'

            input_csv = path.join(TestModelComputeCluster.OUTPUT_DIR, 'jobs.csv')
            makedirs(TestModelComputeCluster.OUTPUT_DIR)
            self._create_jobs_csv(filename=input_csv, starttime=starttime, endtime=endtime, number_of_jobs=number_of_jobs)
            csv_parser = CSVLogParser(input_csv, None, starttime, endtime)
            compute_cluster_model = ComputeClusterModel(csv_parser, TestModelComputeCluster.CONFIG_FILENAME, TestModelComputeCluster.OUTPUT_DIR, starttime, endtime, None, None)

            #CSVLogParser_logger.setLevel(logging.DEBUG)
            #ModelComputeCluster_logger.setLevel(logging.DEBUG)
            #SchedulerJobInfo_logger.setLevel(logging.DEBUG)
            #SchedulerLogParser_logger.setLevel(logging.DEBUG)
            #VersionCheck_logger.setLevel(logging.DEBUG)

            compute_cluster_model.model_jobs()
            assert compute_cluster_model.total_jobs == number_of_jobs
            assert csv_parser.total_jobs_outside_time_window == 2
            assert compute_cluster_model.total_failed_jobs == 0
        finally:
            self._restore_instance_type_info()

    order += 1
    @pytest.mark.order(order)
    def test_no_spot_instances(self):
        try:
            self._use_static_instance_type_info()
            self.cleanup_output_files()

            config_file = path.join(TestModelComputeCluster.TEST_FILES_BASE_DIR, 'config_hpc_instances_only.yml')
            number_of_jobs = 100
            # Cover DST switch in spring
            starttime = '2022-03-12T00:00:00'
            endtime = '2022-03-13T23:00:00'

            input_csv = path.join(TestModelComputeCluster.OUTPUT_DIR, 'jobs.csv')
            makedirs(TestModelComputeCluster.OUTPUT_DIR)
            self._create_jobs_csv(filename=input_csv, starttime=starttime, endtime=endtime, number_of_jobs=number_of_jobs)
            csv_parser = CSVLogParser(input_csv, None, starttime, endtime)
            compute_cluster_model = ComputeClusterModel(csv_parser, config_file, TestModelComputeCluster.OUTPUT_DIR, starttime, endtime, None, None)

            #CSVLogParser_logger.setLevel(logging.DEBUG)
            #ModelComputeCluster_logger.setLevel(logging.DEBUG)
            #SchedulerJobInfo_logger.setLevel(logging.DEBUG)
            #SchedulerLogParser_logger.setLevel(logging.DEBUG)
            #VersionCheck_logger.setLevel(logging.DEBUG)

            compute_cluster_model.model_jobs()
            assert compute_cluster_model.total_jobs == number_of_jobs
            assert csv_parser.total_jobs_outside_time_window == 2
            assert compute_cluster_model.total_failed_jobs == 0
        finally:
            self._restore_instance_type_info()
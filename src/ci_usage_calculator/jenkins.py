#!/usr/bin/env python3

import datetime
import collections
import getpass
import argparse
import concurrent.futures
import os
from tabulate import tabulate

import jenkins
import backoff
from tqdm import tqdm
import requests.exceptions

from . import _stats

MAX_WORKERS=25
JENKINS_URL=None
USERNAME=None
PASSWORD=None

def _log_preparation_backoff(details):
	job_name = details['args'][0]
	wait = details['wait']
	tries = details['tries']
	tqdm.write(f'Error fetching job info for {job_name}-- backing off {wait:0.1f} seconds (try {tries})')

@backoff.on_exception(backoff.expo, jenkins.JenkinsException, max_tries=3, on_backoff=_log_preparation_backoff)
def _prepare_builds(job_fullname):
	build_infos = []

	job_info = _jenkins_server().get_job_info(job_fullname, fetch_all_builds=True)

	if 'builds' in job_info:
		build_infos = [_stats.BuildInfo(job_fullname, build['number']) for build in job_info['builds']]

	return build_infos

def _log_processing_backoff(details):
	build_info = details['args'][0]
	wait = details['wait']
	tries = details['tries']
	tqdm.write(f'Error fetching build {build_info.build_number} for {build_info.job_name}-- backing off {wait:0.1f} seconds (try {tries})')

@backoff.on_exception(backoff.expo, jenkins.JenkinsException, max_tries=3, on_backoff=_log_processing_backoff)
def _process_build(build_info):
	build_info = _jenkins_server().get_build_info(build_info.job_name, build_info.build_number)
	return _stats.BuildStats(datetime.datetime.fromtimestamp(build_info['timestamp']/1000.0), build_info['duration'] / 1000.0 / 60.0)

# Unclear if this is thread-safe, so just create new ones
def _jenkins_server():
	return jenkins.Jenkins(JENKINS_URL, username=USERNAME, password=PASSWORD, timeout=300)

def main():
	global JENKINS_URL
	global USERNAME
	global PASSWORD
	global MAX_WORKERS

	parser = argparse.ArgumentParser(
                    prog='calculate-jenkins-minutes',
                    description='Calculate CI minutes for an entire Jenkins instance')

	parser.add_argument('jenkins_url', metavar='jenkins-url')
	parser.add_argument('-u', '--username')
	parser.add_argument('-w', '--workers', default=MAX_WORKERS)
	parser.add_argument('-a', '--anonymous', action='store_true')

	args = parser.parse_args()
	MAX_WORKERS = args.workers
	JENKINS_URL = args.jenkins_url
	if not args.anonymous:
		USERNAME = args.username
		if USERNAME is None:
			USERNAME = input('Jenkins username: ')
		PASSWORD = os.environ.get('JENKINS_PASSWORD')
		if PASSWORD is None:
			PASSWORD = getpass.getpass('Jenkins password: ')

	server = _jenkins_server()

	build_infos = []
	stats = collections.defaultdict(lambda: collections.defaultdict(_stats.CIStats))

	try:
		jobs = server.get_all_jobs()

		with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
			futures = [executor.submit(_prepare_builds, job['fullname']) for job in jobs]
			try:
				for future in tqdm(concurrent.futures.as_completed(futures), total=len(futures), desc="Fetching jobs", dynamic_ncols=True, unit="job"):
					build_infos += future.result()

			except KeyboardInterrupt:
				tqdm.write("Exiting...")
				for future in futures:
					future.cancel()
				return

		with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
			futures = [executor.submit(_process_build, build_info) for build_info in build_infos]
			try:
				for future in tqdm(concurrent.futures.as_completed(futures), total=len(futures), desc="Fetching/processing builds", dynamic_ncols=True, unit="build"):
					build_stat = future.result()
					ci_stats = stats[build_stat.timestamp.year][build_stat.timestamp.month]
					ci_stats.total_builds += 1
					ci_stats.total_duration += build_stat.duration
			except KeyboardInterrupt:
				tqdm.write("Exiting...")
				for future in futures:
					future.cancel()
				return
	finally:
		_stats.print_stats(stats, unit="build")

#!/usr/bin/env python3

import csv
import datetime
import collections
from operator import attrgetter
import getpass
import argparse
import concurrent.futures
import os
import json
from tabulate import tabulate

import jenkins
import backoff
from tqdm import tqdm
import requests.exceptions

import xml.etree.ElementTree

_JobInfo = collections.namedtuple('_JobInfo', ['name', 'jenkins_url', 'scm_url', 'scm_branch', 'enabled'])

def _extract_scm_info(server, job_name):
	scm_urls = []
	scm_branches = []

	root = xml.etree.ElementTree.fromstring(server.get_job_config(job_name))
	for remote_config in root.iter('hudson.plugins.git.UserRemoteConfig'):
		scm_urls.append(remote_config.find('url').text)

	for branch_spec in root.iter('hudson.plugins.git.BranchSpec'):
		scm_branches.append(branch_spec.find('name').text)

	return (', '.join(scm_urls), ', '.join(scm_branches))

# Flatten all folders
def _extract_job_infos(server, jobs, *, show_progress=True):
	# Use a dict to ensure uniqueness (there is some duplication due to the folders)
	job_collection = dict()
	if show_progress:
		jobs = tqdm(jobs, total=len(jobs), desc=f'Processing jobs from {server.server}', dynamic_ncols=True, unit="job")
	for job in jobs:
		jenkins_url = job['url']
		if jenkins_url in job_collection:
			continue

		if 'color' in job:
			name = job['fullname']
			enabled = job['color'] != 'disabled'
			# if not enabled:
			# 	continue

			scm_url, scm_branch = _extract_scm_info(server, name)
			# if len(scm_url) == 0 or 'gitlab-be' in scm_url or 'rndser-repo' in scm_url:
			# 	continue

			job_collection[jenkins_url] = _JobInfo(name, jenkins_url, scm_url, scm_branch, enabled)
		if 'jobs' in job:
			job_collection.update(_extract_job_infos(server, job['jobs'], show_progress=False))

	return job_collection

def _write_job_infos_to_csv(job_infos, output_file):
	with open(output_file, 'w', newline='') as csvfile:
		writer = csv.DictWriter(csvfile, fieldnames=_JobInfo._fields)

		writer.writeheader()

		for job_info in sorted(job_infos.values(), key=attrgetter('name')):
			writer.writerow(job_info._asdict())

def main():
	parser = argparse.ArgumentParser(
                    prog='extract-active-jenkins-jobs',
                    description='Create CSV of active jobs in a given Jenkins instance')

	parser.add_argument('jenkins_urls', nargs='+', metavar='jenkins-url')
	parser.add_argument('-u', '--username')
	parser.add_argument('-a', '--anonymous', action='store_true')
	parser.add_argument('-o', '--output', required=True)

	args = parser.parse_args()
	jenkins_urls = args.jenkins_urls
	username = None
	password = None
	if not args.anonymous:
		username = args.username
		if username is None:
			username = input('Jenkins username: ')
		password = os.environ.get('JENKINS_PASSWORD')
		if password is None:
			password = getpass.getpass('Jenkins password: ')

	job_infos = dict()

	for jenkins_url in jenkins_urls:
		server = jenkins.Jenkins(jenkins_url, username=username, password=password, timeout=300)
		jobs = server.get_all_jobs()
		job_infos.update(_extract_job_infos(server, jobs))

	_write_job_infos_to_csv(job_infos, args.output)

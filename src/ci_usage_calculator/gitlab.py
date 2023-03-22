#!/usr/bin/env python3

import collections
import getpass
import argparse
import os
import urllib3

import gitlab
import dateutil.parser
from tqdm import tqdm

from . import _stats

def _get_stats(server, stats):
	projects = server.projects.list(as_list=False, retry_transient_errors=True)

	for project in tqdm(projects, desc="Processing projects", dynamic_ncols=True, unit="project"):
		if not project.jobs_enabled:
			continue

		for job in project.jobs.list(as_list=False, retry_transient_errors=True):
			created_at = dateutil.parser.isoparse(job.created_at)
			ci_stats = stats[created_at.year][created_at.month]
			ci_stats.total_builds += 1
			if job.duration is not None:
				ci_stats.total_duration += job.duration / 60

def main():
	parser = argparse.ArgumentParser(
                    prog='calculate-gitlab-minutes',
                    description='Calculate CI minutes for an entire Gitlab instance')

	parser.add_argument('gitlab_url', metavar='gitlab-url')
	parser.add_argument('-k', '--insecure', action='store_true')

	args = parser.parse_args()
	gitlab_url = args.gitlab_url
	ssl_verify = not args.insecure
	if not ssl_verify:
		urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

	gitlab_token = os.environ.get('GITLAB_TOKEN')
	if gitlab_token is None:
		gitlab_token = getpass.getpass('Gitlab private token: ')

	stats = collections.defaultdict(lambda: collections.defaultdict(_stats.CIStats))
	server = gitlab.Gitlab(url=gitlab_url, private_token=gitlab_token, ssl_verify=ssl_verify, timeout=60)

	try:
		_get_stats(server, stats)
	except KeyboardInterrupt:
		tqdm.write("Exiting...")
	finally:
		_stats.print_stats(stats)

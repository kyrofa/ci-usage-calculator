import collections

from tabulate import tabulate

BuildStats = collections.namedtuple('BuildStats', ['timestamp', 'duration'])
BuildInfo = collections.namedtuple('BuildInfo', ['job_name', 'build_number'])

class CIStats:
    def __init__(self, total_builds=0, total_duration=0):
        self.total_builds = total_builds
        self.total_duration = total_duration

def print_stats(stats, unit='job'):
	datapoint_count = 0
	build_count = 0
	min_builds = None
	max_builds = None

	overall_duration = 0
	min_duration = None
	max_duration = None

	tabulated = []

	for year, months in sorted(stats.items()):
		for month, month_stats in sorted(months.items()):
			tabulated.append([f'{year}-{month}', month_stats.total_builds, f'{month_stats.total_duration:.2f}'])

			datapoint_count += 1
			build_count += month_stats.total_builds
			overall_duration += month_stats.total_duration

			min_builds = min([v for v in [min_builds, month_stats.total_builds] if v is not None])
			max_builds = max([v for v in [max_builds, month_stats.total_builds] if v is not None])
			min_duration = min([v for v in [min_duration, month_stats.total_duration] if v is not None])
			max_duration = max([v for v in [max_duration, month_stats.total_duration] if v is not None])

	if datapoint_count > 0:
		print(tabulate(tabulated, headers=['Month', f'{unit.capitalize()} count', 'CI minutes']))

		print(f"\nOverall {unit} number stats:")
		print(f'    min: {min_builds}')
		print(f'    max: {max_builds}')
		print(f'    avg: {build_count/datapoint_count:.2f}')

		print(f"\nOverall {unit} duration stats:")
		print(f'    min: {min_duration:.2f}')
		print(f'    max: {max_duration:.2f}')
		print(f'    avg: {overall_duration/datapoint_count:.2f}')

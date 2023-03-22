from setuptools import setup, find_packages

setup(
    name="ci-usage-calculator",
    version="0.1.0",
    author="Kyle Fazzari",
    author_email="kyrofa@ubuntu.com",
    packages=find_packages("src"),
    package_dir={"": "src"},
    entry_points={
        "console_scripts": [
            "calculate-gitlab-usage=ci_usage_calculator.gitlab:main",
            "calculate-jenkins-usage=ci_usage_calculator.jenkins:main",
        ]
    },
)

from setuptools import setup, find_packages

setup(
    name="task-manager",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "click>=8.0",
        "rich>=10.0",
        "python-dateutil>=2.8",
    ],
    entry_points={
        "console_scripts": [
            "tm=task_manager.cli:cli",
        ],
    },
    python_requires=">=3.8",
)
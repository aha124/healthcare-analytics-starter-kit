"""Setup configuration for Healthcare Analytics Starter Kit."""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [
        line.strip()
        for line in fh
        if line.strip() and not line.startswith("#")
    ]

setup(
    name="healthcare-analytics-starter-kit",
    version="1.0.0",
    author="Anthony Arbaiza",
    author_email="anthony.arbaiza124@gmail.com",
    description="Production-ready healthcare analytics infrastructure using open-source tools",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/aha124/healthcare-analytics-starter-kit",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Healthcare Industry",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Scientific/Engineering :: Medical Science Apps.",
        "Topic :: Database",
        "Typing :: Typed",
    ],
    python_requires=">=3.10",
    install_requires=requirements,
    extras_require={
        "dev": [
            "pytest>=7.4.0",
            "pytest-cov>=4.1.0",
            "black>=23.12.0",
            "ruff>=0.1.0",
            "mypy>=1.8.0",
        ],
        "docs": [
            "mkdocs>=1.5.0",
            "mkdocs-material>=9.5.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "hask-refresh=pipelines.daily_refresh:main",
            "hask-schedule=pipelines.scheduled_tasks:main",
        ],
    },
    include_package_data=True,
    package_data={
        "": ["sql/**/*.sql", "grafana/**/*.json", "grafana/**/*.yml"],
    },
)

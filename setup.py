from setuptools import setup, find_packages


setup(
    name="pqv",
    version="0.4.0",
    author="Pieter Provoost",
    author_email="pieterprovoost@gmail.com",
    description="Simple parquet viewer",
    url="https://github.com/pieterprovoost/pqv",
    license="MIT",
    packages=find_packages(),
    include_package_data=True,
    package_data={"pqv": ["*.css"]},
    license_files=("LICENSE",),
    zip_safe=False,
    entry_points={
        "console_scripts": [
            "pqv = pqv.__main__:main"
        ]
    },
)

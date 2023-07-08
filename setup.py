import setuptools

setuptools.setup(

    name="ZONES",
    version="0.0.2",
    author="Noel M nguemechieu",
    author_email="nguemechieu@live.com",
    description="Trade management software for MetaTrader",
    long_description_content_type="text/x-rst",
    keywords=['run', 'open', 'trade'],
    url="https://github.com/nguemechieu/Zones_EA",
    include_package_data=True,
    package_dir={'ZONES': 'src'},

    packages=['ZONES'],

    license='LICENSE-MIT',
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: LICENSE-MIT",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.11'
)

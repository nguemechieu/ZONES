from setuptools import setup, find_packages

setup(
    name="ZONES",
    version="1.0.0",
    author="Noel M nguemechieu",
    author_email="nguemechieu@live.com",
    description="AI-powered trading software for MetaTrader 4/5",
    long_description_content_type="text/x-rst",
    keywords=['run', 'open', 'trade'],
    url="https://github.com/nguemechieu/zones",
    include_package_data=True,
    zip_safe=False,
    packages=find_packages(),
    license='MIT',  # Corrected the license classifier
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",  # Adjusted the license classifier
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.12',  # Adjusted the minimum Python version
    entry_points={
        'console_scripts': [
            'zones = ZONES.main:main',
        ],
    },
    install_requires=[
        # Adjusted the way to specify requirements
        # Use install_requires directly with a list of dependencies
        'numpy>=1.18.0',
        'pandas>=1.0.0',
        'scikit-learn>=0.22.0',
        'twine',
        'SQLAlchemy>=1.3.2',
        'tkinter',
        'tqdm>=4.41.1',
        'pycryptodome>=3.9.7',
        
        'pyodbc>=4.0.30',
        'pywin32>=227',
        # Add other dependencies as needed
    ],
)

from setuptools import setup, find_packages

setup(
    name="wsn_framework",
    version="1.0.0",
    description="WSN Simulation Framework — NS3 + Python unified test environment",
    packages=find_packages(exclude=["tests*", "docker*"]),
    python_requires=">=3.9",
    install_requires=[
        "numpy>=1.24", "pandas>=2.0", "matplotlib>=3.7",
        "scipy>=1.11", "jinja2>=3.1", "pyyaml>=6.0",
        "seaborn>=0.12", "tabulate>=0.9",
    ],
    entry_points={
        "console_scripts": ["wsn=wsn_framework.cli:main"],
    },
    include_package_data=True,
    package_data={"wsn_framework": ["ns3/templates/*.j2", "configs/*.yaml"]},
)

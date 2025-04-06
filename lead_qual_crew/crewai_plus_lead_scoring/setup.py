from setuptools import setup, find_packages

setup(
    name="crewai_plus_lead_scoring",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "crewai",
        "crewai_tools",
        "pydantic"
    ],
    python_requires=">=3.8",
) 
from setuptools import setup, find_packages

setup(
    name="enterprise-valuation-model",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        line.strip()
        for line in open("requirements.txt").readlines()
        if not line.startswith("#")
    ],
    python_requires=">=3.8",
)

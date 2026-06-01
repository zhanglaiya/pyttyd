from setuptools import setup

setup(
    name="pyttyd",
    install_requires=[
        "fastapi>=0.100",
        "uvicorn[standard]>=0.23",
        "typer>=0.9",
        "python-multipart>=0.0.6",
    ],
    include_package_data=True,
)

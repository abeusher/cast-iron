"""
A python module for debugging the Faust worker.
If you are running locally, you will need to have kafka in your
/etc/hosts file (see README.md)
"""
import faust

from python_worker.etl import app

if __name__ == "__main__":
    worker = faust.Worker(app, loglevel='info')
    worker.execute_from_commandline()

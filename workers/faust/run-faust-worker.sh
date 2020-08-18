#!/bin/bash
faust -A python_worker.etl:app worker -l info

#!/bin/bash
isort .
black .
autopep8 --in-place --aggressive --aggressive -r .
flake8 .

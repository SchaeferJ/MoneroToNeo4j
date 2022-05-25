## Overview

This repository aims to provide a covenient way of importing the Monero Blockchain into a Neo4j Graph Database for Blockchain Analysis. It is a fork of [Malte Möser's code](https://github.com/maltemoeser/moneropaper) that has been slightly updated to support the RingCT transactions currently used by Monero.


**IMPORTANT:** This Readme file has not yet been fully updated to reflect the changes in the code.
## 1. Monero Blockchain Data Export

- Install the [Monero software](https://github.com/monero-project/monero/releases), start the daemon and wait for the node to synchronize
- Install the [requests](https://pypi.python.org/pypi/requests) python library: `pip install requests`
- Run the `monero-to-csv.py` script (i.e., `python monero-to-csv.py`)


## 2. Neo4j Import

- Download and/or install the [Neo4j graph database v3.4.5](https://neo4j.com/download-thanks/?edition=community&release=3.4.5&flavour=unix)
- You should now have a folder structure similar to this:
    - `./csv/`: the Monero blockchain export (CSV files)
    - `./csv-headers/`: the CSV header files
- Use the following import script to use the `neo4j-import` tool for a quick import (you'll need to modify the `--into <DIRECTORY>` directory to match the location of your Neo4j installation)

```
neo4j-import --into <DIRECTORY> --nodes:Block "csv-headers/blocks.csv,csv/blocks.csv" --relationships:PREV_BLOCK "csv-headers/blocks-rels.csv,csv/blocks-rels.csv" --nodes:Transaction "csv-headers/transactions.csv,csv/transactions.csv" --relationships:IN_BLOCK "csv-headers/tx-blocks.csv,csv/tx-blocks.csv" --nodes:Output "csv-headers/outputs.csv,csv/outputs.csv" --relationships:TX_OUTPUT "csv-headers/output-rels.csv,csv/output-rels.csv" --nodes:Input "csv-headers/inputs.csv,csv/inputs.csv" --relationships:TX_INPUT "csv-headers/input-rels.csv,csv/input-rels.csv" --relationships:REFERENCES "csv-headers/input-output-refs.csv,csv/input-output-refs.csv"
```

- Afterwards, you should see a message similar to the following:
```
IMPORT DONE in 5m 41s 347ms.
Imported:
  45169429 nodes
  84119631 relationships
  109326559 properties
Peak memory usage: 1.51 GB
```

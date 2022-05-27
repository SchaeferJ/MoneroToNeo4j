## Overview

This repository aims to provide a covenient way of importing the Monero Blockchain into a Neo4j Graph Database for Blockchain Analysis. It is a fork of [Malte Möser's code](https://github.com/maltemoeser/moneropaper) that has been slightly updated to support the RingCT transactions currently used by Monero.

## 0. System requirements ##

The code should be platform independent, however it has only been tested on Ubuntu.
- At least 260 GB of storage, SSD highly recommended (Size estimates as of May 2022)
  - Size of Monero Blockchain: ~ 140 GB 
  - Size of CSV Files: ~ 60 GB
  - Size of Database: ~ 60 GB
- A fast internet connection for syncing the Monero node


## 1. Monero Blockchain Data Export

- Install the [Monero software](https://www.getmonero.org/downloads/#cli), start the daemon and wait for the node to synchronize
- Install the python dependencies: `pip install -r requirements.txt`
- Run the `monero-to-csv.py` script (i.e., `python monero-to-csv.py`)
- You should now have a folder structure similar to this:
    - `./csv/`: the Monero blockchain export (CSV files)
    - `./csv-headers/`: the CSV header files

## 2. Neo4j Import

- Download and/or install the [Neo4j graph database](https://neo4j.com/docs/operations-manual/current/installation/)
- Use the following script to call the CSV bulk import from `neo4j-admin` for a quick import. **CAUTION**: This expects an entirely empty database! Any data stored in the neo4j-database will be overwritten!
    - Set the `--high-io` parameter to true if the target volume (i.e. the disk you store the database on) supports high throughput parallel IO. ThIs is usually the case for fast SSDs.
```
neo4j-admin import --nodes=Block=csv-headers/blocks.csv,csv/blocks.csv --relationships=PREV_BLOCK=csv-headers/blocks-rels.csv,csv/blocks-rels.csv --nodes=Transaction=csv-headers/transactions.csv,csv/transactions.csv \
--relationships=IN_BLOCK=csv-headers/tx-blocks.csv,csv/tx-blocks.csv --nodes=Output=csv-headers/outputs.csv,csv/outputs.csv --relationships=TX_OUTPUT=csv-headers/output-rels.csv,csv/output-rels.csv \
--nodes=Input=csv-headers/inputs.csv,csv/inputs.csv --relationships=TX_INPUT=csv-headers/input-rels.csv,csv/input-rels.csv --relationships=REFERENCES=csv-headers/input-output-refs.csv,csv/input-output-refs.csv \
--high-io=[true/false] --skip-duplicate-nodes=true --force
```
- Depending on you system configuration, the input process may take a couple of hours.
- Afterwards, you should see a message similar to the following:
```
IMPORT DONE in 1h 17m 51s 526ms.
Imported:
  170011974 nodes
  698528755 relationships
  626808602 properties
Peak memory usage: 2.240GiB
```

## Differences to the original code

The key difference to the original code is that this fork supports RingCT transactions. Implementation-wise, the dictionary lookup
mapping the key indexes to outputs was replaced with an RPC-Call.

Also, some additional features were added as node labels:
- In-Degree, Out-Degree and Tx-Extra for Transactions
- Stealth Addresses for Outputs
- Key Images for Inputs

While the original code used output IDs to reference output-nodes, this fork 
references them based on their stealth address. This causes a minor problem in
terms of data integrity, as Monero does not enforce the uniqueness of stealth
addresses: Multiple transactions can create different outputs all spending to the
same stealth address. As spending any of these outputs would always yield the same key image,
reusing a stealth address essentially burns all but one of the outputs.
Nevertheless, this [has happened](https://monero.stackexchange.com/questions/7746/duplicate-output-keys).
In its current state, this fork is unable to properly reflect this (hence the `--skip-duplicates` option during import).

Given how rare stealth address reuse is, this should not have a significant impact on the usability of the database though. 


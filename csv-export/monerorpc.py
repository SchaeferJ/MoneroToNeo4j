import json
import requests


class MoneroRPCInterface(object):
    def __init__(self, url="http://127.0.0.1:18081/"):
        self.url = url

    def _rpc_data_template(self, method, params=None):
        data = {
            "jsonrpc": "2.0",
            "id": "0",
            "method": method
        }
        if params:
            data["params"] = params
        return data

    def make_request(self, data, url_extension):
        return requests.post(self.url + url_extension, data=json.dumps(data))

    def get_blockcount(self):
        """
        :rtype: int
        :return: the number of blocks in the Monero blockchain
        """
        data = self._rpc_data_template("getblockcount")
        r = self.make_request(data, "json_rpc")
        response = r.json()
        return response["result"]["count"]

    def get_block(self, height):
        """

        :rtype: MoneroBlock
        """
        data = self._rpc_data_template("getblock", params={"height": height})
        r = self.make_request(data, "json_rpc")
        response = r.json()
        block = MoneroBlock()
        block.from_rpc(response)
        return block

    def get_block_header(self, height):
        """

        :rtype: MoneroBlock
        """
        data = {
            "jsonrpc": "2.0",
            "id": "0",
            "method": "getblockheaderbyheight",
            "params": {"height": height}
        }
        r = self.make_request(data, "json_rpc")
        response = r.json()
        block = MoneroBlock()
        block.header_from_rpc(response)
        return block

    def get_transactions(self, tx_hashes):
        """

        :rtype: list[MoneroTransaction]
        """
        data = {
            "txs_hashes": tx_hashes,
            "decode_as_json": True
        }
        r = self.make_request(data, "gettransactions")
        response = r.json()
        txs = []
        for tx, tx_hash in zip(response["txs_as_json"], tx_hashes):
            mtx = MoneroTransaction(tx_hash)
            mtx.from_rpc(json.loads(tx), self)
            txs.append(mtx)
        return txs

    def get_references(self, vin, version, amount):
        """

        :param vin: The Input to look the references up for
        :param version: Transaction version (1 or 2)
        :param amount: The amount consumed by the input (only relevant for v1 transactions)
        :return: list[String], the references outputIDs/stealth addresses
        """
        # We have to look up the key offset to properly define which outputs an input is referencing. This differs
        # between v1 and v2 transactions. See
        # https://monero.stackexchange.com/questions/11550/where-are-the-input-keys-stored-for-a-transaction-understanding-vin-field
        index_list = []
        key_offset = 0
        if version == 1:
            for index in vin["key"]["key_offsets"]:
                key_offset += index
                index_list.append({"index": key_offset, "amount": amount})
            data = {"outputs": index_list}
        elif version == 2:
            for index in vin["key"]["key_offsets"]:
                key_offset += index
                index_list.append({"index": key_offset})
            data = {"outputs": index_list}
        else:
            raise Exception("Unknown transaction type")
        r = self.make_request(data, "get_outs")
        return r.json()

    def get_height(self):
        """
        Retrieves and returns the current height of the blockchain as known to the daemon
        :return: dict, the blockchain information
        """
        r = self.make_request({}, "get_height")
        return r.json()

class MoneroBlock(object):
    def __init__(self):
        self.height = None
        self.block_hash = None
        self.timestamp = None
        self.coinbase = None
        self.header = None
        self.reward = None
        self.tx_hashes = []

    def from_rpc(self, response_json):
        self.header_from_rpc(response_json)

        content = json.loads(response_json["result"]["json"])
        tx = MoneroTransaction(self.header["miner_tx_hash"])
        tx.coinbase_from_rpc(content["miner_tx"])
        self.coinbase = tx
        self.tx_hashes = content["tx_hashes"]

    def header_from_rpc(self, response_json):
        self.header = response_json["result"]["block_header"]
        self.block_hash = self.header["hash"]
        self.height = self.header["height"]
        self.timestamp = self.header["timestamp"]
        self.reward = self.header["reward"]


class MoneroTransaction(object):
    def __init__(self, tx_hash = ""):
        self.tx_hash = tx_hash
        self.inputs = []
        self.outputs = []
        self.fee = None
        self.in_degree = None
        self.out_degree = None
        self.extra = None

    def coinbase_from_rpc(self, obj):
        # RCT coinbase transactions have a single output that counts as a 0-value output
        # https://github.com/monero-project/monero/blob/c534fe8d19aa20a30849ca123f0bd90314659970/src/blockchain_db/blockchain_db.cpp#L179
        #if obj["version"] == 2:
        #    self.outputs.append(MoneroOutput(0))
        #else:
        for output in obj["vout"]:
            self.outputs.append(
                MoneroOutput(output["amount"], output["target"]["key"])
            )
        self.fee = 0
        self.in_degree = 0
        self.out_degree = len(self.outputs)
        self.extra = str(bytes(obj["extra"]).hex())


    def from_rpc(self, obj, interface):
        for vin in obj["vin"]:
            tx_in = MoneroInput(interface)
            tx_in.from_rpc(vin, obj["version"])
            self.inputs.append(tx_in)

        for vout in obj["vout"]:
            self.outputs.append(
                MoneroOutput(vout["amount"], vout["target"]["key"])
            )

        self.in_degree = len(self.inputs)
        self.out_degree = len(self.outputs)
        self.extra = str(bytes(obj["extra"]).hex())
        if "rct_signatures" in obj:
            self.fee = obj["rct_signatures"]["txnFee"]
        else:
            self.fee = sum([x.amount for x in self.inputs]) - sum([x.amount for x in self.outputs])


class MoneroOutput(object):
    def __init__(self, amount, stealth_address):
        self.amount = amount
        self.stealthAddress = stealth_address


class MoneroInput(object):
    def __init__(self, interface):
        self.references = []
        self.key_image = ""
        self.amount = 0
        self.version = 0
        self.interface = interface

    def from_rpc(self, vin, version):
        self.key_image = vin["key"]["k_image"]
        self.amount = vin["key"]["amount"]
        response = self.interface.get_references(vin, version, self.amount)
        self.references = [o["key"] for o in response["outs"]]


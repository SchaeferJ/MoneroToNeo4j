import json
import requests

TX_HEIGHTS = {}

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
        coinbase_tx = self.get_transactions([response["result"]["block_header"]["miner_tx_hash"]])
        block = MoneroBlock(coinbase_tx[0])
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
        for tx, raw_tx, tx_hash in zip(response["txs_as_json"], response["txs"], tx_hashes):
            if raw_tx["as_hex"] == "": # Coinbase TXs
                raw_size = len(raw_tx["pruned_as_hex"]) / 2
            else:
                raw_size = len(raw_tx["as_hex"]) / 2
            mtx = MoneroTransaction(tx_hash, raw_size)
            TX_HEIGHTS[tx_hash] = raw_tx["block_height"]
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
        # Pre-RingCT Transactions and Transactions that are RingCT but input non-RingCT outputs
        if version == 1 or (version == 2 and vin["key"]["amount"] > 0):
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
        data["get_txid"] = True
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
    def __init__(self, coinbase_tx):
        self.height = None
        self.block_hash = None
        self.timestamp = None
        self.coinbase = coinbase_tx
        self.header = None
        self.reward = None
        self.tx_hashes = []

    def from_rpc(self, response_json):
        self.header_from_rpc(response_json)

        content = json.loads(response_json["result"]["json"])
        #tx = MoneroTransaction(self.header["miner_tx_hash"])
        #tx.coinbase_from_rpc(content["miner_tx"])
        #self.coinbase = tx
        self.tx_hashes = content["tx_hashes"]

    def header_from_rpc(self, response_json):
        self.header = response_json["result"]["block_header"]
        self.block_hash = self.header["hash"]
        self.height = self.header["height"]
        self.timestamp = self.header["timestamp"]
        self.reward = self.header["reward"]


class MoneroTransaction(object):
    def __init__(self, tx_hash = "", raw_size=0):
        self.tx_hash = tx_hash
        self.raw_size = raw_size
        self.inputs = []
        self.outputs = []
        self.fee = None
        self.in_degree = None
        self.out_degree = None
        self.extra = None
        self.tx_version = None
        self.is_ringct = None
        self.ringct_version = 0
        self.is_coinbase = False
        ## Data contained in extra
        self.len_padding = 0
        self.tx_pubkey = None
        self.plain_payment_id = None
        self.enc_payment_id = None
        self.extra_nonce = None
        self.merge_mining = None
        self.pubkey_additional = None
        self.minergate = None

    def from_rpc(self, obj, interface):
        self.is_coinbase = "gen" in obj["vin"][0]

        if not self.is_coinbase:
            for vin in obj["vin"]:
                tx_in = MoneroInput(interface)
                tx_in.from_rpc(vin, obj["version"])
                self.inputs.append(tx_in)
            self.in_degree = len(self.inputs)
        else:
            self.in_degree = 0

        for vout in obj["vout"]:
            self.outputs.append(
                MoneroOutput(vout["amount"], vout["target"]["key"])
            )

        self.out_degree = len(self.outputs)
        self.extra = str(bytes(obj["extra"]).hex())
        self.__parse_extra(self.extra)
        self.tx_version = obj["version"]
        self.is_ringct = self.tx_version == 2
        if self.is_ringct:
            self.ringct_version = obj["rct_signatures"]["type"]

        if self.is_ringct and not self.is_coinbase:
            self.fee = obj["rct_signatures"]["txnFee"]
        elif not self.is_ringct and not self.is_coinbase:
            self.fee = sum([x.amount for x in self.inputs]) - sum([x.amount for x in self.outputs])
        else:
            self.fee = 0

    def __parse_extra(self, extra):
        pointer = 0
        extra_contents = {}
        while pointer < len(extra) - 2:
            first_byte = extra[pointer:pointer + 2]
            if first_byte == "00":  # Padding at end of extra
                padding = extra[pointer + 2:]
                assert len(padding) % 2 == 0
                assert all(v == '0' for v in padding)
                self.len_padding = len(padding) / 2
                pointer = len(extra)
            elif first_byte == "01":  # Pubkey, 32 byte
                self.tx_pubkey = extra[pointer + 2:pointer + 2 + 32 * 2]
                pointer += (2 + 32 * 2)
            elif first_byte == "02":  # Extra nonce or payment ID
                if extra[pointer + 2:pointer + 6] == "2100":  # Plaintext Payment ID
                    self.plain_payment_id = extra[pointer + 6:pointer + 6 + 32 * 2]
                    pointer += (6 + 32 * 2)
                elif extra[pointer + 2:pointer + 6] == "0901":  # Encoded Payment ID
                    self.enc_payment_id = extra[pointer + 6:pointer + 6 + 8 * 2]
                    pointer += (6 + 8 * 2)
                else:  # Nonce
                    field_size = int(extra[pointer + 2:pointer + 4], 16)
                    assert field_size <= 255
                    self.extra_nonce = extra[pointer + 4:pointer + 4 + field_size * 2]
                    pointer += (4 + field_size * 2)
            elif first_byte == "03":  # Merge Mining
                field_size = int(extra[pointer + 2:pointer + 4], 16)
                assert field_size <= 255
                self.merge_mining = extra[pointer + 4:pointer + 4 + field_size * 2]
                pointer += (4 + field_size * 2)
            elif first_byte == "04":  # Additional Pubkeys
                key_count = int(extra[pointer + 2:pointer + 4], 16)
                key_list = []
                for i in range(key_count):
                    key_list.append(extra[pointer + 4 + i * 32 * 2:pointer + 4 + (i + 1) * 32 * 2])
                self.pubkey_additional = key_list
                pointer += (4 + (i + 1) * 32 * 2)
            elif first_byte.upper() == "DE":  # Mysterious Minergate
                field_size = int(extra[pointer + 2:pointer + 4], 16)
                assert field_size <= 255
                self.minergate = extra[pointer + 4:pointer + 4 + field_size * 2]
                pointer += (4 + field_size * 2)
            else:
                raise Exception("Invalid tag")
        return extra_contents

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
        self.references_txids = []

    def from_rpc(self, vin, version):
        self.key_image = vin["key"]["k_image"]
        self.amount = vin["key"]["amount"]
        response = self.interface.get_references(vin, version, self.amount)
        self.rrr = response
        self.references = [o["key"] for o in response["outs"]]
        self.references_txids = [o["txid"] for o in response["outs"]]



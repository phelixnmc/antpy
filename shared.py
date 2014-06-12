# todo
# address reuse is evil
# clipboard stuffing / monitoring

import namerpc

txFeeNmc = 0.001

NAMENEWFEENMC = 0.01
NMCSATOSHIS = 100000000

def to_satoshis(v):
    return int(round(float(v) * NMCSATOSHIS, 0))
def from_satoshis(v):
    return round(float(v) / NMCSATOSHIS, 8)

TXFEESATOSHIS = to_satoshis(txFeeNmc)

# from pybitcointools
def select(unspent, value):
    value = int(value)
    high = [u for u in unspent if u["satoshis"] >= value]
    high.sort(key=lambda u:u["satoshis"])
    low = [u for u in unspent if u["satoshis"] < value]
    low.sort(key=lambda u:-u["satoshis"])
    if len(high): return [high[0]]
    i, tv = 0, 0
    while tv < value and i < len(low):
        tv += low[i]["satoshis"]
        i += 1
    if tv < value: raise Exception("Not enough funds")
    return low[:i]

def get_name(vouts):
    names = []    
    for v in vouts:
        try:
            names.append(v["scriptPubKey"]["nameOp"]["name"])
        except KeyError:
            pass
    if len(names) != 1:
        raise IndexError()
    return names[0]

def analyze_tx(tx, rpc):
    print "\nTx fee: " + str(tx["fees"]) + "NMC"
    if tx["fees"] < 0:
        raise Exception("Tx fee is negative. !?")
    if tx["fees"] > NAMENEWFEENMC:
        raise Exception("Transaction fee seems to high.")
    if to_satoshis(tx["fees"]) < to_satoshis(txFeeNmc):
        print "WARNING: Tx fee is lower than current setting."

    try:
        name = get_name(tx["vout"])
    except IndexError:
        raise Exception("Multiple names in offer. Currently not supported.")
    print "Name to transfer:", name

    nameShow = rpc.call("name_show", [name])
    if nameShow == []:
        raise Exception("Name is not registered.")
    sellerAddress = nameShow["address"]
    print "Seller address:", sellerAddress, "(currently holding the name)"

    compensation = 0
    i = 0
    for v in tx["vout"]:
        if (len(v["scriptPubKey"]["addresses"]) == 1 and
            v["scriptPubKey"]["addresses"][0] == sellerAddress):
            compensation += v["value"]
            i += 1
    if i != 1:
        raise Exception("Compensation divided over multiple outputs. Currently not supported.")
    print "Compensation: " + str(compensation)

    sumInputsNmc = sum([i["value"] for i in tx["vin"]])
    print "(Sum of input values: " + str(sumInputsNmc) + "NMC)"
    
    return name

class UnlockWallet(object):
    def __init__(self, rpc):
        self.unlocked = None
        self.rpc = rpc
    def __enter__(self):        
        if not self.rpc.is_locked():
            return self
        print "\nWallet is locked. Manually unlock wallet or enter your passphrase:"
        passPhrase = raw_input()
        if not self.rpc.is_locked():  # manually unlocked in the meantime?
            del passPhrase  # just in case
            return self
        if passPhrase == "":
            raise Exception("Wallet is locked, empty passphrase entered.")
        self.unlocked = True  # set before the actual unlock to be on the safe side
        self.rpc.call("walletpassphrase", [passPhrase, 10])
        del passPhrase
        print
    def __exit__(self, exc_type, exc_value, traceback): 
        if self.unlocked:
            r = self.rpc.call("walletlock")
            if r:
                raise Exception("Error locking wallet: " + str(r))
            self.unlocked = False

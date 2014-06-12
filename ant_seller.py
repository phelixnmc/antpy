#!/usr/bin/python2

### Abstract: seller checks
## Incoming
# Height of compensation to seller address holding the name - user
# Compensation must be in a single output.
# As always all inputs must be signed.
## Outgoing
# Name to transfer is in my wallet.
# Exactly one input is signed with the key that holds the name.
# The value of the signed input is of NAMENEWFEENMC.
# The previous name tx has the same name as this tx. (necessary?)
# There is only one name_op in this tx and in the previous name tx.

import traceback
while 1:
    try:  # pause on error for GUI start
        import namerpc
        import shared

        rpc = namerpc.CoinRpc()
        unlockedWallet = shared.UnlockWallet(rpc)

        if not rpc.blockchain_is_uptodate():
            raise Exception("Blockchain does not seem up to date. Download all blocks first.")

        # tx input
        print "Enter unfinished hex TX from buyer:"
        hexTx = ""
        while 1:
            r = raw_input().strip().replace("\n", "").replace("\r", "").replace(" ", "")
            try:
                int(r, 16)
            except ValueError:
                continue
            hexTx += r
            try:
                tx = rpc.call("decoderawtransaction", [hexTx])        
            except namerpc.RPCError as e:
                if (e.args[0]["error"]["code"] == -8 or e.args[0]["error"]["code"] == -22):  # decode errors
                    continue
                raise
            break
        vinOrig = tx["vin"]

        # analyze tx
        name = shared.analyze_tx(tx, rpc)
        nameList = rpc.call("name_list", [name])
        if nameList == []:
            raise Exception("Name not in wallet: " + str(name))
        if nameList[0].has_key("transferred") and nameList[0]["transferred"]:
            raise Exception("Name has already been transferred: " + str(name))
        sellerAddress = nameList[0]["address"]

        # seller sign
        with unlockedWallet:
            privKey = rpc.call("dumpprivkey", [sellerAddress])
        r = rpc.call("signrawtransaction", [hexTx, [], [privKey]])
        del privKey

        if r["complete"] != True:
            raise Exception("Could not complete transaction.")

        hexTx = r["hex"]
        tx = rpc.call("decoderawtransaction", [hexTx])

        # verify tx
        vinDiff = []
        for v in tx["vin"]:
            if not v in vinOrig:
                vinDiff.append(v)
        if len(vinDiff) != 1:
            raise Exception("Signed more than one input. Bailing due to fraud potential.")
        if vinDiff[0]["value"] != shared.NAMENEWFEENMC:
            raise Exception("Signed wrong input value (" + str(vinDiff[0]["value"]) + "NMC). Bailing due to fraud potential.")

        # verify name (necessary?)
        pTx = rpc.call("getrawtransaction", [vinDiff[0]["txid"], 1])
        try:
            prevName = shared.get_name(pTx["vout"])
        except IndexError:
            raise Exception("Multiple names in previous tx. Currently not supported.")        
        if prevName != name:
            raise Exception("Wrong name in previous tx: " + str(prevName) + " Bailing due to fraud potential.")

        # broadcast
        print "Press <enter> to broadcast, <ctrl-c> to cancel."
        r = raw_input()
        if r != "":
            raise Exception("User break.")

        r = rpc.call("sendrawtransaction", [hexTx])
        print "Done. txID:", r

    except:
        traceback.print_exc()
    finally:
        print "\nPress <enter> for another round, <ctrl-c> to exit."
        raw_input()

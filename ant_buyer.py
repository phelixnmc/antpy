#!/usr/bin/python2

import traceback
while 1:
    try:  # pause on error for GUI start
        import namerpc
        import shared
        rpc = namerpc.CoinRpc()
        unlockedWallet = shared.UnlockWallet(rpc)

        if not rpc.blockchain_is_uptodate():
            raise Exception("Blockchain does not seem up to date. Download all blocks first.")

        # choose name
        print "Enter a name to create a buy offer for. Example: d/nx"
        name = raw_input()
        try:
            sellerAddress = rpc.call("name_show", [name])["address"]
        except namerpc.RpcError as e:
            if e.args[0]["error"]["code"] == -4:  # failed to read from db
                raise Exception("Name is not yet registered.")

        # choose price
        availableBalanceNmc = rpc.call("getbalance") - shared.txFeeNmc
        print "\nYou have %.8fNMC + txFee available in this wallet." % availableBalanceNmc
        print "Enter the amount of NMC you would like to offer for the name:"
        bidNmc = raw_input()
        bidNmc = float(bidNmc)
        if bidNmc >= availableBalanceNmc:
            raise Exception("Not enough funds.")

        # inputs (select uses satoshis)
        bidSatoshis = shared.to_satoshis(bidNmc)
        unspent = rpc.call("listunspent")
        for u in unspent:
            u["satoshis"] = shared.to_satoshis(u["amount"])
        inputs = shared.select(unspent, bidSatoshis + shared.TXFEESATOSHIS)  # !!! check for too many inputs
        sumInputsNmc = sum([i["amount"] for i in inputs])

        # outputs
        outputs = {sellerAddress : bidNmc}  # Bitcoin client will do proper rounding

        changeNmc = sumInputsNmc - bidNmc - shared.txFeeNmc
        if shared.to_satoshis(changeNmc) != 0:
            buyerChangeAddress = rpc.call("getnewaddress")
            outputs[buyerChangeAddress] = changeNmc

        # name_op
        buyerNameAddress = rpc.call("getnewaddress")
        nameOp = {"op" : "name_update",
                  "name" : name,
                  "value" : "",  # name data !!! make changeable by user
                  "address" : buyerNameAddress}

        # assembly
        rawTx = rpc.call("createrawtransaction", [inputs, outputs, nameOp])

        # fee check
        tx = rpc.call("decoderawtransaction", [rawTx])
        if tx["fees"] != shared.txFeeNmc:
            raise Exception("Wrong fee height: " + str(tx["fees"]) + "NMC")

        # buyer sign
        with unlockedWallet:
            r = rpc.call("signrawtransaction", [rawTx])
        rawTx = r["hex"]

        # buyer check
        tx = rpc.call("decoderawtransaction", [rawTx])
        shared.analyze_tx(tx, rpc)

        # output
        print "\n" + rawTx
        print "\nDone. Send the string above to the seller."

    except:
        traceback.print_exc()
    finally:
        print "\nPress <enter> for another round, <ctrl-c> to exit."
        raw_input()

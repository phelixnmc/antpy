# Copyright (C) 2014 by phelix / blockchained.com
# Copyright (C) 2013 by Daniel Kraft <d@domob.eu>
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import base64
import socket
import json
import sys
from os import path, environ
import time

COINAPP = "namecoin"
DEFAULTCLIENTPORT =  8332
DEFAULTNMCONTROLPORT =  9000
HOST = "127.0.0.1"

class RpcError(Exception):
    pass

class RpcConnectionError(Exception):
    pass

class CoinRpc(object):
    """connectionType: client or nmcontrol"""
    def __init__(self, connectionType="client", options=None):
        self.bufsize = 4096
        self.queryid = 1
        self.connectionType = connectionType
        if options == None:
            if connectionType == "nmcontrol":
                options = {"rpcport":"9000"}
            else:
                options = self.get_options()
        self.options = options
        self.host = HOST
        # check connection ?

    def call(self, method="getinfo", params=[]):
        data = {"method": method, "params": params, "id": self.queryid}
        if self.connectionType == "client":
          resp = self.query_http(json.dumps(data))
        elif self.connectionType == "nmcontrol":
          resp = self.query_server(json.dumps(data))
        else:
          assert False
        val = json.loads (resp)

        if self.connectionType != "nmcontrol" and val["id"] != self.queryid:
            raise Exception("ID mismatch in JSON RPC answer.")
        self.queryid = self.queryid + 1

        if val["error"] is not None:
            raise RpcError(val)  # attn: different format for client and nmcontrol

        return val["result"]

    def query_http(self, data):
        """Query the server via HTTP. (client)"""
        header = "POST / HTTP/1.1\n"
        header += "User-Agent: coinrpc\n"
        header += "Host: %s\n" % self.host
        header += "Content-Type: application/json\n"
        header += "Content-Length: %d\n" % len (data)
        header += "Accept: application/json\n"
        authstr = "%s:%s" % (self.options["rpcuser"], self.options["rpcpassword"])
        header += "Authorization: Basic %s\n" % base64.b64encode (authstr)

        resp = self.query_server("%s\n%s" % (header, data))
        lines = resp.split("\r\n")
        result = None
        body = False
        for line in lines:
            if line == "" and not body:
                body = True
            elif body:
                if result is not None:
                    raise Exception("Expected a single line in HTTP response.")
                result = line
        return result

    def query_server(self, data):
        """Helper routine sending data to the RPC server and returning the result."""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.connect((self.host, int(self.options["rpcport"])))
            s.sendall(data)
            result = ""
            while True:
                tmp = s.recv(self.bufsize)
                if not tmp:
                  break
                result += tmp
            s.close()
            return result
        except socket.error as exc:
            raise RpcConnectionError("Socket error in RPC connection to " +
                                     "%s: %s" % (str(self.connectionType), str(exc)))

    def lookup_conf_folder(self):
        if sys.platform == "darwin":
            if "HOME" in environ:
                dataFolder = path.join(environ["HOME"],
                                       "Library/Application Support/", COINAPP) + '/'
            else:
                print ("Could not find home folder, please report.")
                sys.exit()
        elif "win32" in sys.platform or "win64" in sys.platform:
            dataFolder = path.join(environ["APPDATA"], COINAPP) + "\\"
        else:
            dataFolder = path.join(environ["HOME"], ".%s" % COINAPP) + "/"
        return dataFolder

    def get_options(self):
        """Read options (rpcuser/rpcpassword/rpcport) from .conf file."""
        options = {}
        options["rpcport"] = DEFAULTCLIENTPORT
        with open(self.lookup_conf_folder() + COINAPP + ".conf") as f:
            while True:
                line = f.readline()
                if line == "":
                    break
                parts = line.split ("=")
                if len(parts) == 2:
                    key = parts[0].strip()
                    val = parts[1].strip()
                    options[key] = val
        return options


    # comfort functions
    def is_locked(self):
        try:
            self.call("sendtoaddress", ["", 0.00000001])  # Certainly there is a more elegant way to check for a locked wallet?
        except RpcError as e:
            if e.args[0]["error"]["code"] == -4:  # invalid namecoin address
                return False
            if e.args[0]["error"]["code"] == -13:  # wallet is locked
                return True

    def chainage(self):
        c = self.call("getblockcount")
        T = 0
        for i in [0, 1, 2]:
            h = self.call("getblockhash", [c - i])
            t = self.call("getblock", [h])["time"]
            T += t + i * 60 * 9  # conservative
        t = T / 3
        return int(round(time.time() - t))

    def blockchain_is_uptodate(self, period=3600):
        if self.chainage() <= period:
            return True
        else:
            return False

if __name__ == "__main__":
    if len(sys.argv) == 1:
        print "NMControl"
        try:
            rpc = CoinRpc(connectionType="nmcontrol")
            print rpc.call("help")["reply"]
            print rpc.call("data", ["getData", "d/nx"])["reply"]
        except:
            import traceback
            traceback.print_exc()

        print "\n\n\nNamecoind"
        rpc = CoinRpc()
        print rpc.call("getinfo")
        print rpc.call("name_show", ["d/nx"])
    else:
        cmd = sys.argv[1]
        rpc = CoinRpc()
        print rpc.call(cmd, sys.argv[2:])

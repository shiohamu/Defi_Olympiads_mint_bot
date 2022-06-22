import logging
import sqlite3
import os
from concurrent.futures import ThreadPoolExecutor
from web3 import Web3
import sys
import json

class dutch_auction():
    def __init__(self):
        # constant
        self.MedalABI = json.load(open("./ABI/medal_ABI.json","r"))["result"]
        self.TicketABI = json.load(open("./ABI/ticket_ABI.json","r"))["result"]
        self.AuctionABI = json.load(open("./ABI/auction_ABI.json","r"))["result"]
        self.MedalAddress = "0xa9A3f0CEdd9Aaa1Cd16BF6c377fbaaD59f9bEeA3"
        self.TicketAddress = "0x97DeB227e81533882BeE467f7EE67fDCb8EF2126"
        self.AuctionAddress = "0xD5D5C07CC2A21fce523b8C16B51F769B0aFa08B4"
        # setting load by settings.json file
        keys = json.load(open("./settings.json","r"))
        self.slippage = keys["slippage"]
        self.transaction_speed = keys["transaction_speed"]
        self.gas_limit_gwei = keys["gas_limit_gwei"]
        self.rpc = keys["rpc"]
        # blockchain connect 
        print("---------------------------------")
        self.fantom = Web3(Web3.HTTPProvider(self.rpc))
        if self.fantom.isConnected() == True:
            print("fantom network connetcted.")
        else:
            print("fantom network not connected.")
            sys.exit(0)
        print("---------------------------------")

        # balance setting
        self.wallet = self.fantom.toChecksumAddress(keys["wallet_address"])
        self.privatekey = keys["wallet_privatekey"]
        self.ftm_balance_limit = self.fantom.toWei(keys["ftm_balance_limit"],"ether")
        self.ticket_quantity = self.fantom.toWei(keys["ticket_quantity"],"ether")
        self.mint_quantity = int(self.fantom.toWei(keys["mint_quantity"],"ether"))

        # database setting
        self.database_init()

        # contract setting
        self.medal = self.fantom.eth.contract(address=self.MedalAddress,abi=self.MedalABI)
        self.ticket = self.fantom.eth.contract(address=self.TicketAddress,abi=self.TicketABI)
        self.auction = self.fantom.eth.contract(address=self.AuctionAddress,abi=self.AuctionABI)

        # balance output
        while 1:
            try:
                self.ftm_balance = int(self.fantom.eth.getBalance(self.wallet))
                break
            except:
                print("FTM get_balance failed. but no problem, one more try.")
                continue
        
        if self.ftm_balance <= self.ftm_balance_limit:
            print("FTM balance is low...\nprogram exit.")
            os.system("pause")
            sys.exit(0)
        else:
            print("FTM balance is    "+ str(self.fantom.fromWei(self.ftm_balance,"ether")))

        while 1:
            try:
                self.ticket_balance = self.ticket.caller.balanceOf(self.wallet)
                break
            except Exception as error:
                print(error)
                print("Ticket get_balance failed. but no problem, one more try.")
                continue

        if self.ticket_balance <= self.ticket_quantity:
            print("Ticket balance is low...\nprogram exit.")
            os.system("pause")
            sys.exit(0)
        
        else:
            print("Ticket balance is "+ str(self.fantom.fromWei(self.ticket_balance,"ether")))
        while 1:
            try:
                self.medal_balance = self.medal.caller.balanceOf(self.wallet)
                break
            except Exception as e:
                print(e)
                print("Medal get_balance failed. but no problem, one more try.")
                continue


        print("Medal balance is  " + str(self.fantom.fromWei(self.medal_balance,"ether")))
        print("---------------------------------")

    def bot_start(self):
        # gas price generate
        print("gas generating...")
        self.get_gas()
        print("gas limit is " + str(int(self.gas_limit_gwei)) + " gwei.")
        print("---------------------------------")


        while 1:
            # medal mint quantity
            try:
                self.now_ticket_mint = int(self.auction.caller.getY(int(self.ticket_quantity)))
            
            except Exception as e:
                print(e)
                print("getY failed. but no problem, one more try.")
                continue

            if(self.now_ticket_mint > self.mint_quantity):
                print("now mint medal will "+ str(self.fantom.fromWei(self.now_ticket_mint,"ether")))

                # Thread setting
                with ThreadPoolExecutor(max_workers=2) as e:
                    e.submit(self.get_nonce())
                    e.submit(self.get_gas())

                # transaction setting
                try :
                    txn = self.auction.functions.swap(
                        x=self.ticket_quantity, 
                        minY=int(self.now_ticket_mint * ((100 - self.slippage) / 100))
                    ).buildTransaction({
                            "from":self.wallet,
                            "gasPrice":int(self.fantom.toWei(self.gas,"gwei")),
                            "nonce":self.nonce,
                    })
                    print("transaction builded.")
                    print("this transaction gas will " + str(self.gas) + " gwei.")
                except Exception as error:
                    # slippage low
                    if str(error).find("InsufficientY"):
                        print("slippage loss is over limit.")
                        print("program exit.")
                        os.system("pause")
                        sys.exit()
                    # slippage low2
                    elif str(error).find("underpriced"):
                        print("slippage loss is over limit.")
                        print("program exit.")
                        os.system("pause")
                        sys.exit()
                    # other error
                    else:
                        print("build transaction error.")
                        print(error)
                        print("program exit.")
                        os.system("pause")
                        sys.exit()

                # transaction sign
                signed_txn = self.fantom.eth.account.sign_transaction(
                    txn,
                    self.privatekey
                )
                print("transaction signed.")
                
                # transaction adopt waiting
                try:                
                    tx_hash = self.fantom.eth.send_raw_transaction(signed_txn.rawTransaction)
                    print("transaction sending...")
                    receipt = self.fantom.eth.wait_for_transaction_receipt(tx_hash)
                    # success
                    if receipt["status"] == 1:
                        print("---------------------------------")
                        print("transaction is success!")
                        mint_medal = self.fantom.fromWei(
                            self.fantom.toInt(
                            hexstr = receipt["logs"][2]["data"]),"ether")
                        print("now minting medal is " + str(mint_medal))
                        self.update_database(self.fantom.toHex(receipt["transactionHash"]),"txn_hash")
                        self.update_database(receipt["gasUsed"],"gas")
                        self.update_database(self.nonce,"nonce")
                        self.medal_balance = self.medal.caller.balanceOf(self.wallet)
                        print("database updated.")
                        print("Now medal balance is " + str(self.fantom.fromWei(self.medal_balance,"ether")))
                    # failed
                    else:
                        print("---------------------------------")
                        print("transaction failed...")
                        self.update_database(self.fantom.toHex(receipt["transactionHash"]),"txn_hash")
                        self.update_database(receipt["gasUsed"],"gas")
                        self.update_database(self.nonce,"nonce")
                        print("database updated.")
                # error
                except Exception as error:
                    # transaction failed
                    if receipt["status"] != 1:
                        print("---------------------------------")
                        print("transaction failed...")
                        continue
                    # time out
                    elif str(error).find("timed out"):
                        print("---------------------------------")
                        print("transaction failed...")
                        print("transaction timed out.")
                        continue
                    # nonce error
                    elif str(error).find("nonce too low"):
                        print("---------------------------------")
                        print("transaction failed...")
                        print("nonce too low.\nplease modify nonce or wait a few minute.")
                    # other error
                    else:
                        print("---------------------------------")
                        print("transaction failed...")
                        print("program exit.")
                    os.system("pause")
                    sys.exit()
                # ftm balance check
                self.ftm_balance = self.fantom.eth.getBalance(self.wallet)
                if self.ftm_balance_limit <= self.ftm_balance:
                    # ticket balance check
                    self.ticket_balance = self.ticket.caller.balanceOf(self.wallet)
                    if self.ticket_quantity <= self.ticket_balance:
                        # balance is over
                        print("Ticket balance is    " + str(self.fantom.fromWei(self.ticket_balance, "ether")))
                        print("FTM balance is       " + str(self.fantom.fromWei(self.ftm_balance,"ether")) + "\nbegin next trade...")
                        print("---------------------------------")
                        continue

                    else :
                        # under Ticket balance
                        print("Ticket balance is low...\nprogram exit.")
                        os.system("pause")
                        sys.exit(0)

                else:
                    # under ftm balances limit
                    print("FTM balance is low...\nprogram exit.")
                    os.system("pause")
                    sys.exit(0)
    
    def get_gas(self):
        first_loop = True
        while 1:
            try: 
                self.gas = int(self.fantom.fromWei(self.fantom.eth.gas_price,"gwei"))
                if self.gas <= self.gas_limit_gwei:
                    print("gas fee is   " + str(self.gas) + " gwei.")
                    break
                elif first_loop == True:
                    print("gas fee is higher to limit. please wait.")
                    first_loop = False
            except:
                print("gas error. continued")


    def get_nonce(self):
        self.nonce = int(self.fantom.eth.get_transaction_count(self.wallet,"pending"))
        sql = """select data from last_txn where name = 'nonce'"""
        db_nonce = int(list(self.cur.execute(sql))[0][0])

        if  db_nonce < self.nonce:
            print("get nonce.")
        else:
            self.nonce = db_nonce + 1
            print("nonce updated.")



    def database_init(self):
        # init
        self.db = sqlite3.connect("local_data.db")
        self.cur = self.db.cursor()

        # table init
        sql = """create table if not exists last_txn(id int, name str, data)"""
        self.cur.execute(sql)
        self.db.commit()

        # make record
        sql = """select * from last_txn"""
        self.cur.execute(sql)
        if not(list(self.cur)):
            sql = """insert into last_txn values(?, ?, ?) """
            data = (1, "txn_hash", 0)
            self.cur.execute(sql,data)
            self.db.commit()
            sql = """insert into last_txn values(?, ?, ?) """
            data = (2, "gas", 0)
            self.cur.execute(sql,data)
            self.db.commit()
            sql = """insert into last_txn values(?, ?, ?) """
            data = (3, "nonce", 0)
            self.cur.execute(sql,data)
            self.db.commit()

    def update_database(self, data, name):
        sql = """update last_txn set data = ? where name = ?"""
        values = (data, name)
        self.cur.execute(sql, values)
        self.db.commit()
        
# start up seaquance
if __name__ == "__main__":
    try:
        dutch_auction().bot_start()
    
    except Exception as error:
        logging.exception(error)
        print("error log\n" + str(error))
        os.system('pause')
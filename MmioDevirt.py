#!/usr/bin/env python
import sys, os
from Scripts import plist, utils

class MmioDevirt:
    def __init__(self):
        self.u = utils.Utils("MmioDevirt")

    def error(self,title = None, message = None):
        self.u.head(title)
        print("")
        print(message)
        print("")
        self.u.grab("Press [enter] to return...")

    def main(self):
        p = None
        while True:
            self.u.head()
            print("")
            print("Please drag and drop your opencore-[timestamp].txt log here.")
            print("")
            print("Make sure the log is from a macOS boot attempt (recovery also works), that")
            print("you're using the debug build of OpenCore, and that you have DevirtualiseMmio")
            print("enabled in your config.plist!")
            print("")
            print("Q. Quit")
            print("")
            menu = self.u.grab("Please drag and drop the log here:  ")
            if not menu: continue
            if menu.lower() == "q":
                self.u.custom_quit()
            m_path = self.u.check_path(menu)
            if not m_path:
                self.error(title="Invalid Path",message="Could not locate:\n{}".format(menu))
                continue
            if not os.path.isfile(m_path):
                self.error(title="Invalid Path",message="The following is a directory, not an OpenCore log:\n{}".format(menu))
                continue
            # Should have a valid path - try to open as text
            self.u.head()
            print("")
            print("Loading {}...".format(os.path.basename(m_path)))
            try:
                with open(m_path,"r") as f:
                    log = f.read()
            except Exception as e:
                self.error(title="Error Loading File",message="Could not read file:\n{}".format(e))
                continue # Invalid file
            # Iterate the lines and keep track of each Mmio Devirt entry
            print("Walking log for MMIO devirt entries...")
            mmio_primed = False
            mmio_devirt = []
            for l in log.split("\n"):
                if "OCABC: MMIO devirt start" in l:
                    print("Located MMIO devirt start...")
                    mmio_primed = True
                    continue
                if "OCABC: MMIO devirt end" in l:
                    print("Located MMIO devirt end...")
                    break # Done
                if not mmio_primed:
                    continue
                # Primed, get the address
                try:
                    addr = l.split("OCABC: MMIO devirt ")[1].split(" (")[0]
                    try:
                        pages = int(l.split("(")[1].split()[0],16)
                        page = " (0x{} page{})".format(
                            hex(pages)[2:].upper(),
                            "" if pages == 1 else "s"
                        )
                    except:
                        page = ""
                    print("Located MMIO devirt at {}".format(addr))
                    mmio_devirt.append({
                        "Comment" : "MMIO devirt {}{}".format(addr,page),
                        "Address" : int(addr,16),
                        "Enabled" : False
                    })
                except Exception as e:
                    print(" - Failed: {}".format(e))
            if not mmio_devirt:
                print("")
                print("No MMIO devirt entries found!")
                print("")
                print("Make sure you are using a debug build of OpenCore, and have DevirtualiseMmio")
                print("enabled in your config.plist!")
                print("")
                print("")
                self.u.grab("Press [enter] to return...")
                continue
            print("Got {:,} entr{}...".format(len(mmio_devirt),"y" if len(mmio_devirt)==1 else "ies"))
            print("Dumping to plist data...")
            print("")
            print("")
            print("------------------ Start Plist Data ------------------")
            print("")
            print(plist.dumps({"Booter":{"MmioWhitelist":mmio_devirt}}).strip())
            print("")
            print("------------------- End Plist Data -------------------")
            print("")
            self.u.grab("Press [enter] to return...")

if __name__ == '__main__':
    m = MmioDevirt()
    m.main()

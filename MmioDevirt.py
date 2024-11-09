#!/usr/bin/env python
import sys, os
from Scripts import plist, utils

class MmioDevirt:
    def __init__(self):
        self.u = utils.Utils("MmioDevirt")
        self.log = None
        self.cr2 = []

    def get_log(self):
        while True:
            self.u.head()
            print("")
            print("Please drag and drop your opencore-[timestamp].txt log here.")
            print("")
            print("Make sure the log is from a macOS boot attempt (recovery also works), that")
            print("you're using the debug build of OpenCore, and that you have DevirtualiseMmio")
            print("enabled in your config.plist!")
            print("")
            print("M. Return to Menu")
            print("Q. Quit")
            print("")
            menu = self.u.grab("Please drag and drop the log here:  ")
            if not menu: continue
            if menu.lower() == "q":
                self.u.custom_quit()
            elif menu.lower() == "m":
                return self.log
            m_path = self.u.check_path(menu)
            if not m_path:
                self.error(title="Invalid Path",message="Could not locate:\n{}".format(menu))
                continue
            if not os.path.isfile(m_path):
                self.error(title="Invalid Path",message="The following is a directory, not an OpenCore log:\n{}".format(menu))
                continue
            return m_path

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
            print("Current CR2 Addresses:")
            if not self.cr2:
                print(" - None")
            else:
                for i,x in enumerate(sorted(self.cr2),start=1):
                    print(" - {}. 0x{}".format(i,hex(x)[2:].upper()))
            print("Selected Log:")
            if self.log and not os.path.isfile(self.log):
                self.log = None # Reset if it doesn't exist
            print(" - {}".format(os.path.basename(self.log) if self.log else "None"))
            print("")
            print("L. Select Debug OpenCore Log")
            print("C. Clear All CR2 Addresses")
            print("P. Process Debug OpenCore Log")
            print("")
            print("Q. Quit")
            print("")
            print("Add CR2 addresses by typing them with the 0x prefix (e.g. 0xFF000000)")
            print("Remove CR2 addresses by typing the number preceeding them (e.g. 1)")
            print("")
            menu = self.u.grab("Please select an option:  ")
            if not len(menu):
                if self.log:
                    menu = self.log
                else:
                    continue
            menu_path = self.u.check_path(menu)
            if menu.lower() == "q":
                self.u.custom_quit()
            elif menu.lower() == "l":
                self.log = self.get_log()
            elif menu.lower() == "c":
                self.cr2 = []
            elif menu.lower() == "p" or menu_path:
                if menu_path:
                    self.log = menu_path
                self.process_log()
            else:
                # Check if we got hex - or an integer
                try:
                    remove_int = int(menu)-1
                    assert 0 <= remove_int < len(self.cr2)
                    del self.cr2[remove_int]
                except Exception:
                    try:
                        add_addr = int(menu,16)
                        if not add_addr in self.cr2:
                            self.cr2.append(add_addr)
                    except ValueError:
                        continue # Nope
    
    def process_log(self):
        # Ensure we have a log
        if not self.log or not os.path.isfile(self.log):
            self.log = self.get_log()
        if not self.log or not os.path.isfile(self.log):
            return # No log to process
        # Should have a valid path - try to open as text
        self.u.head()
        print("")
        print("Loading {}...".format(os.path.basename(self.log)))
        try:
            with open(self.log,"r") as f:
                log = f.read()
        except Exception as e:
            self.error(title="Error Loading File",message="Could not read file:\n{}".format(e))
            return # Invalid file
        # Iterate the lines and keep track of each Mmio Devirt entry
        print("Walking log for MMIO devirt entries...")
        mmio_primed = False
        mmio_devirt = []
        cr2_found = []
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
            #try:
            addr = l.split("OCABC: MMIO devirt ")[1].split(" (")[0]
            try:
                pages = int(l.split("(")[1].split()[0],16)
                page = " (0x{} page{})".format(
                    hex(pages)[2:].upper(),
                    "" if pages == 1 else "s"
                )
            except:
                pages = 0
                page = ""
            print("Located MMIO devirt: {}{}".format(addr,page))
            enabled = False
            matches = []
            start = int(addr,16)
            end   = (start + pages * 4096) - 1
            print(" - Range: 0x{} -> 0x{}".format(
                hex(start)[2:].upper(),
                hex(end)[2:].upper()
            ))
            if self.cr2 and pages:
                # Check the address and see if any of our CR2 addresses fall
                # within that
                for c in self.cr2:
                    if start <= c <= end:
                        # Got a match
                        matches.append("0x{}".format(hex(c)[2:].upper()))
                        if not c in cr2_found:
                            cr2_found.append(c)
                if matches:
                    print(" -> Matched CR2: {}".format(", ".join(matches)))
                    print(" -> Enabling...")
                    enabled = True
            mmio_devirt.append({
                "Comment" : "MMIO devirt {}{}{}".format(
                    addr,
                    page,
                    " - Matched CR2: {}".format(", ".join(matches)) if matches else ""
                ),
                "Address" : start,
                "Enabled" : enabled
            })
            #except Exception as e:
            #    print(" - Failed: {}".format(e))
        if not mmio_devirt:
            print("")
            print("No MMIO devirt entries found!")
            print("")
            print("Make sure the log is from a macOS boot attempt (recovery also works), that")
            print("you're using the debug build of OpenCore, and that you have DevirtualiseMmio")
            print("enabled in your config.plist!")
            print("")
            self.u.grab("Press [enter] to return...")
            return
        print("Got {:,} entr{}...".format(len(mmio_devirt),"y" if len(mmio_devirt)==1 else "ies"))
        print("Dumping to plist data...")
        # Add some comments that further show users where to start and stop copying
        plist_parts = []
        for line in plist.dumps({"Booter":{"MmioWhitelist":mmio_devirt}}).strip().split("\n"):
            if "</array>" in line:
                plist_parts.extend((
                    "",
                    line.split("<")[0]+"<!-- END COPYING HERE -->",
                    ""
                ))
            plist_parts.append(line)
            if "<array>" in line:
                plist_parts.extend((
                    "",
                    line.split("<")[0]+"<!-- START COPYING HERE -->",
                    ""
                ))
        print("")
        print("")
        print("------------------ Start Plist Data ------------------")
        print("")
        print("\n".join(plist_parts))
        print("")
        print("------------------- End Plist Data -------------------")
        print("")
        not_found = [x for x in self.cr2 if not x in cr2_found]
        if not_found:
            # We didn't find them all
            print("The following CR2 addresses were not matched:")
            for x in sorted(not_found):
                print(" - 0x{}".format(hex(x)[2:].upper()))
            print("")
        self.u.grab("Press [enter] to return...")

if __name__ == '__main__':
    m = MmioDevirt()
    m.main()

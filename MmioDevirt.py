#!/usr/bin/env python
import sys, os
from Scripts import plist, utils

class MmioDevirt:
    def __init__(self):
        self.u = utils.Utils("MmioDevirt")
        self.log = None
        self.auto_disable = 0
        self.auto_disable_print = {
            0:"Disabled",
            1:"Big Sur and Later ~200 MB",
            2:"Catalina and Prior ~128 MB"
        }
        self.auto_disable_size = {
            0:0,
            1:200 * 1024 ** 2, # 200 MB
            2:128 * 1024 ** 2, # 128 MB
        }
        self.cr2 = []


    def get_size(self, size, suffix=None, round_to=2, strip_zeroes=False):
        # Failsafe in case our size is unknown
        if size == -1:
            return "Unknown"
        ext = ["B","KB","MB","GB","TB","PB"]
        div = 1024
        s = float(size)
        s_dict = {} # Initialize our dict
        # Iterate the ext list, and divide by 1000 or 1024 each time to setup the dict {ext:val}
        for e in ext:
            s_dict[e] = s
            s /= div
        # Get our suffix if provided - will be set to None if not found, or if started as None
        suffix = next((x for x in ext if x.lower() == suffix.lower()),None) if suffix else suffix
        # Get the largest value that's still over 1
        biggest = suffix if suffix else next((x for x in ext[::-1] if s_dict[x] >= 1), "B")
        # Determine our rounding approach - first make sure it's an int; default to 2 on error
        try:round_to=int(round_to)
        except:round_to=2
        round_to = 0 if round_to < 0 else 15 if round_to > 15 else round_to # Ensure it's between 0 and 15
        bval = round(s_dict[biggest], round_to)
        # Split our number based on decimal points
        a,b = str(bval).split(".")
        # Check if we need to strip or pad zeroes
        b = b.rstrip("0") if strip_zeroes else b.ljust(round_to,"0") if round_to > 0 else ""
        return "{:,}{} {}".format(int(a),"" if not b else "."+b,biggest)

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
            print("A. Auto-Enable Entries Based On Size (Currently: {})".format(
                self.auto_disable_print.get(self.auto_disable,"Disabled")
            ))
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
            elif menu.lower() == "a":
                self.auto_disable += 1
                if self.auto_disable > 2:
                    self.auto_disable = 0
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
                size = self.get_size(pages*4096,strip_zeroes=True)
                page = " (0x{} page{} - {})".format(
                    hex(pages)[2:].upper(),
                    "" if pages == 1 else "s",
                    size
                )
            except:
                pages = 0
                page = ""
            print("Located MMIO devirt: {}{}".format(addr,page))
            enabled = False
            comment = ""
            matches = []
            start = int(addr,16)
            end   = (start + pages * 4096) - 1
            print(" - Range: 0x{} -> 0x{}".format(
                hex(start)[2:].upper(),
                hex(end)[2:].upper()
            ))
            if pages:
                # Check if we have a CR2 address match - and if not
                # check entry size if auto enabling
                if self.cr2:
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
                        comment = " - Matched CR2: {}".format(", ".join(matches))
                        enabled = True
                # Only check entry size if auto enabling, and not already
                # enabled
                if self.auto_disable and not enabled and \
                pages * 4096 < self.auto_disable_size.get(self.auto_disable,0):
                    print(" -> Cannot Fit Kernel")
                    print(" -> Enabling...")
                    comment = " - Cannot Fit Kernel"
                    enabled = True
            mmio_devirt.append({
                "Comment" : "MMIO devirt {}{}{}".format(
                    addr,
                    page,
                    comment
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

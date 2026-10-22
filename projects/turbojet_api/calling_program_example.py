
import sys
print("Python executable:", sys.executable)
# from gspy.api.arp4868 import *
import gspy.api.arp4868 as arp4868

def main():
    # args = ["turbojet_api", "build_model", "./projects/turbojet_api"]
    args = ["turbojet_api", "build_model"]
    st = arp4868.py4868initProg(len(args), args)
    if st != 0:
        msg = [""]
        # arp4868.py4868getErrorMsg(msg, 2000)
        raise RuntimeError(msg[0])

    arp4868.py4868activateLog("stdOut")

    # Example: either parse a CSV or use parseString
    # arp4868.py4868parseFile("./projects/turbojet/input/Turbojet_AMinput.csv")
    arp4868.py4868parseString("setD ambient.Ts000=288.15; setD ambient.Ps000=101325")

    arp4868.py4868run()

    # get an output from OutputTable last row
    Fn = [0.0]
    arp4868.py4868getD("Fn", Fn)
    print("Fn", Fn[0])

    arp4868.py4868terminate()


if __name__ == "__main__":
    main()

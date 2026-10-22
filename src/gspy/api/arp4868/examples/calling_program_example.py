from gspy.api.arp4868 import *

def main():
    args = ["projects.turbojet_api.turbojet_api", "build_model", "./projects/turbojet_api"]
    st = py4868initProg(len(args), args)
    if st != 0:
        msg = [""]
        py4868getErrorMsg(msg, 2000)
        raise RuntimeError(msg[0])

    py4868activateLog("stdOut")

    # Example: either parse a CSV or use parseString
    # py4868parseFile("./projects/turbojet/input/Turbojet_AMinput.csv")
    py4868parseString("setD ambient.Ts000=288.15; setD ambient.Ps000=101325")

    py4868run()

    # get an output from OutputTable last row
    Fn = [0.0]
    py4868getD("Fn", Fn)
    print("Fn", Fn[0])

    py4868terminate()


if __name__ == "__main__":
    main()

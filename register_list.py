import os
from amaranth import Signal


class RegConf(dict):
    def __init__(self, addr, bits, signame, reset=0):
        self.addr = addr
        self.reset = reset
        self.bits = bits
        self.name = signame
        self.signal = Signal(bits, name=signame, reset=self.reset)
        dict.__init__(self, addr=addr, reset=reset, bits=bits, name=signame)


def print_as_table(reg, name):
    text = "Register list '{}'\n".format(name)
    text += "----------------------------------------------\n"
    text += "  addr bits    default    maximum name\n"
    text += "----------------------------------------------\n"
    for r1 in reg:
        it = reg[r1]
        if type(it) is list:
            for i, item in enumerate(reg[r1]):
                for r0 in reg[r1][i]:
                    r = reg[r1][i][r0]
                    maximum = (1 << r.bits)
                    text += "0x{:04x}: {:3d} {:10d} {:10d} {}\n".format(
                            r.addr, r.bits, r.reset, maximum, r.name)
        else:
            for r0 in reg[r1]:
                r = reg[r1][r0]
                maximum = (1 << r.bits)
                text += "0x{:04x}: {:3d} {:10d} {:10d} {}\n".format(
                        r.addr, r.bits, r.reset, maximum, r.name)
    return text


def register_list(listname, offset, names):
    regs = {}
    for i, conf in enumerate(names):
        if len(conf) == 2:
            name, bits = conf
            reset = 0
        elif len(conf) == 3:
            name, bits, reset = conf
        else:
            print("ERROR: register item must be a 2 or 3 tuple.")
            os.abort()
        signame = listname + "_" + name
        regs[name] = RegConf(offset + i, bits, signame, reset)
    return regs
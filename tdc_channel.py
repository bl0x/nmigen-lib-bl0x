from amaranth import *
from amaranth.sim import *
from amaranth.lib.fifo import AsyncFIFO
from amaranth.lib.cdc import PulseSynchronizer

from tdc import Tdc
from tdc_to_hit import TdcToHit

# This implements a single channel TDC (time-to-digital converter).
# The time resolution is determined by the time scale of the "fast" clocks.
# A "fast" clock of 250 MHz yields a time resolution of (1/250e6)/4 s = 1 ns.
# Measurement starts at rising edge of input, and stops at falling edge.

# Interface:
#   input: Signal to be measured
#   time: Timestamp to attach to the converted data
#   output: 16 bit timestamp & 16 bit measured time
#   counter: number of rising edges of input signal seen

class TdcChannel(Elaboratable):

    def __init__(self, name):
        # in
        self.input = Signal()
        self.time = Signal(32)
        self.strobe = Signal()
        self.name = name
        # out
        self.output = Signal(32)
        self.counter = Signal(16)

        self.debug_tdc_rdy = Signal()
        self.debug_fifo_rdy = Signal()
        self.debug_hit_busy = Signal()
        self.debug_hit_rdy = Signal()
        self.strobe2 = Signal()

    def elaborate(self, platform):

        tdc = Tdc(self.name)
        fifo = AsyncFIFO(width=38, depth=16, w_domain="fast", r_domain="sync")
        tdc2hit = TdcToHit()

        m = Module()

        m.d.comb += [
            tdc.input.eq(self.input),
            tdc.time.eq(self.time),
            fifo.w_data.eq(tdc.output),
            fifo.w_en.eq(tdc.rdy),
            tdc2hit.input.eq(fifo.r_data),
            tdc2hit.strobe.eq(self.strobe),
            self.output.eq(Mux(tdc2hit.rdy, tdc2hit.output, 0xffffffff)),
            self.counter.eq(tdc2hit.counter_rise)
        ]

        m.d.comb += [
            self.debug_tdc_rdy.eq(tdc.rdy),
            self.debug_fifo_rdy.eq(fifo.r_rdy),
            self.debug_hit_busy.eq(tdc2hit.busy),
            self.debug_hit_rdy.eq(tdc2hit.rdy)
        ]

        with m.FSM(reset="WAIT_STROBE") as strobe_fsm:
            with m.State("WAIT_STROBE"):
                m.d.sync += self.strobe2.eq(0)
                with m.If(self.strobe == 1):
                    m.next = "WAIT_FIFO"
            with m.State("WAIT_FIFO"):
                with m.If((fifo.r_rdy) & (fifo.r_level > 1)):
                    m.d.sync += self.strobe2.eq(1)
                    m.next = "GO1"
            with m.State("GO1"):
                m.d.sync += self.strobe2.eq(0)
                m.next = "GO2"
            with m.State("GO2"):
                m.d.sync += self.strobe2.eq(1)
                m.next = "GO3"
            with m.State("GO3"):
                m.d.sync += self.strobe2.eq(0)
                m.next = "WAIT_STROBE"

        with m.If((fifo.r_rdy == 1) & (tdc2hit.busy != 1) & (self.strobe2 == 1)):
            m.d.sync += fifo.r_en.eq(~fifo.r_en)
        with m.Else():
            m.d.sync += fifo.r_en.eq(0)

        m.submodules.tdc = tdc
        m.submodules.fifo = fifo
        m.submodules.tdc2hit = tdc2hit

        return m

if __name__ == "__main__":
    dut = DomainRenamer("clk100")(TdcChannel("test"))
    i0 = Signal()
    t = Signal(32)
    out = Signal(32)
    counter = Signal(16)
    strobe = Signal()
    strobe_100 = Signal()

    m = Module()
    m.domains += ClockDomain("sync")
    m.domains += ClockDomain("fast")
    m.domains += ClockDomain("input")
    m.submodules.dut = dut

    strobe_sync = PulseSynchronizer("sync", "clk100")
    m.submodules.strobe_sync = strobe_sync

    m.d.comb += [
        strobe_sync.i.eq(strobe),
        strobe_100.eq(strobe_sync.o),
        dut.input.eq(i0),
        dut.time.eq(t),
        out.eq(dut.output),
        counter.eq(dut.counter),
        dut.strobe.eq(strobe_100)
    ]

    sim = Simulator(m)

    stop = 130

    def time():
        for i in range(stop):
            yield t.eq(t + 1)
            yield

    def proc():
        yield

    def pulse(steps):
        for i in range(steps):
            yield i0.eq(1)
            yield
        yield i0.eq(0)
        yield

    def pause(steps):
        for i in range(steps):
            yield

    def input():
        for i in range(5):
            yield from pulse(i)
            yield from pause(5)

        yield from pause(40)
        yield from pulse(17)
        yield from pause(80)
        yield from pulse(37)

    def do_strobe():
        yield strobe.eq(1)
        yield
        yield strobe.eq(0)
        yield

    def reader():
        for i in range(5):
            yield from do_strobe()
            yield from pause(3)

    sim.add_clock(1/12e6)
    sim.add_clock(1/100e6, domain="clk100")
    sim.add_clock(1/500e6, domain="input")
    sim.add_clock(1/250e6, domain="fast")
    sim.add_clock(1/250e6, phase=(1/250e6)/4, domain="fast_90")
    sim.add_sync_process(proc)
    sim.add_sync_process(reader)
    sim.add_sync_process(time, domain="fast")
    sim.add_sync_process(input, domain="input")
    with sim.write_vcd("tdc_fifo_hit.vcd", "tdc_fifo_hit_orig.gtkw"):
        sim.run()

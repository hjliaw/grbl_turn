"""GrblWorker driven synchronously against the in-process simulator."""

from grbl_turn.comms.grbl import GrblWorker, parse_status
from grbl_turn.comms.simulator import SimTransport


def make_worker():
    worker = GrblWorker()
    events = []
    worker.connected.connect(lambda d: events.append(("connected", d)))
    worker.disconnected.connect(lambda r: events.append(("disconnected", r)))
    worker.stream_finished.connect(
        lambda ok, msg: events.append(("finished", ok, msg)))
    worker.status.connect(lambda st: events.append(("status", st)))
    worker.alarm.connect(lambda a: events.append(("alarm", a)))
    return worker, events


def pump(worker, n=50):
    for _ in range(n):
        worker.step()


def test_connect_and_banner():
    worker, events = make_worker()
    worker.commands.put(("connect", SimTransport()))
    pump(worker)
    assert ("connected", "simulator") in events


def test_stream_completes():
    worker, events = make_worker()
    sim = SimTransport()
    worker.commands.put(("connect", sim))
    worker.commands.put(("stream", ["G0 X0.25 Z0.04", "G1 Z-0.75 F3",
                                    "G0 X0.29", "M2"]))
    pump(worker)
    assert ("finished", True, "program complete") in events
    assert sim.pos["Z"] == -0.75


def test_stream_error_aborts():
    worker, events = make_worker()
    sim = SimTransport(error_on=lambda l: 20 if b"G1" in l else None)
    worker.commands.put(("connect", sim))
    worker.commands.put(("stream", ["G0 X0.25", "G1 Z-0.75 F3", "G0 X0.29"]))
    pump(worker)
    finished = [e for e in events if e[0] == "finished"]
    assert len(finished) == 1
    ok, msg = finished[0][1], finished[0][2]
    assert not ok
    assert "error:20" in msg and "G1 Z-0.75" in msg
    # the line after the failing one was never sent
    assert sim.pos["X"] == 0.25


def test_status_polling_and_parse():
    worker, events = make_worker()
    worker.commands.put(("connect", SimTransport()))
    worker._last_poll = 0.0   # force an immediate poll
    pump(worker)
    statuses = [e[1] for e in events if e[0] == "status"]
    assert statuses and statuses[-1]["state"] == "Idle"
    assert statuses[-1]["MPos"] == [0.0, 0.0, 0.0]


def test_hold_and_resume_realtime():
    worker, events = make_worker()
    sim = SimTransport()
    worker.commands.put(("connect", sim))
    pump(worker)
    worker.commands.put(("realtime", b"!"))
    pump(worker, 5)
    assert sim.state == "Hold:0"
    worker.commands.put(("realtime", b"~"))
    pump(worker, 5)
    assert sim.state == "Idle"


def test_soft_reset_kills_stream():
    worker, events = make_worker()
    # ack_delay so the stream is still in flight when we reset
    sim = SimTransport(ack_delay=10.0)

    # avoid actually sleeping 10 s: patch the sim to never ack
    sim.ack_delay = 0.0
    sim._handle_line = lambda line: None

    worker.commands.put(("connect", sim))
    worker.commands.put(("stream", ["G1 Z-1 F3", "G0 Z0"]))
    pump(worker, 5)
    worker.commands.put(("realtime", b"\x18"))
    pump(worker, 5)
    finished = [e for e in events if e[0] == "finished"]
    assert finished == [("finished", False, "stopped by soft reset")]


def test_parse_status_full_report():
    st = parse_status("<Run|MPos:0.100,0.000,-0.500|FS:3.0,600>")
    assert st["state"] == "Run"
    assert st["MPos"] == [0.1, 0.0, -0.5]
    assert st["rpm"] == 600

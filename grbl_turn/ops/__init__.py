"""Operation registry, in launcher-grid order (2 rows x 4 columns)."""

from grbl_turn.ops import boring, facing, parting, taper, threading_op, turning

REGISTRY = [
    # row 0: external operations
    threading_op.OP_EXT, taper.OP_EXT, turning.OP, facing.OP,
    # row 1: internal operations + parting
    threading_op.OP_INT, taper.OP_INT, boring.OP, parting.OP,
]

BY_KEY = {op.key: op for op in REGISTRY}

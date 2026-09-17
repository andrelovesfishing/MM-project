# 3. The quoter is built from optional components

**Decision:** `ASQuoter` takes `inventory_skew`, `size_skew` and `ofi_guard` as component objects, each `None` when off. Anything the engine calls only needs `quote(market, i, inventory)` and `inventory_limit`.

**Why:**
- The old version toggled features with `use_*` flags checked inside one long pricing block. Each flag made that block harder to read.
- An ablation is now `replace(quoter, ofi_guard=None)`, and each component is tested on its own.
- A new idea (e.g. OFI as a price skew) is a new component or a new `Strategy`, not another branch in shared code.

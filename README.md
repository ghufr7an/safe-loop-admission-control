# SAFE-LOOP: Freshness-Aware Network Admission Control
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.23651714.svg)](https://doi.org/10.5281/zenodo.23651714)

**An emulation-based evaluation of refresh-and-revalidate admission, in-process reservations, and Open vSwitch enforcement.**

> **Research status:** Experimental prototype and supporting artifacts. Journal submission and peer-review status should be confirmed separately. This repository is **not** evidence of IEEE publication or production deployment.

## Research question

What happens when network admission decisions rely on stale capacity observations? Stale information may allow requests that contribute to overload; rejecting every request with stale information can unnecessarily deny feasible traffic. SAFE-LOOP investigates a refresh-and-revalidate alternative under controlled conditions.

## Contributions and scope

- A Python **single-process** admission coordinator (`controller.py`) using an `RLock` to coordinate reservations.
- A **configured-capacity refresh callback**, rather than measured real-time available bandwidth.
- A Mininet/Open vSwitch experiment (`integrated.py`) with drop-flow enforcement for denied candidates.
- Four compared admission policies: independent, stale capacity-only, freshness guard, and SAFE-LOOP.
- Four load/freshness scenarios, with five repetitions per policy/scenario cell (**80 trials**).
- Trial-level JSON and CSV outputs included for independent inspection.

## Experimental findings (reported in supplied artifacts)

| Scenario | Comparison | Reported outcome |
|---|---|---|
| Stale underload | SAFE-LOOP vs freshness guard | 5/5 candidate admissions vs 0/5 |
| Stale overload | SAFE-LOOP vs stale capacity-only | 0/5 candidate admissions vs 5/5 |
| Stale overload | Background packet loss | SAFE-LOOP: 0%; stale capacity-only: 14.603% mean |

**Interpretation:** These observations describe the specific emulated scenarios, not general production-network effectiveness. Some reported nominal-window payload rates require additional cross-checking against receiver timing and network counters before making strong throughput claims.

## Files

```text
controller.py                    In-process admission coordinator
integrated.py                    Mininet/OVS experiment runner
results_full/summary.csv        Full-run trial-level summary
results_full/*.json             Full-run trial records and metadata
diagnostic/summary.csv          Short diagnostic-run summary
diagnostic/*.json               Diagnostic trial records
docs/ORIGINAL_EXPERIMENT_README.md  Original run notes
```

## Environment and reproduction

The experiment is intended for **Linux/Ubuntu** with Python 3, Mininet, Open vSwitch, and TCLink. It requires administrative privileges and should run only in an isolated test VM.

```bash
sudo mn -c
sudo /usr/bin/python3 integrated.py --repeats 1 --seconds 5 --output diagnostic_new
sudo mn -c
sudo /usr/bin/python3 integrated.py --repeats 5 --seconds 15 --output results_new
```

The first command runs a short diagnostic. The second requests a full 80-trial run. **These commands have not been independently executed or validated in this preparation environment.** Compare any new outputs with the included records and document differences rather than overwriting the supplied evidence.

## Methodological limitations

1. Capacity refresh reads configured link capacity; it does **not** implement independent live utilization/available-bandwidth telemetry.
2. Reservation synchronization is **in-process**; no distributed coordination, consensus, or multi-controller guarantees are demonstrated.
3. Evaluation is **Mininet/OVS emulation**, not a live operator deployment or 5G/6G system.
4. Decision timing excludes topology creation and OVS rule installation; application throughput uses a nominal sender window.
5. Results should not be generalized beyond the evaluated scenarios without further testing.

## Authors and attribution

Research manuscript: **Ghufran Shakeel and Hammad Tayyab**. The public release and license should be reviewed and approved by all relevant rights holders.

## Citation

A formal manuscript/preprint DOI is **not yet provided here**. When an approved preprint or article is publicly available, add its verified citation and DOI. Until then, cite the repository URL and an immutable commit or release tag.

## License

The repository was initialized with an MIT license on GitHub. Confirm that all included source files are owned or appropriately licensed for MIT distribution before publication.

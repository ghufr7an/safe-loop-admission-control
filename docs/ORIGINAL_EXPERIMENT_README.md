# SAFE-LOOP: integrated Mininet / Open vSwitch evaluation

Requires Ubuntu with Mininet, Open vSwitch, TCLink and Python 3; run as root. The code was syntax-checked, but has **not** been run in your Ubuntu VM. First run one short repetition to verify OVS behavior.

```
cd ~/research/safe-loop/SAFE_LOOP_integrated
sudo mn -c
sudo /usr/bin/python3 integrated.py --repeats 1 --seconds 5 --output diagnostic
sudo mn -c
sudo /usr/bin/python3 integrated.py --repeats 5 --seconds 15 --output results_full
```

This is real packet delivery within a Mininet emulation. It does not include an actual 5G RAN, 5G core, or 6G network. SAFE-LOOP refresh uses **configured capacity**, not measured available bandwidth; the OVS flow rule enforces denial. The coordinator runs in one process and provides in-process locking, not distributed consensus. Candidate packets are generated even when admission is denied, so OVS drop counters and receiver counts can confirm enforcement. Application-layer payload throughput is calculated from received bytes divided by the nominal sender duration, and loss from sender/receiver packet counts; timing/receiver window and scheduling must be considered when interpreting results. Decision times exclude topology creation and OVS rule installation. Compare throughput and admission fairness, not only loss. Tests are randomized in a deterministic order.

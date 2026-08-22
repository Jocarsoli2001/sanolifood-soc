# ADR-006: Suricata as a containerized edge IDS sensor

## Status

Accepted for SOC increment v0.5.0.

## Context

SanoliFood exposes Nginx through the Ubuntu VM address and port 8080. The
Docker DMZ bridge contains only Nginx, but observing only that bridge would
hide probes aimed at other published services of the simulated corporate host.
The bridge identifier also changes whenever Docker recreates the network.

## Decision

Run one pinned Suricata container with host networking and the capabilities
`NET_ADMIN`, `NET_RAW`, and `SYS_NICE`. A bootstrap script discovers the
default-route interface and the current VM IPv4 address. The sensor operates
only in IDS mode; it cannot drop or modify packets.

The generated EVE JSON log is persisted in the named volume
`sanolifood_suricata_logs`. Wazuh mounts the same volume read-only and parses
the single-line JSON events using its standard Suricata rules plus SanoliFood
child rules.

## Consequences

- External reconnaissance and traffic to published services are observable.
- Interface names and DHCP addresses are not hard-coded in Git.
- Live validation must originate from another machine, such as Windows or
  Kali, because loopback traffic does not cross the monitored interface.
- The container is capped at 1 GiB RAM and 1.5 CPUs for the available host.
- Visibility is limited to traffic received or transmitted by this VM; a full
  network TAP or virtual switch mirror remains a future enhancement.

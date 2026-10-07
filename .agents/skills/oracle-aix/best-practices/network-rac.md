# Oracle on Power: Network and RAC Configuration on AIX

> **Read this file for:** public network and RAC interconnect settings on AIX,
> `no` and interface-specific (ISNO) tunables, UDP buffers, ephemeral ports, jumbo
> frames, HAIP vs EtherChannel, consistent interface names (`rendev`), the PowerVS
> IPv6 interface-order issue, TCP fast loopback, and RAC-related AIX APARs.
> **Source:** IBM Power Systems VUG May 2024 (Ralf Schmidt-Dannert, IBM ATG), the
> Oracle Grid Infrastructure installation guide for AIX, and MOS 811293.1.
> **Before changing any `no` tunable**, check it with `no -L <tunable>`. Use `-p`
> for persistent changes and `-r` for reboot-type tunables.

---

## 1. Global `no` vs Interface-Specific Options (ISNO)

With `use_isno=1` (the default), the values set on each interface (`enX`)
**override** the global `no` values for `tcp_sendspace`, `tcp_recvspace`,
`rfc1323`, `tcp_nodelay`, and `tcp_mssdflt`. Changing only `no -o` may have no
effect.

```bash
no -L use_isno
ifconfig en0                 # shows the ISNO values in effect on the interface
lsattr -El en0 -a tcp_sendspace -a tcp_recvspace -a rfc1323 -a tcp_nodelay
```

---

## 2. Public Network (TCP)

```bash
# Set on each Oracle interface (persistent in the ODM, takes effect immediately)
chdev -l en0 -a tcp_sendspace=262144 -a tcp_recvspace=262144 -a rfc1323=1 -a tcp_nodelay=1

# Global defaults (used where the interface has no ISNO value)
no -p -o tcp_sendspace=262144
no -p -o tcp_recvspace=262144
no -p -o rfc1323=1

no -L sb_max        # send/recv spaces must be below sb_max (default 1048576)
```

### Ephemeral ports

Oracle's installer checks the ephemeral port range:

```bash
no -p -o tcp_ephemeral_low=9000 -o tcp_ephemeral_high=65500
no -p -o udp_ephemeral_low=9000 -o udp_ephemeral_high=65500
no -a | grep ephemeral
```

### TCP fast loopback (client and database in the same LPAR)

```bash
no -L tcp_fastlo
no -p -o tcp_fastlo=1
```

On old levels, check for the memory-leak APARs IV67463 (AIX 6.1 TL9) and IV66228
(AIX 7.1 TL3).

---

## 3. RAC Private Interconnect (UDP)

```bash
no -p -o udp_sendspace=65536
no -p -o udp_recvspace=655360        # 10 x udp_sendspace, must be < sb_max
no -a | grep -E "udp_sendspace|udp_recvspace|sb_max"

netstat -s | grep -i "socket buffer overflows"   # growing count -> raise udp_recvspace
```

### Jumbo frames (only if every switch port on the path supports them)

```bash
lsattr -El ent1 -a jumbo_frames
# Changing the adapter needs its interface down. -P applies the change at the next reboot.
# Do this in a change window, on one node at a time.
chdev -l ent1 -a jumbo_frames=yes -P
chdev -l en1 -a mtu=9000 -P
```

After the change, test end to end with large packets. Use `ping -s 8972` with the
don't-fragment option for your AIX level (see `man ping`), or Oracle `cluvfy`.

### HAIP vs EtherChannel / NIB

| Option | Use | Notes |
|---|---|---|
| **HAIP** (Oracle Redundant Interconnect) | Active-active interconnect over several private interfaces | Native to Oracle and managed by Clusterware. No switch configuration needed |
| **LACP** (802.3ad EtherChannel) | Higher bandwidth plus HA | Needs switch support |
| **NIB** (Network Interface Backup) | Active-passive failover | Simple; no added bandwidth |

```bash
oifcfg getif                                         # interfaces marked cluster_interconnect
crsctl stat res ora.cluster_interconnect.haip -init  # HAIP resource state (as grid or root)
ifconfig -a | grep 169.254                           # HAIP link-local addresses

lsdev -Cc adapter | grep ent
entstat -d ent2 | more          # EtherChannel / NIB status (use the entX of the EtherChannel)
```

---

## 4. Consistent Interface Names Across RAC Nodes

Every RAC node must use the **same interface name for the same network role**
(public, private). Use `rendev` to align names. Each network device has three
objects that must be renamed consistently: the adapter `entN`, the interface
`enN`, and the 802.3 interface `etN`.

This disrupts the network, so do it from the console or HMC terminal in a change
window, before Grid Infrastructure is configured, or with the stack stopped:

```bash
ifconfig en5 down detach          # the interface must not be in use
rendev -l ent5 -n ent2            # target names must not already exist
rendev -l en5  -n en2
rendev -l et5  -n et2
cfgmgr
lsdev -Cc adapter | grep ent; lsdev -Cc if
```

Configure the IP address again afterwards (`smitty chinet` or `mktcpip`), then
check it with `ifconfig -a`.

### PowerVS: IPv6 or unaddressed interfaces detected first

**Symptom:** the RAC installer or `cluvfy` picks up IPv6-only or unaddressed
management interfaces that come before the intended IPv4 interfaces. This can
happen even when those interfaces are excluded explicitly.

**Fix:** use the `rendev` procedure above, so the RAC public and private IPv4
interfaces come first (`en0`, `en1`, and so on). Specifying the interfaces
explicitly during installation is a weaker workaround.

```bash
ifconfig -a | grep -E "^en|inet "
```

---

## 5. Name Resolution and Time Synchronisation

- **Name resolution:** slow DNS lookups add latency to every new connection. Look
  in `/etc/hosts` first, and on IPv4-only networks skip AAAA lookups:

```bash
grep -i '^hosts' /etc/netsvc.conf     # e.g.  hosts = local, bind4
```

- **Time:** RAC needs synchronised clocks and NTP in slewing mode (`xntpd -x`).
  The setup is in `os-prereqs.md` §8.

---

## 6. Large Send Offload and Other Adapter Features

```bash
entstat -d ent0 | grep -i -E "large send|checksum|jumbo"
lsattr -El ent0 | grep -i -E "large_send|chksum|flow_ctrl"
```

The settings depend on the adapter type (physical, SEA, vNIC, SR-IOV). Follow
IBM's documentation for your adapter and VIOS level.

---

## 7. Other Settings in the Source (verify before use)

The source also lists the tunables below. Their names and types vary by AIX
level, so **check each one exists with `no -L <name>` / `schedo -L <name>` before
recommending it**:

| Setting | Source claim | Check |
|---|---|---|
| `rtentry_lock_complex` | 1 (default on AIX 7.x). A reboot tunable | `no -L rtentry_lock_complex` |
| `flexctl_latency` | "boost" for 25 Gb flex adapters on a latency-sensitive interconnect | `schedo -L flexctl_latency` |

---

## 8. RAC-Related AIX APARs

**Confirm the details on IBM Fix Central / FLRT** for the exact level.

| Issue | Affected | Fix |
|---|---|---|
| IP multicast registration failure breaks the RAC heartbeat (APAR IJ50588) | AIX 7300-01-00 to 7300-01-04 (`bos.net.tcp.client_core`) | 7300-01-04-2420 or later |
| `vmo` output format change breaks `cluvfy` parsing (APAR IJ38518) | AIX 7.3 below 7300-00-02 | 7300-00-02 or later |

```bash
oslevel -s
instfix -ik IJ50588
```

---

## References

- Oracle Grid Infrastructure installation guide for AIX (19c): https://docs.oracle.com/en/database/oracle/oracle-database/19/cwaix/
- AIX interface-specific network options: https://www.ibm.com/docs/en/aix/7.3?topic=interfaces-interface-specific-network-options
- MOS 811293.1 (RAC and Clusterware best practices), MOS 1949615.1 (RAC interconnect monitoring)
- IBM: Oracle Database 19c and RAC on AIX, tips and considerations: https://www.ibm.com/support/pages/node/6355761

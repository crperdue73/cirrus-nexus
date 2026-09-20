# Lab 3 — Lock It Down 🔒🌐

## Objective
Configure SSH on the router, port security on the switch, and deploy IPv4/IPv6 dual-stack. This is the **dress rehearsal** for the capstone.

## Topology
```
[PC-B] ─── [RTR eth1]
               [RTR eth2] ─── [SW1] ─── [PC-A]
```

- **RTR** = FRR router (vtysh) with SSH access
- **SW1** = FRR-based switch with bridge (vtysh) + port security
- **PC-A** = Alpine Linux, behind SW1 (Subnet A)
- **PC-B** = Alpine Linux, directly on RTR (Subnet B)

## Warm-Up: Subnetting Exercise

Your network is **192.168.12.0/24**. You need to divide it into two subnets:

| Subnet | Needs to support | Minimum prefix |
|---|---|---|
| Subnet A (PC-A side) | 63 hosts | /25 (126 usable) |
| Subnet B (PC-B side) | 10 hosts | /28 (14 usable) |

**Your task:** Determine the network address, first usable, last usable, and broadcast for each subnet.

| Subnet | Network | First Host | Last Host | Broadcast |
|---|---|---|---|---|
| A (/25) | 192.168.12.0 | .1 | .126 | .127 |
| B (/28) | 192.168.12.128 | .129 | .142 | .143 |

*Remember: .0 is the network address, .255 is the broadcast for /24, but once subnetted, each subnet has its own network and broadcast.*

## IP Scheme

| Device | Interface | IPv4 | IPv6 (SLAAC prefix) |
|---|---|---|---|
| RTR | eth1 (to PC-B) | 192.168.12.129/28 | 2001:db8:1::1/64 |
| RTR | eth2 (to SW1) | 192.168.12.1/25 | 2001:db8:2::1/64 |
| SW1 | br0 (SVI) | 192.168.12.2/25 | 2001:db8:2::2/64 |
| PC-A | eth1 | 192.168.12.10/25 | SLAAC (from RA) |
| PC-B | eth1 | 192.168.12.138/28 | SLAAC (from RA) |

## New Concepts

| Concept | What it means |
|---|---|
| **SSH** | Encrypted remote access — replaces insecure Telnet |
| **Port security** | Limit which MAC addresses can connect to a switch port |
| **IPv6 SLAAC** | Stateless Address Autoconfiguration — a host generates its own IPv6 address from a router advertisement |
| **Dual-stack** | Running IPv4 and IPv6 on the same network — both work simultaneously |
| **Router Advertisement** | The router periodically announces the IPv6 prefix, enabling SLAAC |

## Step-by-Step

### Part 1: Subnet the Network

Before touching any devices, confirm your subnet boundaries. This is a real-world skill — you plan the IP scheme before you configure anything.

The answers from the warm-up table above give you the IPv4 plan. Write them down — you'll use them in every part of this lab.

### Part 2: Configure RTR — Router

Open the terminal for **RTR** and enter vtysh:

```bash
vtysh
configure terminal

# Basic config
hostname RTR
enable secret cisco
banner motd line
Unauthorized Access Prohibited
end

# Configure FRR's VTY access (controls who can reach FRR's CLI)
configure terminal
username admin privilege 15 password cisco
line vty
 transport ssh
 login local
 exit

# Create a local user for Linux-level SSH access
# (this is done separately from vtysh — SSH uses Linux PAM)
exit
write memory
```

Configure both interfaces with IPv4 **and** IPv6:

```bash
configure terminal
interface eth1
 ip address 192.168.12.129/28
 ipv6 enable
 ipv6 address 2001:db8:1::1/64
 no shutdown
 description Link to PC-B (Subnet B)
exit

interface eth2
 ip address 192.168.12.1/25
 ipv6 enable
 ipv6 address 2001:db8:2::1/64
 no shutdown
 description Link to SW1 (Subnet A)
exit

# Enable IPv6 routing
ipv6 unicast-routing
exit
write memory
```

From the Linux shell, create a user for SSH and start the daemon:

```bash
# Create a Linux user for SSH access (sshd was installed in YAML exec)
adduser -D admin
# Set the password (needed for SSH password auth)
echo "admin:cisco" | chpasswd

# Start the SSH daemon
sshd
```

Verify SSH is listening:
```bash
netstat -tlnp | grep 22
```

You should see `sshd` listening on port 22.

### Part 3: Configure SW1 — Switch

Open the terminal for **SW1** and enter vtysh:

```bash
vtysh
configure terminal

# Basic config
hostname SW1
enable secret cisco
banner motd line
Unauthorized Access Prohibited
end

# Configure SVI (management IP)
configure terminal
interface br0
 ip address 192.168.12.2/25
 ipv6 enable
 ipv6 address 2001:db8:2::2/64
 no shutdown
 description Management SVI
 exit
exit
write memory
```

Set the switch's default gateway from the Linux shell:
```bash
ip route add default via 192.168.12.1
```

Now configure **port security** — in this lab, that means disabling unused switch ports:

SW1 has 6 interfaces (eth1–eth6). Only eth1 (uplink to RTR) and eth2 (to PC-A) should be active. The rest are **unused** and must be shut down.

```bash
vtysh
configure terminal

interface eth3
 shutdown
 description ** UNUSED PORT **
 exit

interface eth4
 shutdown
 description ** UNUSED PORT **
 exit

interface eth5
 shutdown
 description ** UNUSED PORT **
 exit

interface eth6
 shutdown
 description ** UNUSED PORT **
 exit
exit

# Save
write memory
```

This is a real-world security practice: **disable every port you're not using.** An attacker can't connect to a port that's shut down.

Verify:
```bash
show ip interface brief
```

eth3–eth6 should show as **down** (shutdown). Only eth1 and eth2 (the bridge ports) should be up.

### Part 4: Configure PC-A

Open the terminal for **PC-A**:

```bash
# IPv4
ip addr add 192.168.12.10/25 dev eth1
ip link set eth1 up
ip route add default via 192.168.12.1

# IPv6 — SLAAC happens automatically when RTR sends Router Advertisements
# Check your SLAAC-assigned address:
ip -6 addr show eth1
```

### Part 5: Configure PC-B

Open the terminal for **PC-B**:

```bash
# IPv4
ip addr add 192.168.12.138/28 dev eth1
ip link set eth1 up
ip route add default via 192.168.12.129

# IPv6 — SLAAC
ip -6 addr show eth1
```

### Part 6: Verify End-to-End

#### IPv4 Connectivity

```bash
# From PC-A
ping -c 4 192.168.12.1      # Ping default gateway (RTR eth2)
ping -c 4 192.168.12.138    # Ping PC-B (across RTR)

# From PC-B
ping -c 4 192.168.12.10     # Ping PC-A (through SW1 + RTR)
ping -c 4 192.168.12.1      # Ping RTR eth2
```

#### IPv6 Connectivity

```bash
# From PC-A — find your SLAAC address first
ip -6 addr show eth1 | grep "2001:db8:2:"

# Ping RTR's IPv6 gateway
ping6 -c 4 2001:db8:2::1

# Ping PC-B's IPv6 address
ping6 -c 4 2001:db8:1::<pc-b-slaac>

# From PC-B
ping6 -c 4 2001:db8:2::1     # Ping RTR eth2 IPv6
ping6 -c 4 2001:db8:2::10    # Ping PC-A IPv6 (through RTR + SW1)
```

#### SSH Verification

From **PC-A**, SSH to RTR's Linux shell:

```bash
ssh admin@192.168.12.1
# Password: cisco
```

Expected: you get a **bash shell** on RTR. You're now connected via encrypted SSH to the Linux container running FRR.

From the SSH session, enter vtysh:

```bash
vtysh
```

You're now in the FRR CLI. This is a **two-layer access model**:
- **Layer 1:** Linux sshd → gives you a bash shell
- **Layer 2:** vtysh → gives you the FRR routing CLI

From **PC-B**, SSH to RTR's other interface:

```bash
ssh admin@192.168.12.129
# Password: cisco
```

Same result — RTR is reachable via SSH from both subnets. This proves SSH access works regardless of which path the traffic takes.

### Part 7: Verify Port Security

From **SW1**, check the bridge port status:

```bash
bridge fdb show br br0
```

You should see the MAC address of PC-A on port eth2 and the MAC of RTR on port eth1. Port security prevents new devices from connecting to eth2 without admin intervention.

## Verification Checklist

| Check | Command | Expected |
|---|---|---|
| RTR has IPv4 routes | `show ip route` | Connected routes for both subnets |
| RTR has IPv6 routes | `show ipv6 route` | Connected routes for both prefixes |
| SW1 is reachable | `ping 192.168.12.2` | From RTR or PC-A |
| PC-A → PC-B (IPv4) | `ping -c 4 192.168.12.138` | Replies |
| PC-A → PC-B (IPv6) | `ping6 -c 4 2001:db8:1::...` | Replies |
| SSH to RTR | `ssh admin@192.168.12.1` | Connects, shows MOTD |
| Port security active | `bridge fdb show` | MACs locked on correct ports |

## What You Just Learned

- **SSH** replaces telnet for secure remote device management
- **Port security** restricts which devices can connect to a switch port
- **IPv6 SLAAC** lets hosts auto-configure addresses from router advertisements
- **Dual-stack** means both IP versions work simultaneously on the same network
- A **subnetting plan** comes first — IP allocation happens after the plan

## Common Pitfalls

| Mistake | How to fix |
|---|---|
| IPv6 ping fails | Check `ipv6 unicast-routing` is enabled on RTR |
| SSH connection refused | Make sure sshd is running: `netstat -tlnp \| grep 22` |
| SLAAC address not assigned | Wait 10s or restart eth1, check `accept_ra=1` |
| Can't reach PC-A from PC-B | Check SW1 bridge has both ports attached to br0 |
| Subnet mask mismatch | Verify PCs use /25 (Subnet A) or /28 (Subnet B) correctly |

## Next Lab

You're ready for the **Net Eng I Capstone**. Same topology, same skills — but this time it counts. 70/100 to pass, 90 minutes.

Good luck. 🐞💍

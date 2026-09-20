# Lab 2 — The Switch in the Middle 🖥️🔗🖧🔀🖥️

## Objective
Add a **switch** between the router and one PC. Learn how traffic crosses Layer 2 (switching) before reaching Layer 3 (routing).

## Topology
```
[PC-A] ─── [SW1] ─── [RTR] ─── [PC-B]
```

- **RTR** = FRR router (vtysh CLI)
- **SW1** = FRR-based switch with Linux bridge (vtysh CLI, same as the router)
- **PC-A** = Alpine Linux, connected to SW1
- **PC-B** = Alpine Linux, directly connected to RTR

## IP Scheme

| Device | Interface | IP Address | Subnet |
|---|---|---|---|
| RTR | eth1 (to PC-B) | 10.0.2.1/24 | Subnet B |
| RTR | eth2 (to SW1) | 10.0.1.1/24 | Subnet A |
| SW1 | bridge br0 (SVI) | 10.0.1.2/24 | Subnet A (mgmt) |
| PC-A | eth1 | 10.0.1.10/24 | Subnet A |
| PC-B | eth1 | 10.0.2.10/24 | Subnet B |

## New Concepts

| Concept | What it means |
|---|---|
| **Layer 2 switching** | Forwarding frames based on MAC addresses — no IP routing involved |
| **Bridge** | A Linux bridge acts like a physical switch. It learns which MAC is on which port. |
| **SVI (Switch Virtual Interface)** | An IP address on the switch itself so you can manage it |
| **Path traversal** | PC-A → SW1 (L2) → RTR (L3 routing) → PC-B — your traffic crosses both layers |

## Step-by-Step

### Part 1: Configure RTR (Router)

Open the terminal for **RTR** and enter vtysh:

```bash
vtysh
configure terminal
hostname RTR
enable secret cisco
banner motd line
Unauthorized Access Prohibited
end
```

Configure both interfaces:

```bash
interface eth1
 ip address 10.0.2.1/24
 no shutdown
 description Link to PC-B (Subnet B)
exit

interface eth2
 ip address 10.0.1.1/24
 no shutdown
 description Link to SW1 (Subnet A)
exit

exit
write memory
```

Verify:
```bash
show ip interface brief
show ip route
```

You should see two connected routes — one for each subnet.

### Part 2: Configure SW1 (Switch)

Open the terminal for **SW1**. The bridge (`br0`) and port attachments are pre-configured. Your job: configure the switch itself via vtysh.

```bash
# Enter the switch CLI (same vtysh as the router)
vtysh
configure terminal

# Give the switch a name
hostname SW1

# Set a MOTD banner
banner motd line
Unauthorized Access Prohibited
end

# Set password security
enable secret cisco
exit
```

Now configure the **SVI (Switch Virtual Interface)** — the management IP for the switch:

```bash
configure terminal
interface br0
 ip address 10.0.1.2/24
 no shutdown
 description Management SVI
 exit
exit

# Save config
write memory
```

Set the switch's default gateway from the Linux shell so it can reach other networks:
```bash
ip route add default via 10.0.1.1
```

Verify the bridge:
```bash
bridge fdb show
```

This shows the switch's **MAC address table** — it learns which MAC address lives on which port. Before any traffic flows, it may be empty. After pings, you'll see MACs appear.

### Part 3: Configure PC-A

Open the terminal for **PC-A**:

```bash
ip addr add 10.0.1.10/24 dev eth1
ip link set eth1 up
ip route add default via 10.0.1.1
```

### Part 4: Configure PC-B

Open the terminal for **PC-B**:

```bash
ip addr add 10.0.2.10/24 dev eth1
ip link set eth1 up
ip route add default via 10.0.2.1
```

### Part 5: Verify Step-by-Step

#### Step 1: PC-A can reach its default gateway

```bash
# From PC-A
ping -c 4 10.0.1.1
```

This ping goes: **PC-A → SW1 (L2 bridge) → RTR eth2**. The switch forwards the Ethernet frame. RTR receives it on eth2 and replies. This proves PC-A can reach the router through the switch.

#### Step 2: PC-A → PC-B — the full path

Before we ping, visualize what happens at each layer:

```
MAC-level path (L2 frames):
  PC-A → eth2 of SW1 → bridged to eth1 of SW1 → RTR eth2
  Then RTR routes to a different interface:
  RTR eth1 → PC-B

IP-level path (L3 packets):
  PC-A (10.0.1.10) → RTR (10.0.1.1) → PC-B (10.0.2.10)
  (SW1 is invisible at Layer 3 — it forwards frames, not packets)
```

Now ping across the full path:

```bash
# From PC-A
ping -c 4 10.0.2.10
```

This crosses: **PC-A → SW1 (L2 bridge) → RTR eth2 → RTR routes internally → RTR eth1 → PC-B**.

The switch doesn't know 10.0.2.0/24 exists. It just forwards the Ethernet frame to RTR. RTR receives it on eth2 (10.0.1.1/24), checks the routing table, finds 10.0.2.0/24 is directly connected on eth1, and forwards the packet out eth1 to PC-B.

#### Step 3: Trace the path

```bash
# From PC-A
traceroute -n 10.0.2.10
```

You should see:
```
1  10.0.1.1     # RTR eth2 (the L3 hop — SW1 is invisible)
2  10.0.2.10    # PC-B
```

**SW1 doesn't appear.** Switches forward at Layer 2 (MAC addresses). Traceroute only counts Layer 3 hops.

#### Step 4: Verify from PC-B

```bash
# From PC-B
ping -c 4 10.0.1.10
traceroute -n 10.0.1.10
```

Works both ways — routing is symmetric.

## Optional: Watch the Switch Learn

From **SW1**, watch the MAC address table fill in:

```bash
# Before traffic
bridge fdb show

# After pinging
bridge fdb show
```

Before: empty or minimal. After: you'll see the MAC addresses of PC-A and RTR mapped to their respective bridge ports (eth2 and eth1). This is the switch learning — it watches which MAC came from which port and stores that information.

## Verification Checklist

| Check | Command | Expected |
|---|---|---|
| RTR has both subnets | `show ip route` | Two connected routes |
| SW1 has learned MACs | `bridge fdb show` | MACs on br0 ports |
| PC-A can ping gateway | `ping -c 4 10.0.1.1` | Replies |
| PC-A can ping PC-B | `ping -c 4 10.0.2.10` | Replies across subnet |
| PC-B can ping PC-A | `ping -c 4 10.0.1.10` | Replies (reverse) |
| Switch is invisible | `traceroute -n 10.0.2.10` | Only RTR then PC-B |

## What You Just Learned

- A **switch forwards at Layer 2** — MAC addresses only, no IP routing
- **Traceroute shows Layer 3 hops** — switches are invisible
- Traffic from PC-A to PC-B crosses **both L2 (switch) and L3 (router)** — they work together
- An **SVI (management IP)** lets you reach the switch for administration
- The **MAC address table** is how a switch knows which port leads to which device

## Common Pitfalls

| Mistake | How to fix |
|---|---|
| PC-A can ping RTR but not PC-B | RTR needs eth1 configured — check `show ip interface brief` |
| `ping: sendto: Network is unreachable` | PC needs a default route: `ip route add default via <gateway>` |
| Switch shows no MACs in table | Send traffic first — the table populates from actual frames |
| Can't ping the switch SVI | Verify br0 has an IP and the interface is not shutdown |

## Next Lab

Get ready for the **capstone dress rehearsal**: SSH on the router, port security on the switch, IPv4/IPv6 dual-stack, and a subnetting warm-up exercise.

# Lab 2 — Crossing Subnets 🖥️🔀🖥️

## Objective
Configure a router with **two interfaces** on different subnets, connect a PC to each, and make them talk **through** the router.

## Topology
```
[PC-A — 10.0.1.10/24] ─── [RTR] ─── [PC-B — 10.0.2.10/24]
```

- **RTR** = FRR router (uses `vtysh` for CLI — just like Cisco IOS)
- **PC-A** = Alpine Linux, connected to RTR's `eth1`
- **PC-B** = Alpine Linux, connected to RTR's `eth2`

## New Concepts

| Concept | What it means |
|---|---|
| **Default gateway** | The router's IP on your subnet. Your PC sends all "I don't know where this is" traffic here. |
| **Connected route** | A route the router knows automatically because an interface has an IP on that subnet. |
| **Multi-interface router** | A router with feet in two networks. Traffic that doesn't belong on one subnet gets forwarded to the other. |
| **Traceroute** | Shows every hop a packet takes. |

## Step-by-Step

### Part 1: Log into RTR and Enter Router CLI

```bash
# You're in the container's Linux shell. To configure the router:
vtysh
```

If it worked, your prompt changes. You're now in **router configuration mode** — the same CLI as Cisco IOS.

### Part 2: Basic Router Configuration

```bash
configure terminal

# Give the router a name
hostname RTR

# Set a welcome message (MOTD banner)
banner motd line
Unauthorized Access Prohibited
end

# Set an encrypted password for privileged mode
enable secret cisco

# Set a username/password for console/SSH access
username admin password cisco
```

Verify your config:
```bash
do show running-config
```

### Part 3: Configure Interface eth1 (to PC-A)

```bash
interface eth1
 ip address 10.0.1.1/24
 no shutdown
 description Link to PC-A
exit
```

### Part 4: Configure Interface eth2 (to PC-B)

```bash
interface eth2
 ip address 10.0.2.1/24
 no shutdown
 description Link to PC-B
exit
```

### Part 5: Save and Verify

```bash
# Save so config survives a reload
write memory

# Check your interfaces
do show ip interface brief

# Check the routing table — notice the connected routes
do show ip route
```

You should see two **connected routes** (marked `C`):
- `10.0.1.0/24` — via eth1
- `10.0.2.0/24` — via eth2

The router knows about both networks automatically because you assigned IPs to those interfaces.

### Part 6: Configure PC-A

Open the terminal for **PC-A**:

```bash
ip addr add 10.0.1.10/24 dev eth1
ip link set eth1 up
ip route add default via 10.0.1.1
```

### Part 7: Configure PC-B

Open the terminal for **PC-B**:

```bash
ip addr add 10.0.2.10/24 dev eth2
ip link set eth2 up
ip route add default via 10.0.2.1
```

### Part 8: Verify End-to-End Connectivity

From **PC-A**, ping PC-B:
```bash
ping -c 4 10.0.2.10
```

If it works — you just sent traffic from 10.0.1.0/24 to 10.0.2.0/24 **through the router**. That's routing.

Now trace the path:
```bash
traceroute -n 10.0.2.10
```

You should see:
```
1  10.0.1.1    # RTR's eth1
2  10.0.2.10   # PC-B
```

**That hop through 10.0.1.1 is the router doing its job.**

### Part 9: From PC-B, ping PC-A

```bash
ping -c 4 10.0.1.10
```

It works both ways. The router doesn't care which direction the traffic comes from — it forwards based on the routing table.

## Verification Checklist

| Check | Command | Expected |
|---|---|---|
| RTR interfaces are up | `show ip interface brief` | eth1 and eth2 both up/up |
| RTR knows both subnets | `show ip route` | Two connected routes (C) |
| PC-A can reach PC-B | `ping -c 4 10.0.2.10` | !!! replies |
| PC-B can reach PC-A | `ping -c 4 10.0.1.10` | !!! replies |
| Path crosses the router | `traceroute -n <remote-ip>` | Two hops, middle is RTR |

## What You Just Learned

- A **default gateway** points traffic toward the router when the destination isn't local
- **Connected routes** appear automatically when you assign an IP to an interface
- A **router with two interfaces** can forward traffic between two subnets without any dynamic routing protocol — the connected routes are enough
- **Traceroute** reveals the path your packets take

## Common Pitfalls

| Mistake | How to fix |
|---|---|
| Ping hangs forever | Use `ping -c 4` (Alpine's ping doesn't stop on its own) |
| `Destination unreachable` | Check PC's default gateway and router's interface config |
| `Network is unreachable` | PC needs a default route — double-check `ip route add default` |
| Can't ping the router | Make sure the PC's interface is up: `ip link set eth1 up` |

## Next Lab

Now that you've crossed subnets through a router, we'll add a **switch between the router and one PC** — introducing Layer 2 forwarding and the separation of switching from routing.

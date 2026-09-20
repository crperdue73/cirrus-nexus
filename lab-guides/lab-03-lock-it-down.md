# AEGIS — Lab 03: Lock It Down 🔒

**Duration:** 90 min | **Difficulty:** Intermediate  
**Prerequisites:** Lab 01 — Crossing Subnets, Lab 02 — The Switch in the Middle

---

## Objective

Dress rehearsal for the capstone. Configure SSH, port security, IPv6 SLAAC, and
subnetting on the same topology you've been building across Labs 1 and 2.

**Proficiency threshold:** 70/100 points

## Topology

```
[PC-B: 10.0.2.10/24] ─── [RTR: eth1 10.0.2.1/24, eth2 10.0.1.1/24]
                                     │
                                     │
                              [SW1: br0 10.0.1.2/24]
                                     │
                                     │
                              [PC-A: 10.0.1.10/24]
```

**IP scheme** (same as Labs 1 & 2 — familiarity breeds confidence):

| Device | Interface | Subnet | IPv4 Address | IPv6 Address |
|--------|-----------|--------|-------------|-------------|
| RTR    | eth1      | B      | 10.0.2.1/24 | 2001:db8:bbad:2::1/64 |
| RTR    | eth2      | A      | 10.0.1.1/24 | 2001:db8:bbad:1::1/64 |
| SW1    | br0       | A      | 10.0.1.2/24 | SLAAC |
| PC-A   | eth1      | A      | 10.0.1.10/24 | SLAAC |
| PC-B   | eth1      | B      | 10.0.2.10/24 | SLAAC |

---

## Part 1 — Subnetting Warm-Up (15 min)

Before touching the devices, work through this on paper:

**Given:** 10.0.0.0/16

1. Carve out a /24 for Lab 1 (Crossing Subnets). What's the network address?
2. From the remaining space, carve out a /24 for this lab. What's the address?
3. Split each /24 into two subnets: one for 50 hosts, one for 25 hosts.
4. Assign IPv6 ULA addresses (fd00::/8) for each subnet.

**Answers:**
1. 10.0.1.0/24 (used for Subnet A in Lab 1)
2. 10.0.2.0/24 (used for Subnet B in Lab 1)
3. Subnet A: 10.0.1.0/25 (126 hosts) — but we only need 2, so /24 is fine
4. fd00:db8:bbad:1::/64 for Subnet A, fd00:db8:bbad:2::/64 for Subnet B

---

## Part 2 — RTR: SSH & Device Security (30 min)

### Tasks

1. **Log into RTR** via browser terminal — enter `vtysh`
2. **Configure basic device settings:**
   ```
   configure terminal
   hostname RTR
   ```
3. **Set passwords:**
   ```
   enable password ncenskills
   username ncadmin password ncenskills
   service password-encryption
   exit
   ```
   
   > 💡 **Before vs. After:** Run `do show running-config | include password` before
   > and after enabling `service password-encryption`. You'll see the password
   > change from plaintext to encrypted (Type 7).

4. **Restrict VTY access:**
   ```
   line vty
    transport input ssh
    login local
    exit
   ```
5. **Set password policy:**
   ```
   security passwords min-length 8
   no ip domain-lookup
   ```
6. **Configure interfaces:**
   ```
   interface eth1
    ip address 10.0.2.1/24
    ipv6 address 2001:db8:bbad:2::1/64
    no shutdown
    exit
   interface eth2
    ip address 10.0.1.1/24
    ipv6 address 2001:db8:bbad:1::1/64
    no shutdown
    exit
   ```
7. **Enable IPv6 routing:**
   ```
   ipv6 unicast-routing
   ```
8. **Verify:**
   ```
   do show running-config
   do show ip interface brief
   do show ipv6 interface brief
   ```

### 💡 SSH Verification

From PC-A, test SSH access to RTR. The SSH daemon (sshd) is already running
on RTR — this was set up in the container's startup. Your job is to test it:

```bash
ssh ncadmin@10.0.1.1
```

First-time connection prompts for fingerprint acceptance. Type `yes`, then
enter password `ncenskills`.

If successful, you'll get a **bash shell** on RTR (not the FRR CLI). This is
because sshd operates at the Linux level, not the FRR level. From here, type
`vtysh` to enter the FRR CLI — the same interface you used in Labs 1 and 2.

```
RTR:~$ vtysh
RTR#
```

Exit with `exit` to return to bash, then `exit` again to close the SSH session.

> 🔒 **What you just did:** SSH encryption is handled by OpenSSH (Linux level).
> The VTY `transport input ssh` config controls which protocols are accepted
> on FRR's own VTY lines. Two layers, same security goal.

---

## Part 3 — SW1: Port Security & SVI (25 min)

### Tasks

1. **Log into SW1** via browser terminal — enter `vtysh`
2. **Configure basic settings:**
   ```
   configure terminal
   hostname SW1
   enable password ncenskills
   service password-encryption
   ```
3. **Configure SVI (br0):**
   ```
   interface br0
    ip address 10.0.1.2/24
    no shutdown
    exit
   ```
4. **Shut down unused ports:**
   
   Before shutting them down, check the current status of the unused ports:
   ```
   do show interface eth3
   do show interface eth4
   ```
   They should show as **up** — these are the ports you'll secure.
   
   Now shut them down:
   ```
   interface eth3
    shutdown
    exit
   interface eth4
    shutdown
    exit
   interface eth5
    shutdown
    exit
   interface eth6
    shutdown
    exit
   ```
   
5. **Verify:**
   ```
   do show interface eth3   # should now show 'administratively down'
   do show running-config | include shutdown
   ```

### 💡 Port Security Discussion

FRR doesn't have Cisco's `switchport port-security` command. In this lab,
"port security" means:

- **Shutting down unused ports** — prevents unauthorized physical access
- **Password-protecting management access** — prevents unauthorized CLI access
- **Disabling unused services** — CDP, LLDP, DNS lookup (taught conceptually)

In a production environment, you'd also use:
- 802.1X for network access control
- DHCP snooping
- Dynamic ARP inspection
- MAC address limiting

---

## Part 4 — PCs: IPv4 + IPv6 SLAAC (10 min)

### Tasks

1. **Configure PC-A:**
   ```bash
   ip addr add 10.0.1.10/24 dev eth1
   ip link set eth1 up
   ip route add default via 10.0.1.1
   ```
2. **Configure PC-B:**
   ```bash
   ip addr add 10.0.2.10/24 dev eth1
   ip link set eth1 up
   ip route add default via 10.0.2.1
   ```
3. **Verify IPv6 SLAAC:**
   ```bash
   ip -6 addr show eth1
   ```
   Look for an address starting with `2001:db8:bbad:` — that's the SLAAC-
   generated address from RTR's Router Advertisement.

---

## Part 5 — End-to-End Verification (10 min)

### Connectivity Tests

| Test | Command | Expected |
|------|---------|----------|
| PC-A → SW1 (IPv4) | `ping -c 4 10.0.1.2` | ✅ Success |
| PC-A → RTR (IPv4) | `ping -c 4 10.0.1.1` | ✅ Success |
| PC-A → PC-B (IPv4) | `ping -c 4 10.0.2.10` | ✅ Success (cross-subnet) |
| PC-B → RTR (IPv4) | `ping -c 4 10.0.2.1` | ✅ Success |
| PC-B → SW1 (IPv4) | `ping -c 4 10.0.1.2` | ✅ Success (via RTR) |
| PC-A → RTR (IPv6) | `ping -c 4 2001:db8:bbad:1::1` | ✅ Success |
| PC-B → RTR (IPv6) | `ping -c 4 2001:db8:bbad:2::1` | ✅ Success |

### Traceroute

From PC-A, trace the path to PC-B:
```bash
traceroute 10.0.2.10
```

Expected output:
```
1   10.0.1.1  (RTR)         2.5 ms
2   10.0.2.10 (PC-B)        5.1 ms
```

The switch (SW1) is invisible — it's an L2 hop. Students should recognize this
from Lab 02.

---

## Grading Rubric (100 pts)

| Component | Max Points | What's Checked |
|-----------|-----------|----------------|
| Subnetting | 15 | Address scheme, CIDR notation, host ranges |
| RTR SSH Config | 30 | hostname, domain name, RSA key, VTY transport, username |
| RTR Interface Config | 15 | eth1 + eth2 IPv4/IPv6, no shutdown |
| SW1 SVI | 15 | br0 IP, running-config |
| SW1 Port Security | 10 | eth3-eth6 shutdown |
| PC Config | 5 | PC-A and PC-B IPv4 + gateway |
| Connectivity | 10 | All 7 ping tests pass |

**💡 Tip:** This is the exact format of the capstone. Nail this lab and the
capstone is review, not a challenge.

---

## Comparison: Lab 03 vs. Capstone

| Feature | Lab 03 (Dress Rehearsal) | Capstone |
|---------|--------------------------|----------|
| IP scheme | 10.0.1.0/24, 10.0.2.0/24 | 192.168.12.0/24 |
| Subnetting | Warm-up (CIDR practice) | Full PBM worksheet |
| SSH | Configured on RTR | Configured on RTR |
| IPv6 | SLAAC on PCs | SLAAC on PCs + Neighbor Discovery |
| Port security | Unused port shutdown | Same + conceptual security |
| Grading | Instructor review | Auto-graded (100 pts) |
| Weight | Practice (low stakes) | Assessment (70% = pass) |

---

*Lab 03 — Lock It Down. Nail this, and the capstone is yours. 🐞🔒💍*

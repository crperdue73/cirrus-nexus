# Tier 03 — Router, Switch, and a PC 🖥️🔗🖧

## Objective
Configure a router connected to a switch, with a PC connected to the switch.

## Topology
```
PC-A ──── SW1 ──── R1
```

## Instructions

1. **Click into R1's terminal**
2. Configure the router:
   ```
   vtysh
   configure terminal
   hostname R1
   interface eth1
    ip address 10.0.1.1/24
    no shutdown
   end
   write memory
   ```
3. **Click into SW1's terminal**
4. Configure the switch SVI:
   ```
   ip link add name br0 type bridge
   ip link set eth1 master br0
   ip link set eth2 master br0
   ip addr add 10.0.1.254/24 dev br0
   ip link set br0 up
   ip link set eth1 up
   ip link set eth2 up
   ```
5. **Click into PC-A's terminal**
6. Configure PC-A:
   ```
   ip addr add 10.0.1.100/24 dev eth1
   ip link set eth1 up
   ip route add default via 10.0.1.254
   ```
7. Verify:
   ```
   ping 10.0.1.1
   traceroute 10.0.1.1
   ```

## Tips
- The switch uses Linux bridging, not FRR
- Check bridge status with `bridge link show`

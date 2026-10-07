# Router Basics — Configure Your First Router 🖥️🔧

## Objective
Log into an FRR router via vtysh and configure hostname, passwords, and an interface IP.

## Topology
```
PC-A ──── R1
```

## Instructions

1. **Click into R1's terminal**
2. Enter vtysh:
   ```
   vtysh
   ```
3. Enter configuration mode:
   ```
   configure terminal
   ```
4. Set the hostname:
   ```
   hostname R1
   ```
5. Set enable password:
   ```
   enable password cisco
   service password-encryption
   ```
6. Configure the interface facing PC-A:
   ```
   interface eth1
    ip address 10.0.1.1/24
    no shutdown
   ```
7. Exit and verify:
   ```
   end
   show running-config
   ```
8. **Click into PC-A's terminal**
9. Configure PC-A:
   ```
   ip addr add 10.0.1.2/24 dev eth1
   ip link set eth1 up
   ip route add default via 10.0.1.1
   ```
10. Verify connectivity:
    ```
    ping 10.0.1.1
    ```

## Tips
- Use `show running-config` to verify your router settings
- Remember `no shutdown` to bring interfaces up in FRR
- PC needs a default gateway to reach the router

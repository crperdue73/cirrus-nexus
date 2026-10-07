# Foundation — Make Two Computers Talk 🖥️🖥️

## Objective
Assign IP addresses to two computers connected through a switch, then verify they can communicate.

## Topology
```
PC-A ──── switch ──── PC-B
```

## Instructions

1. **Click into the terminal for PC-A**
2. Assign IP 10.0.1.1/24 on eth1:
   ```
   ip addr add 10.0.1.1/24 dev eth1
   ip link set eth1 up
   ```
3. **Click into the terminal for PC-B**
4. Assign IP 10.0.1.2/24 on eth1:
   ```
   ip addr add 10.0.1.2/24 dev eth1
   ip link set eth1 up
   ```
5. **From PC-A**, ping PC-B:
   ```
   ping 10.0.1.2
   ```

## Verification
- `ip addr show eth1` — check your IP config
- `ping 10.0.1.2` from PC-A — should get replies

## Tips
- Use `ip addr show eth1` to verify your configuration
- If ping fails, check both interfaces are up

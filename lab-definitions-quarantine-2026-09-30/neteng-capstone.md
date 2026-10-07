# Capstone — Net Eng I Performance-Based Measurement

## Objective
Comprehensive assessment covering subnetting, device configuration, and end-to-end connectivity.

## Topology
```
PC-A ──── SW1 ──── R1 ──── SW2 ──── PC-B
```

## Tasks

1. **Subnet 192.168.12.0/24** into:
   - A /25 subnet (192.168.12.0/25)
   - A /28 subnet (192.168.12.128/28)

2. **Configure R1** in vtysh:
   - Hostname: R1
   - Interface eth1: 192.168.12.1/25
   - Interface eth2: 192.168.12.129/28
   - Enable password

3. **Configure SW1** as a bridge:
   - Bridge br0 with eth1 and eth2
   - IP: 192.168.12.2/25
   - Default gateway: 192.168.12.1

4. **Configure SW2** as a bridge:
   - Bridge br0 with eth1 and eth2
   - IP: 192.168.12.130/28
   - Default gateway: 192.168.12.129

5. **Configure PC-A**:
   - IP: 192.168.12.50/25
   - Default gateway: 192.168.12.1

6. **Configure PC-B**:
   - IP: 192.168.12.150/28
   - Default gateway: 192.168.12.129

## Grading
- 100 points total. 70+ = Proficient
- Graded automatically via API

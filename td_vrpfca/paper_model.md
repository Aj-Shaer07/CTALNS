
# TD-VRPFCA model implemented in Objective 1

Source mapping:

- Sets: `I, N, K, D, L, C, A`
- Parameters: `v_ij^l, delta_ij, t_id^l, omega_d^c, W^k, V^c, q_i, Q^k, Ll^l, Ul^l`
- Objective: `min T_MAX`
- Route/assignment/capacity constraints: paper constraints (2)-(14)
- Time propagation: paper constraints (15)-(20)
- Domains: paper constraints (21)-(22)
- Constructive time evaluation: paper Algorithm 1 / repository `Codes/Fitness.py`

The implementation keeps optimization methods separate from the evaluator.

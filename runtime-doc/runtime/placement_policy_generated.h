/* Regenerate from placement_policy.doc and compare exactly in CI. */
#define F_place_parallel(P_tasks) (v_le(vi(0x0000000000000020LL),P_tasks))
#define F_place_workers(P_tasks,P_capacity) (v_if(F_place_parallel(P_tasks),v_if(v_lt(P_capacity,v_quot(P_tasks,vi(0x0000000000000010LL))),P_capacity,v_quot(P_tasks,vi(0x0000000000000010LL))),vi(0x0000000000000001LL)))
#define F_place_device(P_mode,P_eligible,P_unsupported) (v_if(v_eq(P_mode,vi(0x0000000000000001LL)),v_if(v_eq(P_unsupported,vi(0x0000000000000000LL)),vi(0x0000000000000001LL),vi((-1LL - 0x0000000000000000LL))),v_if(v_eq(P_mode,vi(0x0000000000000002LL)),v_if(v_le(vi(0x0000000000000040LL),P_eligible),vi(0x0000000000000001LL),vi(0x0000000000000000LL)),vi(0x0000000000000000LL))))

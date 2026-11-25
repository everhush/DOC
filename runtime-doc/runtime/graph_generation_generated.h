/* Regenerated from graph_generation.doc; tested for exact equality. */
#define F_graph_admit(P_stable,P_current,P_requested) (v_if(P_stable,v_if(v_eq(P_current,P_requested),v_lt(P_current,vi(0x7fffffffffffffffLL)),vb(0)),vb(0)))
#define F_graph_source(P_role) (v_if(v_eq(P_role,vi(0x0000000000000001LL)),vb(1),v_eq(P_role,vi(0x0000000000000005LL))))
#define F_graph_carry(P_old_role,P_new_role,P_old_kind,P_new_kind,P_same_name) (v_if(P_same_name,v_if(F_graph_source(P_old_role),v_if(F_graph_source(P_new_role),v_eq(P_old_kind,P_new_kind),vb(0)),vb(0)),vb(0)))

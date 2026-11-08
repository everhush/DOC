//! Independent finite-DAG schedule checks. This is not a recurrence proof.
use doc_runtime::{Cutoff, Graph, Runtime, Value};

fn diamond() -> Graph {
    Graph::parse(
        "source a: int = 2\n\
         derive left: int (a) = add(a,1)\n\
         derive right: int (a) = mul(a,3)\n\
         derive join: int (left,right) = add(left,right)\n",
    )
    .unwrap()
}

#[test]
fn all_initial_diamond_frontier_orders_agree() {
    // A frontier may be committed together or as either singleton first.
    // These are the complete legal first-frontier partitions of this diamond.
    for schedule in [
        vec![vec![1, 2], vec![3]],
        vec![vec![1], vec![2], vec![3]],
        vec![vec![2], vec![1], vec![3]],
    ] {
        for workers in [1, 2, 4] {
            let mut runtime = Runtime::new(diamond(), workers, Cutoff::Exact);
            for frontier in &schedule {
                for &node in frontier {
                    assert!(runtime.ready().contains(&node));
                }
                runtime.step(frontier).unwrap();
            }
            assert!(runtime.stable());
            assert_eq!(runtime.value(3), Some(Value::Int(9)));
            assert_eq!(
                runtime.snapshot().into_iter().map(Option::unwrap).collect::<Vec<_>>(),
                runtime.oracle().unwrap()
            );
        }
    }
}

#[test]
fn no_premature_join_and_no_illegal_mixed_frontier() {
    for workers in [1, 2, 4] {
        let mut runtime = Runtime::new(diamond(), workers, Cutoff::Exact);
        let before = runtime.snapshot();
        assert!(runtime.step(&[1, 3]).is_err());
        assert_eq!(runtime.snapshot(), before);
        assert_eq!(runtime.ready(), vec![1, 2]);

        runtime.step(&[2]).unwrap();
        assert!(!runtime.ready().contains(&3));
        runtime.step(&[1]).unwrap();
        assert_eq!(runtime.ready(), vec![3]);
        runtime.step(&[3]).unwrap();
        assert_eq!(runtime.value(3), Some(Value::Int(9)));
    }
}

#[test]
fn repair_matches_complete_oracle_after_source_change() {
    for workers in [1, 2, 4] {
        let mut runtime = Runtime::new(diamond(), workers, Cutoff::Exact);
        runtime.stabilize().unwrap();
        for input in [-3, 0, 1, 7, 2] {
            runtime.update(&[(0, Value::Int(input))]).unwrap();
            runtime.stabilize().unwrap();
            assert!(runtime.stable());
            assert_eq!(runtime.value(3), Some(Value::Int(input * 4 + 1)));
            assert_eq!(
                runtime.snapshot().into_iter().map(Option::unwrap).collect::<Vec<_>>(),
                runtime.oracle().unwrap()
            );
        }
    }
}

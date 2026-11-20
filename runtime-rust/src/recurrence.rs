//! Forward carry between finite DOC epochs over the existing int/bool domains.

use std::collections::HashSet;

use crate::{Cutoff, Graph, Result, Runtime, StateId, Value};

/// A demand-driven sequence of stable epochs with retention of the latest one.
/// Template source literals supply defaults. The caller can supply facts for
/// uncarried sources. A failed epoch leaves the last stable epoch observable.
#[derive(Debug)]
pub struct Recurrence {
    carry: Vec<(StateId, StateId)>,
    carried_sources: HashSet<StateId>,
    current: Runtime,
    epoch: u64,
}

impl Recurrence {
    /// Each carry pair is (next epoch source, previous epoch state).
    pub fn new(
        template: Graph,
        carry: Vec<(StateId, StateId)>,
        initial_facts: &[(StateId, Value)],
        workers: usize,
    ) -> Result<Self> {
        let template = Graph::new(template.states)?;
        let mut carried_sources = HashSet::new();
        for &(source, previous) in &carry {
            let source_state = template.states.get(source).ok_or("unknown carry source")?;
            let previous_state = template.states.get(previous).ok_or("unknown carry state")?;
            if source_state.definition.is_some() || source_state.kind != previous_state.kind {
                return Err("carry requires a source of the previous state's type".into());
            }
            if !carried_sources.insert(source) {
                return Err("duplicate carry authority".into());
            }
        }
        let mut current = Runtime::new(template, workers, Cutoff::Exact);
        current.update(initial_facts)?;
        current.stabilize()?;
        Ok(Self {
            carry,
            carried_sources,
            current,
            epoch: 0,
        })
    }

    pub fn epoch(&self) -> u64 {
        self.epoch
    }

    pub fn value(&self, state: StateId) -> Option<Value> {
        self.current.value(state)
    }

    /// Demand exactly one more epoch. Facts apply only to that epoch.
    pub fn advance(&mut self, facts: &[(StateId, Value)]) -> Result<()> {
        let next = self.epoch.checked_add(1).ok_or("epoch index exhausted")?;
        if facts
            .iter()
            .any(|(source, _)| self.carried_sources.contains(source))
        {
            return Err("epoch fact conflicts with carry authority".into());
        }
        let mut changes = Vec::with_capacity(self.carry.len() + facts.len());
        for &(source, previous) in &self.carry {
            let value = self
                .current
                .value(previous)
                .ok_or("missing carried value")?;
            changes.push((source, value));
        }
        changes.extend_from_slice(facts);
        let mut candidate = Runtime::new(
            self.current.graph.clone(),
            self.current.workers,
            Cutoff::Exact,
        );
        candidate.update(&changes)?;
        candidate.stabilize()?;
        self.current = candidate;
        self.epoch = next;
        Ok(())
    }
}

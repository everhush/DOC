//! Forward carry between finite DOC epochs over the existing int/bool domains.

use std::collections::{HashSet, VecDeque};

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
    retention: usize,
    snapshots: VecDeque<(u64, Vec<Option<Value>>)>,
}

impl Recurrence {
    /// Each carry pair is (next epoch source, previous epoch state).
    pub fn new(
        template: Graph,
        carry: Vec<(StateId, StateId)>,
        initial_facts: &[(StateId, Value)],
        workers: usize,
    ) -> Result<Self> {
        Self::new_with_retention(template, carry, initial_facts, workers, 1)
    }

    /// Retain exactly the most recent `retention` stable, independently owned
    /// epoch snapshots, including the current epoch. Retention must be positive.
    /// These snapshots are copies of scalar values, not invalidatable GPU caches.
    pub fn new_with_retention(
        template: Graph,
        carry: Vec<(StateId, StateId)>,
        initial_facts: &[(StateId, Value)],
        workers: usize,
        retention: usize,
    ) -> Result<Self> {
        if retention == 0 {
            return Err("recurrence retention must be at least one epoch".into());
        }
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
        let mut snapshots = VecDeque::new();
        snapshots.push_back((0, current.snapshot()));
        Ok(Self {
            carry,
            carried_sources,
            current,
            epoch: 0,
            retention,
            snapshots,
        })
    }

    pub fn epoch(&self) -> u64 {
        self.epoch
    }

    pub fn value(&self, state: StateId) -> Option<Value> {
        self.current.value(state)
    }


    /// This returns an owned, immutable view of a retained past stable epoch.
    /// An evicted epoch is absent, never a stale or silently reconstructed value.
    pub fn snapshot_at(&self, epoch: u64) -> Option<Vec<Option<Value>>> {
        self.snapshots.iter()
            .find(|(index, _)| *index == epoch)
            .map(|(_, snapshot)| snapshot.clone())
    }

    pub fn retained_epochs(&self) -> Vec<u64> {
        self.snapshots.iter().map(|(epoch, _)| *epoch).collect()
    }

    /// Demand a finite prefix through the requested epoch (inclusive).
    /// Previously materialized epochs are never recomputed by this operation.
    pub fn demand_through(&mut self, requested: u64) -> Result<()> {
        while self.epoch < requested {
            self.advance(&[])?;
        }
        Ok(())
    }

    /// Stop at the first stable epoch whose Boolean state is true. Reaching the
    /// finite cap without halting returns false, not a universality claim.
    /// Every successful epoch is committed separately; a failed candidate does
    /// not change the current epoch or its retained history.
    pub fn advance_until(&mut self, halt_state: StateId, max_epoch: u64) -> Result<bool> {
        if self.current.graph.states.get(halt_state)
            .map(|s| s.kind) != Some(crate::Type::Bool) {
            return Err("halt predicate must name a Boolean state".into());
        }
        loop {
            if self.value(halt_state) == Some(Value::Bool(true)) {
                return Ok(true);
            }
            if self.epoch >= max_epoch {
                return Ok(false);
            }
            self.advance(&[])?;
        }
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
        let snapshot = candidate.snapshot();
        self.current = candidate;
        self.epoch = next;
        self.snapshots.push_back((next, snapshot));
        while self.snapshots.len() > self.retention {
            self.snapshots.pop_front();
        }
        Ok(())
    }
}

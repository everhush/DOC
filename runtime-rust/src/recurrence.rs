//! Forward carry between finite DOC epochs over the existing int/bool domains.

use std::collections::{BTreeMap, HashSet, VecDeque};

use crate::{automatic::{AutomaticScheduler,AutomaticStats},Cutoff, Graph, Result, Runtime, StateId, Value};

/// A demand-driven sequence of stable epochs with retention of the latest one.
/// Template source literals supply defaults. The caller can supply facts for
/// uncarried sources. A failed epoch leaves the last stable epoch observable.
#[derive(Debug)]
pub struct Recurrence {
    carry: Vec<(StateId, StateId)>,
    automatic:Option<AutomaticScheduler>,
    carried_sources: HashSet<StateId>,
    current: Runtime,
    epoch: u64,
    retention: usize,
    snapshots: VecDeque<(u64, Vec<Option<Value>>)>,
    template: Graph,
    initial_facts: Vec<(StateId,Value)>,
    // Compact authoritative *fact metadata*, not every epoch valuation.
    // No metadata entry is needed for epochs using template defaults.
    fact_log: BTreeMap<u64,Vec<(StateId,Value)>>,
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
        let original_template=template.clone();
        let original_facts=initial_facts.to_vec();
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
            automatic:None,
            carried_sources,
            current,
            epoch: 0,
            retention,
            snapshots,
            template:original_template,
            initial_facts:original_facts,
            fact_log:BTreeMap::new(),
        })
    }

    /// Select engine-owned automatic placement; DOC authored source is unchanged.
    /// This does not assert a physical GPU exists: pure CPU is always valid.
    pub fn enable_automatic(&mut self){
        self.automatic=Some(AutomaticScheduler::new());
    }
    pub fn new_automatic_with_retention(
        template:Graph,carry:Vec<(StateId,StateId)>,
        facts:&[(StateId,Value)],workers:usize,retention:usize
    )->Result<Self>{
        let mut recurrence=Self::new_with_retention(template,carry,facts,workers,retention)?;
        recurrence.enable_automatic();
        Ok(recurrence)
    }
    pub fn automatic_stats(&self)->Option<AutomaticStats>{
        self.automatic.as_ref().map(AutomaticScheduler::stats)
    }
    pub fn automatic_report(&self)->Option<String>{
        self.automatic.as_ref().map(AutomaticScheduler::report)
    }

    /// Read-only schema used to validate independently persisted source facts.
    pub fn graph(&self) -> &Graph { &self.template }

    /// Forward-carry authority is included in the checkpoint schema.
    pub fn carries(&self) -> &[(StateId,StateId)] { &self.carry }

    pub fn epoch(&self) -> u64 {
        self.epoch
    }

    pub fn value(&self, state: StateId) -> Option<Value> {
        self.current.value(state)
    }

    /// Independently owned typed source facts for the latest *stable* epoch.
    /// This is a pure checkpoint boundary: effects have already been sampled,
    /// derived values are rebuilt by DOC when restoring, and no host gameplay
    /// state or interpreter dispatch is embedded in the checkpoint.
    pub fn current_source_facts(&self) -> Result<Vec<(StateId, Value)>> {
        self.current.graph.states.iter().enumerate()
            .filter(|(_, state)| state.definition.is_none())
            .map(|(id, _)| self.current.value(id)
                .map(|value| (id, value))
                .ok_or_else(|| format!("missing stable source value for state {id}")))
            .collect()
    }

    /// Restore the current logical DOC valuation in an independent recurrence.
    /// The fork starts at epoch zero and does not copy historical epoch indices
    /// or externally performed effects. Callers may persist typed source facts
    /// separately, subject to their own explicit I/O and provenance policy.
    pub fn fork_current(&self) -> Result<Self> {
        let facts=self.current_source_facts()?;
        let mut fork=Self::new_with_retention(
            self.template.clone(),self.carry.clone(),&facts,
            self.current.workers,self.retention,
        )?;
        if self.automatic.is_some(){fork.enable_automatic();}
        Ok(fork)
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

    /// Reconstruct a logically available, formerly evicted stable epoch from
    /// its authoritative immutable template, typed forward carry and sparse
    /// epoch-local fact log. Never resurrect an uncommitted/failed epoch.
    ///
    /// The cache uses O(retention * live values) plus O(explicit facts) storage,
    /// apart from the current graph/template. A reconstruction costs up to
    /// O(requested_epoch * one-epoch evaluation), including big-number work.
    /// It returns an owned view and cannot mutate the current publication.
    pub fn reconstruct_epoch(&self,requested:u64)
        ->Result<Option<Vec<Option<Value>>>>
    {
        if requested>self.epoch {return Ok(None);}
        if let Some(cached)=self.snapshot_at(requested){return Ok(Some(cached));}
        let mut replay=Self::new_with_retention(
            self.template.clone(),self.carry.clone(),
            &self.initial_facts,self.current.workers,1
        )?;
        for epoch in 1..=requested {
            let facts=self.fact_log.get(&epoch).map(Vec::as_slice).unwrap_or(&[]);
            replay.advance(facts)?;
        }
        Ok(replay.snapshot_at(requested))
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
        self.advance_validated(facts, |_| Ok(()))
    }

    /// Admit a platform-bound projection of the private stabilized candidate
    /// before publishing any epoch, source facts or snapshot. The validator
    /// is a pure check and must not perform externally visible effects.
    pub fn advance_validated(
        &mut self, facts: &[(StateId, Value)], validate: impl FnOnce(&Runtime)->Result<()>
    ) -> Result<()> {
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
        if let Some(scheduler)=self.automatic.as_mut(){
            candidate.stabilize_automatic(scheduler)?;
        }else{
            candidate.stabilize()?;
        }
        validate(&candidate)?;
        let snapshot = candidate.snapshot();
        // Record only successful explicitly supplied facts; never log a
        // failed candidate or invent a value for an uncarried source.
        if !facts.is_empty(){self.fact_log.insert(next,facts.to_vec());}
        self.current = candidate;
        self.epoch = next;
        self.snapshots.push_back((next, snapshot));
        while self.snapshots.len() > self.retention {
            self.snapshots.pop_front();
        }
        Ok(())
    }
}

//! Narrow typed host-side resource storage for DOC-authored data/effects.
//! No gameplay decisions run here. Handles are generational and stale IDs fail
//! closed after replacement, eviction or complete release, even on slot reuse.
//! The logical payload-byte budget is NOT a measurement of heap allocation.

use crate::{Result,Type,Value};

#[derive(Debug,Clone,Copy,PartialEq,Eq,Hash)]
pub struct DataHandle {
    pub slot: u32,
    pub generation: u64,
}
#[derive(Debug)]
struct Slot {
    generation: u64,
    value: Option<Value>,
    retired: bool,
}
#[derive(Debug)]
pub struct DataResources {
    slots: Vec<Slot>,
    maximum_slots: usize,
    maximum_payload_bytes: usize,
    live: usize,
    live_payload_bytes: usize,
    peak_payload_bytes: usize,
}
impl DataResources {
    pub fn new(maximum_slots: usize,maximum_payload_bytes: usize)->Result<Self>{
        if maximum_slots>1024 {return Err("DOC data resource slot ceiling is 1024".into());}
        Ok(Self{slots:Vec::new(),maximum_slots,maximum_payload_bytes,
            live:0,live_payload_bytes:0,peak_payload_bytes:0})
    }
    fn payload_bytes(value:&Value)->Result<usize>{
        value.validate()?;
        match value {
            Value::Int(_)=>Ok(8),
            Value::Bool(_)=>Ok(1),
            Value::MaybeInt(_)=>Ok(9),
            Value::Nat(v)|Value::Text(v)=>Ok(v.len()),
            Value::Ints(v)=>v.len().checked_mul(8).ok_or_else(
                ||"DOC data asset byte size overflow".into()),
        }
    }
    fn validate(&self,handle:DataHandle)->Result<usize>{
        let slot=usize::try_from(handle.slot).map_err(|_|"DOC handle slot invalid")?;
        let item=self.slots.get(slot).ok_or("DOC resource slot out of bounds")?;
        if item.retired || item.generation!=handle.generation || item.value.is_none(){
            return Err("DOC resource handle stale or released".into());
        }
        Ok(slot)
    }
    fn checked_budget(&self,old_bytes:usize,replacement_bytes:usize)->Result<usize>{
        let projected=self.live_payload_bytes.checked_sub(old_bytes)
            .and_then(|n|n.checked_add(replacement_bytes))
            .ok_or("DOC resource size accounting overflow")?;
        if projected>self.maximum_payload_bytes {
            return Err("DOC resource byte budget exceeded".into());
        }
        Ok(projected)
    }
    pub fn insert(&mut self,value:Value)->Result<DataHandle>{
        let bytes=Self::payload_bytes(&value)?;
        let total=self.checked_budget(0,bytes)?;
        let existing=self.slots.iter().position(|slot|slot.value.is_none()&&!slot.retired);
        let index=match existing {
            Some(idx)=>idx,
            None if self.slots.len()<self.maximum_slots=>self.slots.len(),
            None=>return Err("DOC resource slot capacity exhausted".into()),
        };
        let slot=u32::try_from(index).map_err(|_|"DOC resource slot index overflow")?;
        if index==self.slots.len(){
            self.slots.push(Slot{generation:1,value:Some(value),retired:false});
        }else{
            self.slots[index].value=Some(value);
        }
        self.live+=1;
        self.live_payload_bytes=total;
        self.peak_payload_bytes=self.peak_payload_bytes.max(total);
        Ok(DataHandle{slot,generation:self.slots[index].generation})
    }
    pub fn get(&self,handle:DataHandle,expected:Type)->Result<&Value>{
        let slot=self.validate(handle)?;
        let value=self.slots[slot].value.as_ref().ok_or("DOC resource missing")?;
        if value.kind()!=expected{return Err("DOC data asset type mismatch".into());}
        Ok(value)
    }
    /// Commit a correctly typed replacement and invalidate all previous handles.
    /// Failed replacement cannot mutate the resource table or its accounting.
    pub fn replace(&mut self,handle:DataHandle,replacement:Value)->Result<DataHandle>{
        let index=self.validate(handle)?;
        let previous=self.slots[index].value.as_ref().ok_or("DOC resource missing")?;
        if previous.kind()!=replacement.kind(){
            return Err("DOC asset replacement changes declared type".into());
        }
        let new_generation=self.slots[index].generation.checked_add(1)
            .ok_or("DOC resource generation exhausted")?;
        let old_bytes=Self::payload_bytes(previous)?;
        let new_bytes=Self::payload_bytes(&replacement)?;
        let total=self.checked_budget(old_bytes,new_bytes)?;
        self.slots[index].value=Some(replacement);
        self.slots[index].generation=new_generation;
        self.live_payload_bytes=total;
        self.peak_payload_bytes=self.peak_payload_bytes.max(total);
        Ok(DataHandle{slot:handle.slot,generation:new_generation})
    }
    /// Free a resource. Reused slots must have a different generation.
    /// A generation that cannot advance is permanently retired rather than wrapped.
    pub fn release(&mut self,handle:DataHandle)->Result<()>{
        let index=self.validate(handle)?;
        let bytes=Self::payload_bytes(self.slots[index].value.as_ref().unwrap())?;
        self.slots[index].value=None;
        self.live_payload_bytes=self.live_payload_bytes.checked_sub(bytes)
            .ok_or("DOC resource size accounting invalid")?;
        self.live-=1;
        match self.slots[index].generation.checked_add(1){
            Some(next)=>self.slots[index].generation=next,
            None=>self.slots[index].retired=true,
        }
        Ok(())
    }
    pub fn live_count(&self)->usize{self.live}
    pub fn live_payload_bytes(&self)->usize{self.live_payload_bytes}
    pub fn peak_payload_bytes(&self)->usize{self.peak_payload_bytes}
    pub fn allocated_slot_count(&self)->usize{self.slots.len()}
}

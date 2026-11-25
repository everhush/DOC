//! Sticky, device-local WebGPU fault authority. Reference-only ownership;
//! independent DOC must reproduce the protection without managed RC.
use crate::Result;
use std::sync::{Arc,atomic::{AtomicU8,Ordering}};
#[derive(Clone,Debug)]
pub(crate) struct DeviceHealth(Arc<AtomicU8>);
impl DeviceHealth {
    pub(crate) fn attach(device:&wgpu::Device)->Self {
        let health=Self(Arc::new(AtomicU8::new(0)));
        let lost=health.clone();
        device.set_device_lost_callback(move|reason,message|{
            lost.0.store(1,Ordering::Release);
            eprintln!("DOC_GPU_DEVICE_LOST: {reason:?}: {message}");
        });
        let uncaptured=health.clone();
        device.on_uncaptured_error(Box::new(move|error:wgpu::Error|{
            // A device loss has priority over a later validation/OOM error.
            let _=uncaptured.0.compare_exchange(0,2,Ordering::AcqRel,Ordering::Acquire);
            eprintln!("DOC_GPU_UNCAPTURED_ERROR: {error}");
        }));
        health
    }
    pub(crate) fn check(&self)->Result<()> {
        match self.0.load(Ordering::Acquire){
            0=>Ok(()),
            1=>Err("DOC_GPU_DEVICE_LOST: no candidate publication".into()),
            _=>Err("DOC_GPU_UNCAPTURED_ERROR: no candidate publication".into()),
        }
    }
}

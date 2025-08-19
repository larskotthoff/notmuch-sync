//! notmuch-sync: Rust implementation for synchronizing notmuch email databases
//! 
//! This crate provides a complete Rust port of the notmuch-sync Python tool,
//! enabling efficient synchronization of notmuch email databases and message 
//! files between local and remote systems.

pub use crate::notmuch_sync::*;

mod notmuch_sync;
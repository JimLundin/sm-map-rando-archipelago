//! `smmr_engine`: Map Rando (our fork) as a Python module, for the Archipelago world (world/smmr/core/engine.py is
//! its port, `smmr_engine.pyi` its types).
//!
//! Map Rando's own data (settings, worlds, randomizations) crosses as JSON text, opaque to Python; `Session.reach`,
//! the logic's hot path, takes and returns Python values. Long calls release the GIL. Map Rando's data is loaded once
//! per process (its data paths are process-wide, `maprando::paths`).

mod engine;
mod world;

use maprando_game::Item;
use pyo3::create_exception;
use pyo3::exceptions::PyException;
use pyo3::prelude::*;
use serde_json::{Value, json};
use std::collections::HashMap;
use std::path::PathBuf;
use std::sync::{Mutex, OnceLock};

create_exception!(smmr_engine, EngineError, PyException, "Map Rando rejected the request.");

static ENGINE: OnceLock<&'static engine::Engine> = OnceLock::new();

fn error(e: anyhow::Error) -> PyErr {
    EngineError::new_err(format!("{e:#}"))
}

fn parse(text: &str) -> PyResult<Value> {
    serde_json::from_str(text).map_err(|e| EngineError::new_err(format!("invalid JSON: {e}")))
}

/// Map Rando with its data loaded.
#[pyclass(frozen, module = "smmr_engine")]
struct Engine {
    inner: &'static engine::Engine,
}

#[pymethods]
impl Engine {
    /// Map Rando's data from `data_dir` (a MapRandomizer checkout, or the data the .apworld bundles), loaded once.
    #[staticmethod]
    fn load(py: Python<'_>, data_dir: PathBuf) -> PyResult<Self> {
        if let Some(&inner) = ENGINE.get() {
            if inner.rust_dir() != std::path::absolute(&data_dir)?.join("rust") {
                return Err(EngineError::new_err(format!(
                    "Map Rando's data is already loaded from {}", inner.rust_dir().display())));
            }
            return Ok(Engine { inner });
        }
        let loaded = py.detach(|| engine::Engine::load(&data_dir)).map_err(error)?;
        let inner: &'static engine::Engine = Box::leak(Box::new(loaded));
        Ok(Engine { inner: *ENGINE.get_or_init(|| inner) })
    }

    fn info(&self, py: Python<'_>) -> PyResult<String> {
        let inner = self.inner;
        py.detach(|| inner.info()).map(|x| x.to_string()).map_err(error)
    }

    fn upgrade(&self, py: Python<'_>, settings: &str) -> PyResult<String> {
        let (inner, request) = (self.inner, json!({ "settings": parse(settings)? }));
        py.detach(|| inner.upgrade(&request)).map(|x| x["settings"].to_string()).map_err(error)
    }

    #[pyo3(signature = (settings, seed, maps_dir=None))]
    fn randomize(&self, py: Python<'_>, settings: &str, seed: u64, maps_dir: Option<PathBuf>) -> PyResult<String> {
        let (inner, request) = (self.inner, json!({ "settings": parse(settings)?, "seed": seed, "maps_dir": maps_dir }));
        py.detach(|| inner.randomize(&request)).map(|x| x.to_string()).map_err(error)
    }

    #[pyo3(signature = (settings, seed, maps_dir=None))]
    fn world(&self, py: Python<'_>, settings: &str, seed: u64, maps_dir: Option<PathBuf>) -> PyResult<String> {
        let (inner, request) = (self.inner, json!({ "settings": parse(settings)?, "seed": seed, "maps_dir": maps_dir }));
        py.detach(|| inner.world(&request)).map(|x| x.to_string()).map_err(error)
    }

    fn open(&self, py: Python<'_>, settings: &str, world: &str) -> PyResult<Session> {
        let (inner, settings, world) = (self.inner, parse(settings)?, parse(world)?);
        let session = py.detach(|| inner.open(&settings, &world)).map_err(error)?;
        Ok(Session { inner: Mutex::new(session) })
    }

    /// `reach` without a session: `{settings, world, inventories, chain?}` (tools/check_reach.py).
    fn reach(&self, py: Python<'_>, request: &str) -> PyResult<String> {
        let (inner, request) = (self.inner, parse(request)?);
        py.detach(|| inner.reach(&request)).map(|x| x.to_string()).map_err(error)
    }

    /// Writes Map Rando's ROM: `{settings, randomization, rom, out}` or `{settings, world, item_placement,
    /// foreign_items, rom, out}`.
    fn rom(&self, py: Python<'_>, request: &str) -> PyResult<()> {
        let (inner, request) = (self.inner, parse(request)?);
        py.detach(|| inner.rom(&request)).map(|_| ()).map_err(error)
    }
}

/// A world's logic, set up once.
#[pyclass(frozen, module = "smmr_engine")]
struct Session {
    inner: Mutex<engine::Session>,
}

#[pymethods]
impl Session {
    /// For each inventory (Map Rando item → count, on top of the starting items): the item locations Samus can reach
    /// and come back from, and whether she can defeat Mother Brain.
    fn reach(&self, py: Python<'_>, inventories: Vec<HashMap<String, usize>>) -> PyResult<Vec<(Vec<usize>, bool)>> {
        let inventories = inventories
            .into_iter()
            .map(|inventory| {
                inventory
                    .into_iter()
                    .map(|(name, count)| {
                        Item::try_from(name.as_str())
                            .map(|item| (item, count))
                            .map_err(|_| EngineError::new_err(format!("unknown item {name}")))
                    })
                    .collect::<PyResult<Vec<_>>>()
            })
            .collect::<PyResult<Vec<_>>>()?;
        let session = &self.inner;
        let answers = py.detach(|| session.lock().expect("a reach panicked").reach(&inventories));
        Ok(answers.into_iter().map(|x| (x.locations, x.beatable)).collect())
    }
}

#[pymodule]
fn smmr_engine(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<Engine>()?;
    m.add_class::<Session>()?;
    m.add("EngineError", m.py().get_type::<EngineError>())?;
    Ok(())
}

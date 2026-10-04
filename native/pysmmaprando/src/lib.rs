//! Python bindings to the Map Randomizer, used by the Archipelago "Super Metroid Map Rando" world.
//!
//! The interface is deliberately coarse-grained and JSON based: settings, randomizations and
//! customization settings cross the boundary as JSON strings using exactly the same formats as
//! the maprando.com website, so that the Rust side stays a thin wrapper around the upstream crates.

use std::path::{Path, PathBuf};
use std::sync::Mutex;

use anyhow::{Context, Result, bail};
use hashbrown::HashMap;
use log::info;
use maprando::customize::mosaic::MosaicTheme;
use maprando::customize::samus_sprite::SamusSpriteCategory;
use maprando::customize::{
    ControllerButton, ControllerConfig, CustomizeSettings, DoorTheme, FlashingSetting,
    ItemDotChange, MapTheme, MusicSettings, PaletteTheme, ShakingSetting, StatuesHallwayAudio,
    StatuesHallwayTiling, TileTheme, parse_controller_button,
};
use maprando::difficulty::{get_full_global, get_link_difficulty_length};
use maprando::map_repository::{MapRepository, MapSettings, OfflineMapRepository};
use maprando::patch::{Rom, make_rom};
use maprando::preset::PresetData;
use maprando::randomize::{
    Randomization, Randomizer, assign_map_areas, filter_links, get_difficulty_tiers,
    get_objectives, randomize_doors,
};
use maprando::settings::{RandomizerSettings, StartLocationMode, try_upgrade_settings};
use maprando_game::{GameData, LinksDataGroup, Map};
use pyo3::exceptions::PyRuntimeError;
use pyo3::prelude::*;
use pyo3::types::PyBytes;
use rand::{RngCore, SeedableRng};
use serde::{Deserialize, Serialize};

const MAP_POOL_BASE_URL: &str = "https://map-rando-artifacts.s3.us-west-004.backblazeb2.com/maps";
const MAP_POOL_VERSION: &str = "v119";

fn to_py_err(e: anyhow::Error) -> PyErr {
    PyRuntimeError::new_err(format!("{e:?}"))
}

/// Map repository which lazily downloads map pool batch files (via a Python callback) into a
/// local cache directory, and reads the vanilla map from the bundled data.
struct LazyMapRepository {
    vanilla: OfflineMapRepository,
    cache_dir: PathBuf,
    fetcher: Py<PyAny>,
    manifests: Mutex<HashMap<String, Vec<String>>>,
}

#[derive(Deserialize)]
struct PoolManifest {
    files: Vec<String>,
}

impl LazyMapRepository {
    fn fetch(&self, pool_dir: &str, filename: &str) -> Result<PathBuf> {
        let dest = self.cache_dir.join(pool_dir).join(filename);
        if dest.exists() {
            return Ok(dest);
        }
        std::fs::create_dir_all(dest.parent().unwrap())?;
        let url = format!("{MAP_POOL_BASE_URL}/{pool_dir}/{filename}");
        info!("Downloading {url}");
        Python::attach(|py| -> PyResult<()> {
            self.fetcher
                .call1(py, (url.clone(), dest.to_string_lossy().to_string()))?;
            Ok(())
        })
        .with_context(|| format!("downloading {url}"))?;
        if !dest.exists() {
            bail!("Map pool download did not produce {}", dest.display());
        }
        Ok(dest)
    }

    fn manifest_files(&self, pool_dir: &str) -> Result<Vec<String>> {
        if let Some(files) = self.manifests.lock().unwrap().get(pool_dir) {
            return Ok(files.clone());
        }
        let path = self.fetch(pool_dir, "manifest.json")?;
        let manifest: PoolManifest = serde_json::from_slice(&std::fs::read(&path)?)?;
        if manifest.files.is_empty() {
            bail!("Empty map pool manifest: {}", path.display());
        }
        self.manifests
            .lock()
            .unwrap()
            .insert(pool_dir.to_string(), manifest.files.clone());
        Ok(manifest.files)
    }
}

impl MapRepository for LazyMapRepository {
    fn get_map_batch(
        &self,
        seed: usize,
        settings: MapSettings,
        game_data: &GameData,
    ) -> Result<Vec<Map>> {
        if settings.vanilla {
            return self.vanilla.get_map_batch(seed, settings, game_data);
        }
        let (pool_name, pool_key) = if settings.small {
            ("Small", "small")
        } else if settings.wild {
            ("Wild", "wild")
        } else {
            ("Standard", "standard")
        };
        let pool_dir = format!("{MAP_POOL_VERSION}-{pool_key}-avro");
        let files = self.manifest_files(&pool_dir)?;
        let idx = seed % files.len();
        self.fetch(&pool_dir, &files[idx])?;

        // Present the single downloaded batch file as a one-file offline pool. The offline pool
        // selects file `seed % 1 == 0` and shuffles it using `seed`, which produces exactly the
        // same maps as an offline pool containing the full set of files.
        let batch_dir = self.cache_dir.join(&pool_dir).join(format!("batch-{idx}"));
        std::fs::create_dir_all(&batch_dir)?;
        let manifest = serde_json::json!({
            "maps_per_file": 1000,
            "files": [format!("../{}", files[idx])],
        });
        std::fs::write(batch_dir.join("manifest.json"), manifest.to_string())?;
        let repo = OfflineMapRepository::new(vec![(pool_name, &batch_dir)])?;
        repo.get_map_batch(seed, settings, game_data)
    }
}

#[derive(Serialize)]
struct ItemLocationInfo {
    index: usize,
    room_id: usize,
    node_id: usize,
    room_name: String,
    node_name: String,
    plm_ptr: usize,
}

#[derive(Serialize)]
struct RandomizeOutput {
    randomization: serde_json::Value,
    summary: serde_json::Value,
    objectives: Vec<String>,
    start_location_name: String,
    hub_location_name: String,
    random_seed: usize,
    map_seed: usize,
    door_randomization_seed: usize,
    item_placement_seed: usize,
    seed_hash: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    spoiler_log: Option<serde_json::Value>,
}

/// Customization (cosmetic) settings, using the same field names and values as the website's
/// "Customize" form.
#[derive(Deserialize)]
#[serde(default)]
struct CustomizeRequest {
    samus_sprite: String,
    etank_color: String,
    map_theme: String,
    item_dot_change: String,
    transition_letters: bool,
    reserve_hud_style: bool,
    room_palettes: String,
    tile_theme: String,
    door_theme: String,
    music: String,
    disable_beeping: bool,
    shaking: String,
    flashing: String,
    vanilla_screw_attack_animation: bool,
    save_icons: bool,
    boss_icons: bool,
    miniboss_icons: bool,
    room_names: bool,
    statues_hallway_tiling: String,
    statues_hallway_audio: String,
    control_shot: String,
    control_jump: String,
    control_dash: String,
    control_item_select: String,
    control_item_cancel: String,
    control_angle_up: String,
    control_angle_down: String,
    spin_lock_buttons: Vec<String>,
    quick_reload_buttons: Vec<String>,
    save_state_buttons: Vec<String>,
    load_state_buttons: Vec<String>,
    moonwalk: bool,
}

impl Default for CustomizeRequest {
    fn default() -> Self {
        let buttons = |v: &[&str]| v.iter().map(|x| x.to_string()).collect::<Vec<String>>();
        CustomizeRequest {
            samus_sprite: "samus_vanilla".to_string(),
            etank_color: "DE3894".to_string(),
            map_theme: "Light".to_string(),
            item_dot_change: "Fade".to_string(),
            transition_letters: true,
            reserve_hud_style: true,
            room_palettes: "area-themed".to_string(),
            tile_theme: "none".to_string(),
            door_theme: "vanilla".to_string(),
            music: "area".to_string(),
            disable_beeping: false,
            shaking: "Vanilla".to_string(),
            flashing: "Vanilla".to_string(),
            vanilla_screw_attack_animation: true,
            save_icons: true,
            boss_icons: true,
            miniboss_icons: true,
            room_names: true,
            statues_hallway_tiling: "Default".to_string(),
            statues_hallway_audio: "Enabled".to_string(),
            control_shot: "X".to_string(),
            control_jump: "A".to_string(),
            control_dash: "B".to_string(),
            control_item_select: "Select".to_string(),
            control_item_cancel: "Y".to_string(),
            control_angle_up: "R".to_string(),
            control_angle_down: "L".to_string(),
            spin_lock_buttons: buttons(&["X", "L", "R", "Up"]),
            quick_reload_buttons: buttons(&["L", "R", "Select", "Start"]),
            save_state_buttons: buttons(&["Select", "B"]),
            load_state_buttons: buttons(&["Select", "A"]),
            moonwalk: false,
        }
    }
}

fn parse_button_list(buttons: &[String]) -> Result<Vec<ControllerButton>> {
    buttons
        .iter()
        .map(|b| match b.as_str() {
            "Start" => Ok(ControllerButton::Start),
            other => parse_controller_button(other),
        })
        .collect()
}

fn parse_customize_settings(req: &CustomizeRequest) -> Result<CustomizeSettings> {
    let etank_color = if req.etank_color.len() == 6 {
        Some((
            u8::from_str_radix(&req.etank_color[0..2], 16)? / 8,
            u8::from_str_radix(&req.etank_color[2..4], 16)? / 8,
            u8::from_str_radix(&req.etank_color[4..6], 16)? / 8,
        ))
    } else {
        None
    };
    Ok(CustomizeSettings {
        samus_sprite: Some(req.samus_sprite.clone()),
        etank_color,
        map_theme: match req.map_theme.as_str() {
            "Light" => MapTheme::Light,
            "Dark" => MapTheme::Dark,
            x => bail!("Unexpected map_theme: {x}"),
        },
        item_dot_change: match req.item_dot_change.as_str() {
            "Stay" => ItemDotChange::Stay,
            "Fade" => ItemDotChange::Fade,
            "Disappear" => ItemDotChange::Disappear,
            x => bail!("Unexpected item_dot_change: {x}"),
        },
        transition_letters: req.transition_letters,
        reserve_hud_style: req.reserve_hud_style,
        vanilla_screw_attack_animation: req.vanilla_screw_attack_animation,
        room_names: req.room_names,
        palette_theme: match req.room_palettes.as_str() {
            "area-themed" => PaletteTheme::AreaThemed,
            "area-shuffled" => PaletteTheme::AreaShuffled,
            "scrambled" => PaletteTheme::Scrambled,
            "vanilla" => PaletteTheme::Vanilla,
            "crateria" => PaletteTheme::Constant(0),
            "brinstar" => PaletteTheme::Constant(1),
            "norfair" => PaletteTheme::Constant(2),
            "wrecked-ship" => PaletteTheme::Constant(3),
            "maridia" => PaletteTheme::Constant(4),
            "tourian" => PaletteTheme::Constant(5),
            x => bail!("Unexpected room_palettes: {x}"),
        },
        tile_theme: match req.tile_theme.as_str() {
            "none" => TileTheme::Vanilla,
            "scrambled" => TileTheme::Scrambled,
            "area_themed" => TileTheme::AreaThemed,
            "area_shuffled" => TileTheme::AreaShuffled,
            x => TileTheme::Constant(x.to_string()),
        },
        door_theme: match req.door_theme.as_str() {
            "vanilla" => DoorTheme::Vanilla,
            "vibrant" => DoorTheme::Vibrant,
            "contrast" => DoorTheme::Contrast,
            x => bail!("Unexpected door_theme: {x}"),
        },
        music: match req.music.as_str() {
            "area" => MusicSettings::AreaThemed,
            "disabled" => MusicSettings::Disabled,
            x => bail!("Unexpected music: {x}"),
        },
        disable_beeping: req.disable_beeping,
        shaking: match req.shaking.as_str() {
            "Vanilla" => ShakingSetting::Vanilla,
            "Reduced" => ShakingSetting::Reduced,
            "Disabled" => ShakingSetting::Disabled,
            x => bail!("Unexpected shaking: {x}"),
        },
        flashing: match req.flashing.as_str() {
            "Vanilla" => FlashingSetting::Vanilla,
            "Reduced" => FlashingSetting::Reduced,
            x => bail!("Unexpected flashing: {x}"),
        },
        save_icons: req.save_icons,
        boss_icons: req.boss_icons,
        miniboss_icons: req.miniboss_icons,
        statues_hallway_tiling: match req.statues_hallway_tiling.as_str() {
            "Disabled" => StatuesHallwayTiling::Disabled,
            "Default" => StatuesHallwayTiling::Default,
            "Enabled" => StatuesHallwayTiling::Enabled,
            x => bail!("Unexpected statues_hallway_tiling: {x}"),
        },
        statues_hallway_audio: match req.statues_hallway_audio.as_str() {
            "Disabled" => StatuesHallwayAudio::Disabled,
            "Enabled" => StatuesHallwayAudio::Enabled,
            "Louder" => StatuesHallwayAudio::Louder,
            x => bail!("Unexpected statues_hallway_audio: {x}"),
        },
        controller_config: ControllerConfig {
            shot: parse_controller_button(&req.control_shot)?,
            jump: parse_controller_button(&req.control_jump)?,
            dash: parse_controller_button(&req.control_dash)?,
            item_select: parse_controller_button(&req.control_item_select)?,
            item_cancel: parse_controller_button(&req.control_item_cancel)?,
            angle_up: parse_controller_button(&req.control_angle_up)?,
            angle_down: parse_controller_button(&req.control_angle_down)?,
            spin_lock_buttons: parse_button_list(&req.spin_lock_buttons)?,
            quick_reload_buttons: parse_button_list(&req.quick_reload_buttons)?,
            save_state_buttons: parse_button_list(&req.save_state_buttons)?,
            load_state_buttons: parse_button_list(&req.load_state_buttons)?,
            moonwalk: req.moonwalk,
        },
    })
}

fn get_seed_hash(display_seed: usize) -> String {
    // This must match the enemy name list in seed_hash_display.asm (copied from maprando-web).
    let enemies = [
        "GEEMER", "RIPPER", "ATOMIC", "POWAMP", "SCISER", "NAMIHE", "PUROMI", "ALCOON", "BEETOM",
        "OWTCH", "ZEBBO", "ZEELA", "HOLTZ", "VIOLA", "WAVER", "RINKA", "BOYON", "CHOOT", "KAGO",
        "SKREE", "COVERN", "EVIR", "TATORI", "OUM", "PUYO", "YARD", "ZOA", "FUNE", "GAMET",
        "GERUTA", "SOVA", "BULL",
    ];
    (display_seed as u32)
        .to_le_bytes()
        .into_iter()
        .map(|i| enemies[i as usize % 32].to_string())
        .collect::<Vec<String>>()
        .join(" ")
}

#[pyclass(frozen)]
struct MapRando {
    game_data: GameData,
    preset_data: PresetData,
    map_repository: LazyMapRepository,
    samus_sprite_categories: Vec<SamusSpriteCategory>,
    mosaic_themes: Vec<MosaicTheme>,
}

impl MapRando {
    fn load(data_root: &Path, cache_dir: &Path, fetcher: Py<PyAny>) -> Result<Self> {
        let rust_dir = data_root.join("rust");
        maprando::paths::set_data_root(&rust_dir);
        let mut game_data = GameData::load(&rust_dir)?;
        let preset_data = PresetData::load(
            &rust_dir.join("data/tech_data.json"),
            &rust_dir.join("data/notable_data.json"),
            &rust_dir.join("data/presets"),
            &game_data,
        )?;
        let global = get_full_global(&game_data);
        game_data.make_links_data(&|link, game_data| {
            get_link_difficulty_length(link, game_data, &preset_data, &global)
        });

        let vanilla = OfflineMapRepository::new(vec![("Vanilla", &data_root.join("maps/vanilla"))])?;
        let map_repository = LazyMapRepository {
            vanilla,
            cache_dir: cache_dir.to_owned(),
            fetcher,
            manifests: Mutex::new(HashMap::new()),
        };

        let sprites_manifest = data_root.join("MapRandoSprites/samus_sprites/manifest.json");
        let samus_sprite_categories: Vec<SamusSpriteCategory> =
            serde_json::from_str(&std::fs::read_to_string(&sprites_manifest).with_context(
                || format!("reading {}", sprites_manifest.display()),
            )?)?;

        let mosaic_themes = [
            ("OuterCrateria", "Outer Crateria"),
            ("InnerCrateria", "Inner Crateria"),
            ("BlueBrinstar", "Blue Brinstar"),
            ("GreenBrinstar", "Green Brinstar"),
            ("PinkBrinstar", "Pink Brinstar"),
            ("RedBrinstar", "Red Brinstar"),
            ("WarehouseBrinstar", "Warehouse Brinstar"),
            ("UpperNorfair", "Upper Norfair"),
            ("LowerNorfair", "Lower Norfair"),
            ("WreckedShip", "Wrecked Ship"),
            ("WestMaridia", "West Maridia"),
            ("YellowMaridia", "Yellow Maridia"),
            ("Bedrock", "Bedrock"),
            ("MechaTourian", "Mecha Tourian"),
            ("MetroidHabitat", "Metroid Habitat"),
        ]
        .into_iter()
        .map(|(x, y)| MosaicTheme {
            name: x.to_string(),
            display_name: y.to_string(),
        })
        .collect();

        Ok(MapRando {
            game_data,
            preset_data,
            map_repository,
            samus_sprite_categories,
            mosaic_themes,
        })
    }

    fn parse_settings(&self, settings_json: &str) -> Result<RandomizerSettings> {
        let (_, mut settings) =
            try_upgrade_settings(settings_json.to_string(), &self.preset_data, true)?;
        if !self.preset_data.full_presets.iter().any(|s| s == &settings) {
            settings.name = Some("Custom".to_string());
        }
        if settings.skill_assumption_settings.ridley_proficiency < 0.0
            || settings.skill_assumption_settings.ridley_proficiency > 1.0
        {
            bail!("Invalid Ridley proficiency");
        }
        Ok(settings)
    }

    #[allow(clippy::too_many_arguments)]
    fn randomize_impl(
        &self,
        settings: &RandomizerSettings,
        random_seed: usize,
        display_seed: usize,
        fixed_map_seed: Option<usize>,
        given_map: Option<&Map>,
        fixed_door_seed: Option<usize>,
        forbidden_start_locations: &[String],
        max_attempts: usize,
        include_spoiler_log: bool,
    ) -> Result<RandomizeOutput> {
        let game_data = &self.game_data;
        let preset_data = &self.preset_data;
        let mut rng_seed = [0u8; 32];
        rng_seed[..8].copy_from_slice(&random_seed.to_le_bytes());
        let mut rng = rand::rngs::StdRng::from_seed(rng_seed);

        let difficulty_tiers = get_difficulty_tiers(
            settings,
            &preset_data.difficulty_tiers,
            game_data,
            &preset_data.tech_by_difficulty["Implicit"],
            &preset_data.notables_by_difficulty["Implicit"],
        );
        let filtered_base_links =
            filter_links(&game_data.links, game_data, &difficulty_tiers[0]);
        let filtered_base_links_data =
            LinksDataGroup::new(filtered_base_links, game_data.vertex_isv.keys.len(), 0);
        let mut map_settings = MapSettings::from_map_layout(&settings.map_layout)?;
        map_settings.area_assignment_base_order =
            settings.other_settings.area_assignment.base_order;
        let requires_area_assignment = self.map_repository.requires_area_assignment(map_settings);

        let max_attempts_per_map =
            if settings.start_location_settings.mode == StartLocationMode::Random {
                10
            } else {
                1
            };
        let max_map_attempts = (max_attempts / max_attempts_per_map).max(1);
        let mut attempt_num = 0;
        let mut map_batch: Vec<Map> = vec![];
        let mut fixed_map: Option<Map> = None;
        for _ in 0..max_map_attempts {
            let map_seed = fixed_map_seed.unwrap_or_else(|| (rng.next_u64() & 0xFFFFFFFF) as usize);
            let rng_door_seed = (rng.next_u64() & 0xFFFFFFFF) as usize;
            let door_randomization_seed = fixed_door_seed.unwrap_or(rng_door_seed);

            let mut map = if let Some(m) = given_map {
                // A shared map layout given directly (with areas already assigned).
                m.clone()
            } else if fixed_map_seed.is_some() {
                // A shared map layout: always use the same map, rather than moving on to the
                // next map in the batch after a failed attempt.
                if fixed_map.is_none() {
                    let mut batch = self.map_repository.get_map_batch(
                        map_seed,
                        map_settings,
                        game_data,
                    )?;
                    fixed_map = Some(batch.pop().context("empty map batch")?);
                }
                fixed_map.clone().unwrap()
            } else {
                if map_batch.is_empty() {
                    map_batch = self
                        .map_repository
                        .get_map_batch(map_seed, map_settings, game_data)?;
                }
                map_batch.pop().context("empty map batch")?
            };
            if given_map.is_none()
                && requires_area_assignment
                && !assign_map_areas(&mut map, settings, map_seed, game_data)
            {
                info!("Area assignment failed for map seed={map_seed}");
                if fixed_map_seed.is_some() {
                    bail!("Area assignment failed for shared map seed={map_seed}");
                }
                continue;
            }
            let objectives = get_objectives(settings, Some(&map), game_data, &mut rng);
            let locked_door_data = randomize_doors(
                game_data,
                &map,
                settings,
                &objectives,
                door_randomization_seed,
            );
            let randomizer = Randomizer::new(
                &map,
                &locked_door_data,
                objectives.clone(),
                settings,
                &difficulty_tiers,
                game_data,
                &filtered_base_links_data,
                &mut rng,
            );
            for _ in 0..max_attempts_per_map {
                let item_placement_seed = (rng.next_u64() & 0xFFFFFFFF) as usize;
                attempt_num += 1;
                info!(
                    "Attempt {attempt_num}/{max_attempts}: Map seed={map_seed}, door randomization seed={door_randomization_seed}, item placement seed={item_placement_seed}"
                );
                let (randomization, spoiler_log) =
                    match randomizer.randomize(attempt_num, item_placement_seed, display_seed, true)
                    {
                        Ok(x) => x,
                        Err(e) => {
                            info!("Attempt {attempt_num}/{max_attempts}: Randomization failed: {e}");
                            continue;
                        }
                    };
                if forbidden_start_locations.contains(&randomization.start_location.name) {
                    info!(
                        "Attempt {attempt_num}/{max_attempts}: start location {} already used",
                        randomization.start_location.name
                    );
                    continue;
                }
                return Ok(RandomizeOutput {
                    randomization: serde_json::to_value(&randomization)?,
                    summary: serde_json::to_value(&spoiler_log.summary)?,
                    objectives: spoiler_log.objectives.clone(),
                    start_location_name: randomization.start_location.name.clone(),
                    hub_location_name: spoiler_log.hub_location_name.clone(),
                    random_seed,
                    map_seed,
                    door_randomization_seed,
                    item_placement_seed,
                    seed_hash: get_seed_hash(randomization.display_seed),
                    spoiler_log: if include_spoiler_log {
                        Some(serde_json::to_value(&spoiler_log)?)
                    } else {
                        None
                    },
                });
            }
        }
        bail!("Failed too many randomization attempts ({attempt_num})")
    }
}

#[pymethods]
impl MapRando {
    /// Load the game data. `data_root` is a directory laid out like the MapRandomizer repository
    /// (containing `rust/data`, `sm-json-data`, `patches`, ...). Map pool files are downloaded on
    /// demand into `cache_dir`, by calling `fetcher(url, dest_path)`.
    #[new]
    fn new(py: Python<'_>, data_root: &str, cache_dir: &str, fetcher: Py<PyAny>) -> PyResult<Self> {
        let data_root = PathBuf::from(data_root);
        let cache_dir = PathBuf::from(cache_dir);
        py.detach(|| MapRando::load(&data_root, &cache_dir, fetcher))
            .map_err(to_py_err)
    }

    /// Validate settings JSON (as exported by maprando.com, possibly from an older version),
    /// apply any named presets, and return the complete upgraded settings JSON.
    fn upgrade_settings(&self, settings_json: &str) -> PyResult<String> {
        let settings = self.parse_settings(settings_json).map_err(to_py_err)?;
        serde_json::to_string(&settings).map_err(|e| to_py_err(e.into()))
    }

    /// All presets, as loaded by Map Rando (in the website's order), as JSON:
    /// {"full": [...], "skill": [...], "item_progression": [...], "quality_of_life": [...], "objectives": [...],
    ///  "doors": [...], "difficulty_levels": [...]}
    fn presets_json(&self) -> PyResult<String> {
        let p = &self.preset_data;
        let out = serde_json::json!({
            "full": p.full_presets,
            "skill": p.skill_presets,
            "item_progression": p.item_progression_presets,
            "quality_of_life": p.quality_of_life_presets,
            "objectives": p.objective_presets,
            "doors": p.doors_presets,
            "difficulty_levels": p.difficulty_levels.keys,
        });
        serde_json::to_string(&out).map_err(|e| to_py_err(e.into()))
    }

    /// The website's default settings, as JSON.
    fn default_settings(&self) -> PyResult<String> {
        serde_json::to_string(&self.preset_data.default_preset).map_err(|e| to_py_err(e.into()))
    }

    /// Generate a randomization (map, doors, objectives, item placement). Returns JSON.
    /// `fixed_map_json` gives a map layout to use (with areas already assigned), e.g. the map of another
    /// randomization, for worlds sharing a map.
    #[pyo3(signature = (settings_json, random_seed, display_seed=None, fixed_map_seed=None, fixed_map_json=None, fixed_door_seed=None, forbidden_start_locations=vec![], max_attempts=2000, include_spoiler_log=false))]
    #[allow(clippy::too_many_arguments)]
    fn randomize(
        &self,
        settings_json: &str,
        random_seed: usize,
        display_seed: Option<usize>,
        fixed_map_seed: Option<usize>,
        fixed_map_json: Option<&str>,
        fixed_door_seed: Option<usize>,
        forbidden_start_locations: Vec<String>,
        max_attempts: usize,
        include_spoiler_log: bool,
    ) -> PyResult<String> {
        if random_seed == 0 {
            return Err(PyRuntimeError::new_err("Invalid random seed: 0"));
        }
        let settings = self.parse_settings(settings_json).map_err(to_py_err)?;
        let fixed_map: Option<Map> = match fixed_map_json {
            Some(j) => Some(serde_json::from_str(j).map_err(|e| to_py_err(e.into()))?),
            None => None,
        };
        let output = self
            .randomize_impl(
                &settings,
                random_seed,
                display_seed.unwrap_or(random_seed),
                fixed_map_seed,
                fixed_map.as_ref(),
                fixed_door_seed,
                &forbidden_start_locations,
                max_attempts,
                include_spoiler_log,
            )
            .map_err(to_py_err)?;
        serde_json::to_string(&output).map_err(|e| to_py_err(e.into()))
    }

    /// Patch an (unheadered, vanilla) Super Metroid ROM according to a randomization. If `item_plm_types` is given
    /// (visible, chozo orb, shot block), these PLM types are used for all items except Nothing.
    #[pyo3(signature = (base_rom, settings_json, randomization_json, customize_json, item_plm_types=None))]
    fn make_rom<'py>(
        &self,
        py: Python<'py>,
        base_rom: &[u8],
        settings_json: &str,
        randomization_json: &str,
        customize_json: &str,
        item_plm_types: Option<[isize; 3]>,
    ) -> PyResult<Bound<'py, PyBytes>> {
        let settings = self.parse_settings(settings_json).map_err(to_py_err)?;
        let mut randomization: Randomization = serde_json::from_str(randomization_json)
            .map_err(|e| to_py_err(anyhow::Error::from(e).context("parsing randomization")))?;
        if randomization.map.room_mask.is_empty() {
            randomization.map.room_mask = vec![true; randomization.map.rooms.len()];
        }
        let customize_req: CustomizeRequest = serde_json::from_str(customize_json)
            .map_err(|e| to_py_err(anyhow::Error::from(e).context("parsing customize settings")))?;
        let customize_settings = parse_customize_settings(&customize_req).map_err(to_py_err)?;
        let mut rom = Rom::new(base_rom.to_vec());
        rom.data.resize(0x400000, 0);
        maprando::patch::set_item_plm_override(item_plm_types);
        let output = make_rom(
            &rom,
            &settings,
            &customize_settings,
            &randomization,
            &self.game_data,
            &self.samus_sprite_categories,
            &self.mosaic_themes,
        );
        maprando::patch::set_item_plm_override(None);
        let output = output.map_err(to_py_err)?;
        Ok(PyBytes::new(py, &output.data))
    }

    /// Information about the 100 item locations, in the order used by `item_placement`.
    fn item_locations(&self) -> PyResult<String> {
        let gd = &self.game_data;
        let mut out = vec![];
        for (index, &(room_id, node_id)) in gd.item_locations.iter().enumerate() {
            out.push(ItemLocationInfo {
                index,
                room_id,
                node_id,
                room_name: gd.room_json_map[&room_id]["name"]
                    .as_str()
                    .unwrap_or_default()
                    .to_string(),
                node_name: gd.node_json_map[&(room_id, node_id)]["name"]
                    .as_str()
                    .unwrap_or_default()
                    .to_string(),
                plm_ptr: gd.node_ptr_map[&(room_id, node_id)],
            });
        }
        serde_json::to_string(&out).map_err(|e| to_py_err(e.into()))
    }

    /// Names of the available start locations (for the "Custom" start location mode), as JSON.
    fn start_locations(&self) -> PyResult<String> {
        let v: Vec<serde_json::Value> = self
            .game_data
            .start_locations
            .iter()
            .map(|s| serde_json::json!({"name": s.name, "room_id": s.room_id, "node_id": s.node_id}))
            .collect();
        serde_json::to_string(&v).map_err(|e| to_py_err(e.into()))
    }
}

/// Decompress a zstd-compressed file (used for the Mosaic tile theme patch archive).
#[pyfunction]
fn zstd_decompress_file(py: Python<'_>, src: &str, dst: &str) -> PyResult<()> {
    py.detach(|| -> Result<()> {
        let input = std::fs::File::open(src)?;
        let mut output = std::fs::File::create(dst)?;
        zstd::stream::copy_decode(input, &mut output)?;
        Ok(())
    })
    .map_err(to_py_err)
}

/// Initialize logging from the Rust side (to stderr). `level` is e.g. "error", "info", "debug".
#[pyfunction]
fn init_logging(level: &str) {
    let _ = env_logger::Builder::from_env(env_logger::Env::default().default_filter_or(level))
        .format_timestamp_millis()
        .try_init();
}

#[pymodule]
fn pysmmaprando(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<MapRando>()?;
    m.add_function(wrap_pyfunction!(zstd_decompress_file, m)?)?;
    m.add_function(wrap_pyfunction!(init_logging, m)?)?;
    m.add("VERSION", env!("CARGO_PKG_VERSION"))?;
    Ok(())
}
